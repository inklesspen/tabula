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

import signal

import trio
from urwid.util import StoppingContext


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

    def __init__(self, screen=None, unhandled_input=None):

        self.screen = screen

        self._unhandled_input = unhandled_input

        self.event_loop = TrioEventLoop()

        if hasattr(self.screen, "signal_handler_setter"):
            # Tell the screen what function it must use to set
            # signal handlers
            self.screen.signal_handler_setter = self.event_loop.set_signal_handler

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

        # watch our input descriptors
        self.screen.hook_event_loop(self.event_loop, self._update)

        return StoppingContext(self)

    def stop(self):
        """
        Cleans up any hooks added to the event loop.  Only call this if you're
        managing the event loop yourself, after the loop stops.
        """
        self.screen.unhook_event_loop(self.event_loop)

        self.screen.stop()

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

    async def run_async(self):
        await self.event_loop.run_async()


class TrioEventLoop:
    """
    Event loop based on the ``trio`` module.

    ``trio`` is an async library for Python 3.5 and later.
    """

    def __init__(self):
        self._pending_tasks = []
        self._nursery = None

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

    def remove_alarm(self, handle):
        """Removes an alarm.

        Parameters:
            handle: the handle of the alarm to remove
        """
        return self._cancel_scope(handle)

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

        try:
            async with trio.open_nursery() as self._nursery:
                self._schedule_pending_tasks()
                await trio.sleep_forever()
        finally:
            self._nursery = None

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

    async def _alarm_task(self, scope, seconds, callback):
        """Asynchronous task that sleeps for a given number of seconds and then
        calls the given callback.

        Parameters:
            scope: the cancellation scope that can be used to cancel the task
            seconds: the number of seconds to wait
            callback: the callback to call
        """
        with scope:
            await trio.sleep(seconds)
            callback()

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
        scope = trio.CancelScope()
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
                await trio.lowlevel.wait_readable(fd)
                callback()
