# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later AND LGPL-2.1-or-later

# Urwid main loop code
#    Copyright (C) 2004-2012  Ian Ward
#    Copyright (C) 2008 Walter Mundt
#    Copyright (C) 2009 Andrew Psaltis
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Urwid web site: http://excess.org/urwid/

import fcntl
import os
import signal
import time

from urwid.util import StoppingContext
from urwid import signals

from .display import INPUT_DESCRIPTORS_CHANGED
from . import display as raw_display


PIPE_BUFFER_READ_SIZE = 4096 # can expect this much on Linux, so try for that

class ExitMainLoop(Exception):
    """
    When this exception is raised within a main loop the main loop
    will exit cleanly.
    """
    pass

class CantUseExternalLoop(Exception):
    pass

class MainLoop(object):
    """
    This is the standard main loop implementation for a single interactive
    session.

    :param screen: screen to use, default is a new :class:`raw_display.Screen`
                   instance; stored as :attr:`screen`
    :type screen: display module screen instance

    :param unhandled_input: a function called when input is not handled by
                            :attr:`.widget`, called from :meth:`.unhandled_input`
    :type unhandled_input: callable

    :param event_loop: if :attr:`.screen` supports external an event loop it may be
                       given here, default is a new :class:`SelectEventLoop` instance;
                       stored as :attr:`.event_loop`
    :type event_loop: event loop instance



    .. attribute:: screen

        The screen object this main loop uses for screen updates and reading input

    .. attribute:: event_loop

        The event loop object this main loop uses for waiting on alarms and IO
    """

    def __init__(self, screen=None, unhandled_input=None, event_loop=None):

        if not screen:
            screen = raw_display.Screen()

        self.screen = screen

        self._unhandled_input = unhandled_input

        if not hasattr(screen, 'hook_event_loop'
                ) and event_loop is not None:
            raise NotImplementedError("screen object passed "
                "%r does not support external event loops" % (screen,))
        if event_loop is None:
            event_loop = TrioEventLoop()
        self.event_loop = event_loop

        if hasattr(self.screen, 'signal_handler_setter'):
            # Tell the screen what function it must use to set
            # signal handlers
            self.screen.signal_handler_setter = self.event_loop.set_signal_handler

        self._watch_pipes = {}


    def set_alarm_in(self, sec, callback, user_data=None):
        """
        Schedule an alarm in *sec* seconds that will call *callback* from the
        within the :meth:`run` method.

        :param sec: seconds until alarm
        :type sec: float
        :param callback: function to call with two parameters: this main loop
                         object and *user_data*
        :type callback: callable
        """
        def cb():
            callback(self, user_data)
        return self.event_loop.alarm(sec, cb)

    def set_alarm_at(self, tm, callback, user_data=None):
        """
        Schedule an alarm at *tm* time that will call *callback* from the
        within the :meth:`run` function. Returns a handle that may be passed to
        :meth:`remove_alarm`.

        :param tm: time to call callback e.g. ``time.time() + 5``
        :type tm: float
        :param callback: function to call with two parameters: this main loop
                         object and *user_data*
        :type callback: callable
        """
        def cb():
            callback(self, user_data)
        return self.event_loop.alarm(tm - time.time(), cb)

    def remove_alarm(self, handle):
        """
        Remove an alarm. Return ``True`` if *handle* was found, ``False``
        otherwise.
        """
        return self.event_loop.remove_alarm(handle)

    def watch_pipe(self, callback):
        """
        Create a pipe for use by a subprocess or thread to trigger a callback
        in the process/thread running the main loop.

        :param callback: function taking one parameter to call from within
                         the process/thread running the main loop
        :type callback: callable

        This method returns a file descriptor attached to the write end of a
        pipe. The read end of the pipe is added to the list of files
        :attr:`event_loop` is watching. When data is written to the pipe the
        callback function will be called and passed a single value containing
        data read from the pipe.

        This method may be used any time you want to update widgets from
        another thread or subprocess.

        Data may be written to the returned file descriptor with
        ``os.write(fd, data)``. Ensure that data is less than 512 bytes (or 4K
        on Linux) so that the callback will be triggered just once with the
        complete value of data passed in.

        If the callback returns ``False`` then the watch will be removed from
        :attr:`event_loop` and the read end of the pipe will be closed. You
        are responsible for closing the write end of the pipe with
        ``os.close(fd)``.
        """
        pipe_rd, pipe_wr = os.pipe()
        fcntl.fcntl(pipe_rd, fcntl.F_SETFL, os.O_NONBLOCK)
        watch_handle = None

        def cb():
            data = os.read(pipe_rd, PIPE_BUFFER_READ_SIZE)
            rval = callback(data)
            if rval is False:
                self.event_loop.remove_watch_file(watch_handle)
                os.close(pipe_rd)

        watch_handle = self.event_loop.watch_file(pipe_rd, cb)
        self._watch_pipes[pipe_wr] = (watch_handle, pipe_rd)
        return pipe_wr

    def remove_watch_pipe(self, write_fd):
        """
        Close the read end of the pipe and remove the watch created by
        :meth:`watch_pipe`. You are responsible for closing the write end of
        the pipe.

        Returns ``True`` if the watch pipe exists, ``False`` otherwise
        """
        try:
            watch_handle, pipe_rd = self._watch_pipes.pop(write_fd)
        except KeyError:
            return False

        if not self.event_loop.remove_watch_file(watch_handle):
            return False
        os.close(pipe_rd)
        return True

    def watch_file(self, fd, callback):
        """
        Call *callback* when *fd* has some data to read. No parameters are
        passed to callback.

        Returns a handle that may be passed to :meth:`remove_watch_file`.
        """
        return self.event_loop.watch_file(fd, callback)

    def remove_watch_file(self, handle):
        """
        Remove a watch file. Returns ``True`` if the watch file
        exists, ``False`` otherwise.
        """
        return self.event_loop.remove_watch_file(handle)


    def run(self):
        """
        Start the main loop handling input events and updating the screen. The
        loop will continue until an :exc:`ExitMainLoop` exception is raised.

        If you would prefer to manage the event loop yourself, don't use this
        method.  Instead, call :meth:`start` before starting the event loop,
        and :meth:`stop` once it's finished.
        """
        try:
            self._run()
        except ExitMainLoop:
            pass


    def start(self):
        """
        Sets up the main loop, hooking into the event loop where necessary.
        Starts the :attr:`screen` if it hasn't already been started.

        If you want to control starting and stopping the event loop yourself,
        you should call this method before starting, and call `stop` once the
        loop has finished.  You may also use this method as a context manager,
        which will stop the loop automatically at the end of the block:

            with main_loop.start():
                ...

        Note that some event loop implementations don't handle exceptions
        specially if you manage the event loop yourself.  In particular, the
        Twisted and asyncio loops won't stop automatically when
        :exc:`ExitMainLoop` (or anything else) is raised.
        """
        self.screen.start()

        try:
            signals.connect_signal(self.screen, INPUT_DESCRIPTORS_CHANGED,
                self._reset_input_descriptors)
        except NameError:
            pass
        # watch our input descriptors
        self._reset_input_descriptors()
        self.idle_handle = self.event_loop.enter_idle(self.entering_idle)

        return StoppingContext(self)

    def stop(self):
        """
        Cleans up any hooks added to the event loop.  Only call this if you're
        managing the event loop yourself, after the loop stops.
        """
        self.event_loop.remove_enter_idle(self.idle_handle)
        del self.idle_handle
        signals.disconnect_signal(self.screen, INPUT_DESCRIPTORS_CHANGED,
            self._reset_input_descriptors)
        self.screen.unhook_event_loop(self.event_loop)

        self.screen.stop()

    def _reset_input_descriptors(self):
        self.screen.unhook_event_loop(self.event_loop)
        self.screen.hook_event_loop(self.event_loop, self._update)

    def _run(self):
        self.start()
        try:
            self.event_loop.run()
        except:
            self.screen.stop() # clean up screen control
            raise
        self.stop()

    def _update(self, keys, raw):
        if keys:
            self.process_input(keys)

    def process_input(self, keys):
        """
        This method will pass keyboard input to :attr:`widget`.
        This method is called automatically from the :meth:`run` method when
        there is input, but may also be called to simulate input from the user.

        *keys* is a list of input returned from :attr:`screen`'s get_input()
        or get_input_nonblocking() methods.

        Returns ``True`` if any key was handled by a widget or the
        :meth:`unhandled_input` method.
        """

        something_handled = False

        for k in keys:
            # if k == 'window resize':
            #     continue
            if k:
                # if command_map[k] == REDRAW_SCREEN:
                #     self.screen.clear()
                #     something_handled = True
                # else:
                something_handled |= bool(self.unhandled_input(k))
            else:
                something_handled = True

        return something_handled

    def unhandled_input(self, input):
        """
        This function is called with any input that was not handled by the
        widgets, and calls the *unhandled_input* function passed to the
        constructor. If no *unhandled_input* was defined then the input
        will be ignored.

        *input* is the keyboard input.

        The *unhandled_input* function should return ``True`` if it handled
        the input.
        """
        if self._unhandled_input:
            return self._unhandled_input(input)

    def entering_idle(self):
        """
        This method is called whenever the event loop is about to enter the
        idle state. :meth:`draw_screen` is called here to update the
        screen when anything has changed.
        """
        if self.screen.started:
            self.draw_screen()

    def draw_screen(self):
        """
        Render the widgets and paint the screen. This method is called
        automatically from :meth:`entering_idle`.

        If you modify the widgets displayed outside of handling input or
        responding to an alarm you will need to call this method yourself
        to repaint the screen.
        """
        return


