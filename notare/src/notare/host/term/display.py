# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later AND LGPL-2.1-or-later

# Urwid raw display module
#    Copyright (C) 2004-2009  Ian Ward
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

"""
Direct terminal UI implementation
"""

import os
import select
import struct
import sys
import signal
import fcntl
import termios
import tty

from urwid.util import StoppingContext
from urwid import escape
from urwid import signals
from urwid.compat import B, bytes3, xrange, with_metaclass

# for replacing unprintable bytes with '?'
UNPRINTABLE_TRANS_TABLE = B("?") * 32 + bytes3(list(xrange(32,256)))


# signals sent by BaseScreen
INPUT_DESCRIPTORS_CHANGED = "input descriptors changed"



class RealTerminal(object):
    def __init__(self):
        super(RealTerminal,self).__init__()
        self._signal_keys_set = False
        self._old_signal_keys = None

    def tty_signal_keys(self, intr=None, quit=None, start=None,
        stop=None, susp=None, fileno=None):
        """
        Read and/or set the tty's signal character settings.
        This function returns the current settings as a tuple.

        Use the string 'undefined' to unmap keys from their signals.
        The value None is used when no change is being made.
        Setting signal keys is done using the integer ascii
        code for the key, eg.  3 for CTRL+C.

        If this function is called after start() has been called
        then the original settings will be restored when stop()
        is called.
        """
        if fileno is None:
            fileno = sys.stdin.fileno()
        if not os.isatty(fileno):
            return

        tattr = termios.tcgetattr(fileno)
        sattr = tattr[6]
        skeys = (sattr[termios.VINTR], sattr[termios.VQUIT],
            sattr[termios.VSTART], sattr[termios.VSTOP],
            sattr[termios.VSUSP])

        if intr == 'undefined': intr = 0
        if quit == 'undefined': quit = 0
        if start == 'undefined': start = 0
        if stop == 'undefined': stop = 0
        if susp == 'undefined': susp = 0

        if intr is not None: tattr[6][termios.VINTR] = intr
        if quit is not None: tattr[6][termios.VQUIT] = quit
        if start is not None: tattr[6][termios.VSTART] = start
        if stop is not None: tattr[6][termios.VSTOP] = stop
        if susp is not None: tattr[6][termios.VSUSP] = susp

        if intr is not None or quit is not None or \
            start is not None or stop is not None or \
            susp is not None:
            termios.tcsetattr(fileno, termios.TCSADRAIN, tattr)
            self._signal_keys_set = True

        return skeys


class ScreenError(Exception):
    pass

class BaseScreen(with_metaclass(signals.MetaSignals, object)):
    """
    Base class for Screen classes (raw_display.Screen, .. etc)
    """
    signals = [INPUT_DESCRIPTORS_CHANGED]

    def __init__(self):
        super(BaseScreen,self).__init__()
        self._started = False

    started = property(lambda self: self._started)

    def start(self, *args, **kwargs):
        """Set up the screen.  If the screen has already been started, does
        nothing.

        May be used as a context manager, in which case :meth:`stop` will
        automatically be called at the end of the block:

            with screen.start():
                ...

        You shouldn't override this method in a subclass; instead, override
        :meth:`_start`.
        """
        if not self._started:
            self._started = True
            self._start(*args, **kwargs)
        return StoppingContext(self)

    def _start(self):
        pass

    def stop(self):
        if self._started:
            self._stop()
        self._started = False

    def _stop(self):
        pass

