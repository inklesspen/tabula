# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later AND LGPL-2.1-or-later

# The code in this file is derived from Urwid, a windowing library for Python.
# Urwid's copyright and license is as follows:
#    Copyright (C) 2004-2011  Ian Ward
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
from __future__ import annotations

import contextlib
import sys
import termios
import tty
import typing

import trio
import trio.lowlevel
from urwid import escape


class AsyncScreen(contextlib.AbstractAsyncContextManager):
    _escape_complete_wait: float

    def __init__(self):
        sync_stream = sys.stdin

        if not hasattr(sync_stream, "fileno"):
            raise TypeError("input stream must have a fd")
        self._fd = sync_stream.fileno()
        self._stream = None
        self.set_escape_complete_wait()

    def set_escape_complete_wait(self, escape_complete_wait=0.125):
        self._escape_complete_wait = escape_complete_wait

    def _start(self):
        self._old_termios_settings = termios.tcgetattr(self._fd)
        # set up terminal mode for our input handling
        mode = termios.tcgetattr(self._fd)
        # turn off XON/XOFF flow control
        mode[tty.IFLAG] = mode[tty.IFLAG] & ~(termios.IXON)
        # turn off echoing, canonical mode, signal characters, and extended characters
        mode[tty.LFLAG] = mode[tty.LFLAG] & ~(
            termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG
        )
        # read at least 0 bytes, return immediately
        mode[tty.CC][termios.VMIN] = 0
        mode[tty.CC][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSAFLUSH, mode)

    def _stop(self):
        if self._old_termios_settings is not None:
            oldmode = self._old_termios_settings
            self._old_termios_settings = None
            termios.tcsetattr(self._fd, termios.TCSAFLUSH, oldmode)

    async def __aenter__(self) -> AsyncScreen:
        self._start()
        self._stream = trio.lowlevel.FdStream(self._fd)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # we must restore the terminal settings _before_ closing the stream
        self._stop()
        stream = self._stream
        self._stream = None
        await stream.aclose()
        return None

    @property
    def stream(self) -> trio.lowlevel.FdStream:
        if self._stream is None:
            raise ValueError("no stream")
        return self._stream

    async def receive_some(self) -> typing.Tuple[str]:
        """
        Wait for any available input, parse it into keys, and return it.
        When possible, tries to complete processing an escape sequence rather than returning
        a partial escape, by waiting up to self._escape_complete_wait (default 1/8 second)
        """
        codes = []
        result = []
        deadline_set = False
        with trio.CancelScope() as wait_scope:
            while True:
                some = await self.stream.receive_some(1)
                if len(some) == 0:
                    continue
                codes.append(ord(some))
                try:
                    processed, remaining_codes = escape.process_keyqueue(codes, True)
                    result.extend(processed)
                    codes[:] = remaining_codes
                except escape.MoreInputRequired:
                    if not deadline_set:
                        wait_scope.deadline = (
                            trio.current_time() + self._escape_complete_wait
                        )
                        deadline_set = True
                    continue
                else:
                    break
        if wait_scope.cancelled_caught and len(codes) > 0:
            # timed out waiting for the escape to be completed
            processed, _ = escape.process_keyqueue(codes, False)
            result.extend(processed)
        return tuple(result)


async def input_loop(send_channel: trio.MemorySendChannel):
    screen: AsyncScreen
    async with AsyncScreen() as screen:
        while True:
            keys = await screen.receive_some()
            for key in keys:
                await send_channel.send(key)