class EventLoop(object):
    """
    Abstract class representing an event loop to be used by :class:`MainLoop`.
    """

    def alarm(self, seconds, callback):
        """
        Call callback() a given time from now.  No parameters are
        passed to callback.

        This method has no default implementation.

        Returns a handle that may be passed to remove_alarm()

        seconds -- floating point time to wait before calling callback
        callback -- function to call from event loop
        """
        raise NotImplementedError()

    def enter_idle(self, callback):
        """
        Add a callback for entering idle.

        This method has no default implementation.

        Returns a handle that may be passed to remove_idle()
        """
        raise NotImplementedError()

    def remove_alarm(self, handle):
        """
        Remove an alarm.

        This method has no default implementation.

        Returns True if the alarm exists, False otherwise
        """
        raise NotImplementedError()

    def remove_enter_idle(self, handle):
        """
        Remove an idle callback.

        This method has no default implementation.

        Returns True if the handle was removed.
        """
        raise NotImplementedError()

    def remove_watch_file(self, handle):
        """
        Remove an input file.

        This method has no default implementation.

        Returns True if the input file exists, False otherwise
        """
        raise NotImplementedError()

    def run(self):
        """
        Start the event loop.  Exit the loop when any callback raises
        an exception.  If ExitMainLoop is raised, exit cleanly.

        This method has no default implementation.
        """
        raise NotImplementedError()

    def watch_file(self, fd, callback):
        """
        Call callback() when fd has some data to read.  No parameters
        are passed to callback.

        This method has no default implementation.

        Returns a handle that may be passed to remove_watch_file()

        fd -- file descriptor to watch for input
        callback -- function to call when input is available
        """
        raise NotImplementedError()

    def set_signal_handler(self, signum, handler):
        """
        Sets the signal handler for signal signum.

        The default implementation of :meth:`set_signal_handler`
        is simply a proxy function that calls :func:`signal.signal()`
        and returns the resulting value.

        signum -- signal number
        handler -- function (taking signum as its single argument),
        or `signal.SIG_IGN`, or `signal.SIG_DFL`
        """
        return signal.signal(signum, handler)




