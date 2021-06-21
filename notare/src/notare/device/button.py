# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import fcntl
import os

import libevdev
import trio
from trio_util import AsyncBool


def open_device():
    f = open("/dev/input/event0", "rb")
    fcntl.fcntl(f, fcntl.F_SETFL, os.O_NONBLOCK)
    d = libevdev.Device(f)
    return d


async def _devicewatch(buttonstate: AsyncBool, *, task_status=trio.TASK_STATUS_IGNORED):
    d = open_device()
    task_status.started()
    while True:
        await trio.sleep(0)
        for e in d.events():
            await trio.sleep(0)
            if e.matches(libevdev.EV_KEY.KEY_POWER):
                buttonstate.value = bool(e.value)


async def _boolwatch(
    buttonstate: AsyncBool, trigger, *, task_status=trio.TASK_STATUS_IGNORED
):
    task_status.started()
    while True:
        await buttonstate.wait_value(True, held_for=1)
        trigger()


async def buttonwatch(trigger):
    async with trio.open_nursery() as nursery:
        buttonstate = AsyncBool()
        await nursery.start(_boolwatch, buttonstate, trigger)
        await _devicewatch(buttonstate)