class Screen(BaseScreen, RealTerminal):
    def __init__(self, input=sys.stdin, output=sys.stdout):
        """Initialize a screen that directly prints escape codes to an output
        terminal.
        """
        super(Screen, self).__init__()
        self.colors = 16 # FIXME: detect this
        self.has_underline = True # FIXME: detect this
        self._keyqueue = []
        self.prev_input_resize = 0
        self.set_input_timeouts()
        self.screen_buf = None
        self._screen_buf_canvas = None
        self._resized = False
        self.maxrow = None
        self.last_bstate = 0
        self._rows_used = None
        self._cy = 0
        self.term = os.environ.get('TERM', '')
        self._next_timeout = None
        self.signal_handler_setter = signal.signal

        # Our connections to the world
        self._term_output_file = output
        self._term_input_file = input

        # pipe for signalling external event loops about resize events
        # self._resize_pipe_rd, self._resize_pipe_wr = os.pipe()
        # fcntl.fcntl(self._resize_pipe_rd, fcntl.F_SETFL, os.O_NONBLOCK)

    def _input_fileno(self):
        """Returns the fileno of the input stream, or None if it doesn't have one.  A stream without a fileno can't participate in whatever.
        """
        if hasattr(self._term_input_file, 'fileno'):
            return self._term_input_file.fileno()
        else:
            return None

    def set_input_timeouts(self, max_wait=None, complete_wait=0.125,
        resize_wait=0.125):
        """
        Set the get_input timeout values.  All values are in floating
        point numbers of seconds.

        max_wait -- amount of time in seconds to wait for input when
            there is no input pending, wait forever if None
        complete_wait -- amount of time in seconds to wait when
            get_input detects an incomplete escape sequence at the
            end of the available input
        resize_wait -- amount of time in seconds to wait for more input
            after receiving two screen resize requests in a row to
            stop Urwid from consuming 100% cpu during a gradual
            window resize operation
        """
        self.max_wait = max_wait
        if max_wait is not None:
            if self._next_timeout is None:
                self._next_timeout = max_wait
            else:
                self._next_timeout = min(self._next_timeout, self.max_wait)
        self.complete_wait = complete_wait
        self.resize_wait = resize_wait

    def _sigwinch_handler(self, signum, frame=None):
        """
        frame -- will always be None when the GLib event loop is being used.
        """
        return
        if not self._resized:
            os.write(self._resize_pipe_wr, B('R'))
        self._resized = True
        self.screen_buf = None

    def _sigcont_handler(self, signum, frame=None):
        """
        frame -- will always be None when the GLib event loop is being used.
        """

        self.stop()
        self.start()
        # self._sigwinch_handler(None, None)

    def signal_init(self):
        """
        Called in the startup of run wrapper to set the SIGWINCH
        and SIGCONT signal handlers.

        Override this function to call from main thread in threaded
        applications.
        """
        # self.signal_handler_setter(signal.SIGWINCH, self._sigwinch_handler)
        self.signal_handler_setter(signal.SIGCONT, self._sigcont_handler)

    def signal_restore(self):
        """
        Called in the finally block of run wrapper to restore the
        SIGWINCH and SIGCONT signal handlers.

        Override this function to call from main thread in threaded
        applications.
        """
        self.signal_handler_setter(signal.SIGCONT, signal.SIG_DFL)
        # self.signal_handler_setter(signal.SIGWINCH, signal.SIG_DFL)

    def set_mouse_tracking(self, enable=True):
        """
        Enable (or disable) mouse tracking.

        After calling this function get_input will include mouse
        click events along with keystrokes.
        """
        raise Exception("nope")

    def _mouse_tracking(self, enable):
        raise Exception("nope")


    def _start(self, alternate_buffer=True):
        """
        Initialize the screen and input mode.

        alternate_buffer -- use alternate screen buffer
        """
        self._rows_used = 0

        fd = self._input_fileno()
        if fd is not None and os.isatty(fd):
            self._old_termios_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)

        self.signal_init()
        self._next_timeout = self.max_wait

        if not self._signal_keys_set:
            self._old_signal_keys = self.tty_signal_keys(fileno=fd)

        signals.emit_signal(self, INPUT_DESCRIPTORS_CHANGED)

        return super(Screen, self)._start()

    def _stop(self):
        """
        Restore the screen.
        """
        self.clear()

        signals.emit_signal(self, INPUT_DESCRIPTORS_CHANGED)

        self.signal_restore()

        fd = self._input_fileno()
        if fd is not None and os.isatty(fd):
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_termios_settings)

        if self._old_signal_keys:
            self.tty_signal_keys(*(self._old_signal_keys + (fd,)))

        super(Screen, self)._stop()


    def write(self, data):
        """Write some data to the terminal.

        You may wish to override this if you're using something other than
        regular files for input and output.
        """
        self._term_output_file.write(data)

    def flush(self):
        """Flush the output buffer.

        You may wish to override this if you're using something other than
        regular files for input and output.
        """
        self._term_output_file.flush()

    def get_input(self, raw_keys=False):
        """Return pending input as a list.

        raw_keys -- return raw keycodes as well as translated versions

        This function will immediately return all the input since the
        last time it was called.  If there is no input pending it will
        wait before returning an empty list.  The wait time may be
        configured with the set_input_timeouts function.

        If raw_keys is False (default) this function will return a list
        of keys pressed.  If raw_keys is True this function will return
        a ( keys pressed, raw keycodes ) tuple instead.

        Examples of keys returned:

        * ASCII printable characters:  " ", "a", "0", "A", "-", "/"
        * ASCII control characters:  "tab", "enter"
        * Escape sequences:  "up", "page up", "home", "insert", "f1"
        * Key combinations:  "shift f1", "meta a", "ctrl b"

        When a narrow encoding is not enabled:

        * "Extended ASCII" characters:  "\\xa1", "\\xb2", "\\xfe"

        When a wide encoding is enabled:

        * Double-byte characters:  "\\xa1\\xea", "\\xb2\\xd4"

        When utf8 encoding is enabled:

        * Unicode characters: u"\\u00a5", u'\\u253c"
        """
        assert self._started

        self._wait_for_input_ready(self._next_timeout)
        keys, raw = self.parse_input(None, None, self.get_available_raw_input())

        # Avoid pegging CPU at 100% when slowly resizing
        # if keys==['window resize'] and self.prev_input_resize:
        #     while True:
        #         self._wait_for_input_ready(self.resize_wait)
        #         keys, raw2 = self.parse_input(None, None, self.get_available_raw_input())
        #         raw += raw2
        #         #if not keys:
        #         #    keys, raw2 = self._get_input(
        #         #        self.resize_wait)
        #         #    raw += raw2
        #         if keys!=['window resize']:
        #             break
        #     if keys[-1:]!=['window resize']:
        #         keys.append('window resize')

        # if keys==['window resize']:
        #     self.prev_input_resize = 2
        # elif self.prev_input_resize == 2 and not keys:
        #     self.prev_input_resize = 1
        # else:
        #     self.prev_input_resize = 0

        if raw_keys:
            return keys, raw
        return keys

    def get_input_descriptors(self):
        """
        Return a list of integer file descriptors that should be
        polled in external event loops to check for user input.

        Use this method if you are implementing your own event loop.

        This method is only called by `hook_event_loop`, so if you override
        that, you can safely ignore this.
        """
        if not self._started:
            return []

        # fd_list = [self._resize_pipe_rd]
        fd_list = []
        fd = self._input_fileno()
        if fd is not None:
            fd_list.append(fd)
        return fd_list

    _current_event_loop_handles = ()

    def unhook_event_loop(self, event_loop):
        """
        Remove any hooks added by hook_event_loop.
        """
        for handle in self._current_event_loop_handles:
            event_loop.remove_watch_file(handle)

        if self._input_timeout:
            event_loop.remove_alarm(self._input_timeout)
            self._input_timeout = None

    def hook_event_loop(self, event_loop, callback):
        """
        Register the given callback with the event loop, to be called with new
        input whenever it's available.  The callback should be passed a list of
        processed keys and a list of unprocessed keycodes.

        Subclasses may wish to use parse_input to wrap the callback.
        """
        wrapper = lambda: self.parse_input(event_loop, callback, self.get_available_raw_input())
        fds = self.get_input_descriptors()
        handles = [event_loop.watch_file(fd, wrapper) for fd in fds]
        self._current_event_loop_handles = handles

    _input_timeout = None
    _partial_codes = None



    def get_available_raw_input(self):
        """
        Return any currently-available input.  Does not block.

        This method is only used by the default `hook_event_loop`
        implementation; you can safely ignore it if you implement your own.
        """
        codes = self._get_keyboard_codes()

        if self._partial_codes:
            codes = self._partial_codes + codes
            self._partial_codes = None

        # clean out the pipe used to signal external event loops
        # that a resize has occurred
        # try:
        #     while True: os.read(self._resize_pipe_rd, 1)
        # except OSError:
        #     pass

        return codes

    def parse_input(self, event_loop, callback, codes, wait_for_more=True):
        """
        Read any available input from get_available_raw_input, parses it into
        keys, and calls the given callback.

        The current implementation tries to avoid any assumptions about what
        the screen or event loop look like; it only deals with parsing keycodes
        and setting a timeout when an incomplete one is detected.

        `codes` should be a sequence of keycodes, i.e. bytes.  A bytearray is
        appropriate, but beware of using bytes, which only iterates as integers
        on Python 3.
        """
        # Note: event_loop may be None for 100% synchronous support, only used
        # by get_input.  Not documented because you shouldn't be doing it.
        if self._input_timeout and event_loop:
            event_loop.remove_alarm(self._input_timeout)
            self._input_timeout = None

        original_codes = codes
        processed = []
        try:
            while codes:
                run, codes = escape.process_keyqueue(
                    codes, wait_for_more)
                processed.extend(run)
        except escape.MoreInputRequired:
            # Set a timer to wait for the rest of the input; if it goes off
            # without any new input having come in, use the partial input
            k = len(original_codes) - len(codes)
            processed_codes = original_codes[:k]
            self._partial_codes = codes

            def _parse_incomplete_input():
                self._input_timeout = None
                self._partial_codes = None
                self.parse_input(
                    event_loop, callback, codes, wait_for_more=False)
            if event_loop:
                self._input_timeout = event_loop.alarm(
                    self.complete_wait, _parse_incomplete_input)

        else:
            processed_codes = original_codes
            self._partial_codes = None

        # if self._resized:
        #     processed.append('window resize')
        #     self._resized = False

        if callback:
            callback(processed, processed_codes)
        else:
            # For get_input
            return processed, processed_codes

    def _get_keyboard_codes(self):
        codes = []
        while True:
            code = self._getch_nodelay()
            if code < 0:
                break
            codes.append(code)
        return codes

    def _wait_for_input_ready(self, timeout):
        ready = None
        fd_list = []
        fd = self._input_fileno()
        if fd is not None:
            fd_list.append(fd)
        while True:
            try:
                if timeout is None:
                    ready,w,err = select.select(
                        fd_list, [], fd_list)
                else:
                    ready,w,err = select.select(
                        fd_list,[],fd_list, timeout)
                break
            except select.error as e:
                if e.args[0] != 4:
                    raise
                # if self._resized:
                #     ready = []
                #     break
        return ready

    def _getch(self, timeout):
        ready = self._wait_for_input_ready(timeout)
        fd = self._input_fileno()
        if fd is not None and fd in ready:
            return ord(os.read(fd, 1))
        return -1

    def _getch_nodelay(self):
        return self._getch(0)

    def get_cols_rows(self):
        """Return the terminal dimensions (num columns, num rows)."""
        y, x = 24, 80
        try:
            if hasattr(self._term_output_file, 'fileno'):
                buf = fcntl.ioctl(self._term_output_file.fileno(),
                                termios.TIOCGWINSZ, ' '*4)
                y, x = struct.unpack('hh', buf)
        except IOError:
            # Term size could not be determined
            pass
        self.maxrow = y
        return x, y

    def draw_screen(self, maxres, r ):
        """Paint screen with rendered canvas."""
        return


    def clear(self):
        """
        Force the screen to be completely repainted on the next
        call to draw_screen().
        """
        self.screen_buf = None