class TrioEventLoop(EventLoop):
    """
    Event loop based on the ``trio`` module.

    ``trio`` is an async library for Python 3.5 and later.
    """

    def __init__(self):
        """Constructor."""
        import trio

        self._idle_handle = 0
        self._idle_callbacks = {}
        self._pending_tasks = []

        self._trio = trio
        self._nursery = None

        self._sleep = trio.sleep
        try:
            self._wait_readable = trio.lowlevel.wait_readable
        except AttributeError:
            # Trio 0.14 or older
            self._wait_readable = trio.hazmat.wait_readable

    def alarm(self, seconds, callback):
        """Calls `callback()` a given time from now.  No parameters are passed
        to the callback.

        Parameters:
            seconds: time in seconds to wait before calling the callback
            callback: function to call from the event loop

        Returns:
            a handle that may be passed to `remove_alarm()`
        """
        return self._start_task(self._alarm_task, seconds, callback)

    def enter_idle(self, callback):
        """Calls `callback()` when the event loop enters the idle state.

        There is no such thing as being idle in a Trio event loop so we
        simulate it by repeatedly calling `callback()` with a short delay.
        """
        self._idle_handle += 1
        self._idle_callbacks[self._idle_handle] = callback
        return self._idle_handle

    def remove_alarm(self, handle):
        """Removes an alarm.

        Parameters:
            handle: the handle of the alarm to remove
        """
        return self._cancel_scope(handle)

    def remove_enter_idle(self, handle):
        """Removes an idle callback.

        Parameters:
            handle: the handle of the idle callback to remove
        """
        try:
            del self._idle_callbacks[handle]
        except KeyError:
            return False
        return True

    def remove_watch_file(self, handle):
        """Removes a file descriptor being watched for input.

        Parameters:
            handle: the handle of the file descriptor callback to remove

        Returns:
            True if the file descriptor was watched, False otherwise
        """
        return self._cancel_scope(handle)

    def _cancel_scope(self, scope):
        """Cancels the given Trio cancellation scope.

        Returns:
            True if the scope was cancelled, False if it was cancelled already
            before invoking this function
        """
        existed = not scope.cancel_called
        scope.cancel()
        return existed

    def run(self):
        """Starts the event loop. Exits the loop when any callback raises an
        exception. If ExitMainLoop is raised, exits cleanly.
        """

        idle_callbacks = self._idle_callbacks

        # This class is duplicated in run_async(). It would be nice to move
        # this somewhere outside, but we cannot do it yet becase we need to
        # derive it from self._trio.abc.Instrument
        class TrioIdleCallbackInstrument(self._trio.abc.Instrument):
            def before_io_wait(self, timeout):
                if timeout > 0:
                    for idle_callback in idle_callbacks.values():
                        idle_callback()

        emulate_idle_callbacks = TrioIdleCallbackInstrument()

        with self._trio.MultiError.catch(self._handle_main_loop_exception):
            self._trio.run(self._main_task, instruments=[emulate_idle_callbacks])

    async def run_async(self):
        """Starts the main loop and blocks asynchronously until the main loop
        exits. This allows one to embed an urwid app in a Trio app even if the
        Trio event loop is already running. Example::

            with trio.open_nursery() as nursery:
                event_loop = urwid.TrioEventLoop()

                # [...launch other async tasks in the nursery...]

                loop = urwid.MainLoop(widget, event_loop=event_loop)
                with loop.start():
                    await event_loop.run_async()

                nursery.cancel_scope.cancel()
        """

        idle_callbacks = self._idle_callbacks

        # This class is duplicated in run_async(). It would be nice to move
        # this somewhere outside, but we cannot do it yet becase we need to
        # derive it from self._trio.abc.Instrument
        class TrioIdleCallbackInstrument(self._trio.abc.Instrument):
            def before_io_wait(self, timeout):
                if timeout > 0:
                    for idle_callback in idle_callbacks.values():
                        idle_callback()

        emulate_idle_callbacks = TrioIdleCallbackInstrument()

        try:
            add_instrument = self._trio.lowlevel.add_instrument
            remove_instrument = self._trio.lowlevel.remove_instrument
        except AttributeError:
            # Trio 0.14 or older
            add_instrument = self._trio.hazmat.add_instrument
            remove_instrument = self._trio.hazmat.remove_instrument

        with self._trio.MultiError.catch(self._handle_main_loop_exception):
            add_instrument(emulate_idle_callbacks)
            try:
                await self._main_task()
            finally:
                remove_instrument(emulate_idle_callbacks)

    def watch_file(self, fd, callback):
        """Calls `callback()` when the given file descriptor has some data
        to read. No parameters are passed to the callback.

        Parameters:
            fd: file descriptor to watch for input
            callback: function to call when some input is available

        Returns:
            a handle that may be passed to `remove_watch_file()`
        """
        return self._start_task(self._watch_task, fd, callback)

    async def _alarm_task(self, scope, seconds, callback):
        """Asynchronous task that sleeps for a given number of seconds and then
        calls the given callback.

        Parameters:
            scope: the cancellation scope that can be used to cancel the task
            seconds: the number of seconds to wait
            callback: the callback to call
        """
        with scope:
            await self._sleep(seconds)
            callback()

    def _handle_main_loop_exception(self, exc):
        """Handles exceptions raised from the main loop, catching ExitMainLoop
        instead of letting it propagate through.

        Note that since Trio may collect multiple exceptions from tasks into a
        Trio MultiError, we cannot simply use a try..catch clause, we need a
        helper function like this.
        """
        self._idle_callbacks.clear()
        if isinstance(exc, ExitMainLoop):
            return None
        else:
            return exc

    async def _main_task(self):
        """Main Trio task that opens a nursery and then sleeps until the user
        exits the app by raising ExitMainLoop.
        """
        try:
            async with self._trio.open_nursery() as self._nursery:
                self._schedule_pending_tasks()
                await self._trio.sleep_forever()
        finally:
            self._nursery = None

    def _schedule_pending_tasks(self):
        """Schedules all pending asynchronous tasks that were created before
        the nursery to be executed on the nursery soon.
        """
        for task, scope, args in self._pending_tasks:
            self._nursery.start_soon(task, scope, *args)
        del self._pending_tasks[:]

    def _start_task(self, task, *args):
        """Starts an asynchronous task in the Trio nursery managed by the
        main loop. If the nursery has not started yet, store a reference to
        the task and the arguments so we can start the task when the nursery
        is open.

        Parameters:
            task: a Trio task to run

        Returns:
            a cancellation scope for the Trio task
        """
        scope = self._trio.CancelScope()
        if self._nursery:
            self._nursery.start_soon(task, scope, *args)
        else:
            self._pending_tasks.append((task, scope, args))
        return scope

    async def _watch_task(self, scope, fd, callback):
        """Asynchronous task that watches the given file descriptor and calls
        the given callback whenever the file descriptor becomes readable.

        Parameters:
            scope: the cancellation scope that can be used to cancel the task
            fd: the file descriptor to watch
            callback: the callback to call
        """
        with scope:
            # We check for the scope being cancelled before calling
            # wait_readable because if callback cancels the scope, fd might be
            # closed and calling wait_readable with a closed fd does not work.
            while not scope.cancel_called:
                await self._wait_readable(fd)
                callback()

 
def _refl(name, rval=None, exit=False):
    """
    This function is used to test the main loop classes.

    >>> scr = _refl("screen")
    >>> scr.function("argument")
    screen.function('argument')
    >>> scr.callme(when="now")
    screen.callme(when='now')
    >>> scr.want_something_rval = 42
    >>> x = scr.want_something()
    screen.want_something()
    >>> x
    42

    """
    class Reflect(object):
        def __init__(self, name, rval=None):
            self._name = name
            self._rval = rval
        def __call__(self, *argl, **argd):
            args = ", ".join([repr(a) for a in argl])
            if args and argd:
                args = args + ", "
            args = args + ", ".join([k+"="+repr(v) for k,v in argd.items()])
            print(self._name+"("+args+")")
            if exit:
                raise ExitMainLoop()
            return self._rval
        def __getattr__(self, attr):
            if attr.endswith("_rval"):
                raise AttributeError()
            #print self._name+"."+attr
            if hasattr(self, attr+"_rval"):
                return Reflect(self._name+"."+attr, getattr(self, attr+"_rval"))
            return Reflect(self._name+"."+attr)
    return Reflect(name)

def _test():
    import doctest
    doctest.testmod()

if __name__=='__main__':
    _test()
