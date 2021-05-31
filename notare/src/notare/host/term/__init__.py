# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later AND LGPL-2.1-or-later

# The code in this directory is derived from Urwid, a windowing library for Python.
# Urwid's license is as follows:
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
import datetime
import typing

import trio

from .main_loop import MainLoop, ExitMainLoop

StopKeys = typing.Tuple[str, ...]

def make_key_handler(stopkeys: StopKeys, send_channel: trio.MemorySendChannel, nursery: trio.Nursery):
    def handler(key):
        if key in stopkeys:
            raise ExitMainLoop()
        # get back in that async world
        nursery.start_soon(send_channel.send, key)
    return handler


async def input_loop(stopkeys: StopKeys, now: datetime.datetime, send_channel: trio.MemorySendChannel, nursery: trio.Nursery):
    loop = MainLoop(unhandled_input=make_key_handler(stopkeys, send_channel, nursery))
    with loop.start():
        print("It's Tabula time!")
        print("(Tabula time is {}.)".format(now))
        await loop.event_loop.run_async()
    # the cancel_scope call unglamorously tears everything down. we can do better
    await send_channel.send('shutdown')
    # nursery.cancel_scope.cancel()
