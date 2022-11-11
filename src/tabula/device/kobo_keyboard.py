# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import collections.abc
from contextlib import contextmanager
import fcntl
import os
import pathlib
import typing

import attr
import libevdev
import trio
import trio_util

from .keyboard_consts import Key, KeyPress
from .types import (
    InputDevice,
    InputDeviceNotFound,
    ScreenInfo,
    ScreenRect,
    KeyEvent,
    TouchEvent,
)

# Evdev keyboard class should represent the concept of an evdev keyboard, not a specific
# input path. Same class can handle enumerating keyboards and delivering input from chosen
# keyboard. This means that the app object can take an instance and not just the class.


# from trio_util import AsyncValue

# OSError: [Errno 19] No such device when keyboard gets unplugged, pretty much immediately
# Traceback (most recent call last):
#   File "<stdin>", line 2, in <module>
#   File "/usr/lib/python3.9/site-packages/libevdev/device.py", line 536, in events
#     ev = self._libevdev.next_event(flags)
#   File "/usr/lib/python3.9/site-packages/libevdev/_clib.py", line 893, in next_event
#     raise OSError(-rc, os.strerror(-rc))
# OSError: [Errno 19] No such device


# Mostly we care about EV_KEY. These events have a value of 1 for keydown and 0 for
# keyup, and 2 for autorepeat (key held down).
# LEDs are controlled with EV_LED, autorepeat is controlled with EV_REP (depending on
# keyboard driver), and raw scancodes can be gotten off EV_MSC.MSC_SCAN.
# EV_SYN is synchronization, but we can ignore that for now, I think.

# stage 0: OS-specific; watch keyboard device and issue keystream, or issue pre-recorded keystream on Mac
# stage 1: track modifier keydown/up and annotate keystream with current modifiers
# stage 2: convert key event + modifier into character or special key code
# stage 3: compose sequences

# device class instantiated with vendor/product/interface, finds its input path, opens it and yields keys
# provides asyncbool properties: keyboard presence, compose sequence
# if the fd goes away because keyboard unplugged, set keyboard asyncbool to false, check every 0.2 secs for it to come back.
# when it comes back, set keyboard asyncbool to true, reopen, proceed.

# hardware buttons are 0, touchscreen is 1
MIN_USB_INPUT = 2


def parse_eventnum(name):
    if not name.startswith("event"):
        return -1
    numstr = name[5:]
    try:
        return int(numstr)
    except ValueError:
        return -1


@contextmanager
def open_device(devpath):
    f = open(devpath, "r+b", buffering=0)
    fcntl.fcntl(f, fcntl.F_SETFL, os.O_NONBLOCK)
    d = libevdev.Device(f)
    d.grab()
    try:
        yield d
    finally:
        f.close()


def identify_inputs():
    found = []
    for input_symlink in pathlib.Path("/sys/class/input").iterdir():
        if parse_eventnum(inputname := input_symlink.name) < MIN_USB_INPUT:
            continue
        inputpath = pathlib.Path("/dev/input") / inputname
        # check if inputpath can actually produce keyboard events
        with open_device(inputpath) as d:
            if not d.has(libevdev.EV_KEY.KEY_Q):
                continue
        resolved = input_symlink.resolve()
        # this actually seems to be the least convoluted way to go about this…
        interface = resolved.parent.parent.parent.parent
        interface_id = (interface / "bInterfaceNumber").read_text("ascii").strip()
        device = interface.parent
        vendor_id = (device / "idVendor").read_text("ascii").strip()
        product_id = (device / "idProduct").read_text("ascii").strip()
        manufacturer = (device / "manufacturer").read_text("utf8").strip()
        product = (device / "product").read_text("utf8").strip()
        found.append(
            InputDevice(
                inputpath=inputpath,
                interface_id=interface_id,
                vendor_id=vendor_id,
                product_id=product_id,
                manufacturer=manufacturer,
                product=product,
            )
        )
    return found


def _contains_input_device_predicate(devicespec):
    def predicate(current_inputs):
        for device in current_inputs:
            if device == devicespec:
                return True
        return False

    return predicate


class EventKeyboard:
    def __init__(self):
        self.keyqueue = collections.deque(maxlen=50)
        self.present_devices = trio_util.AsyncValue(value=[])
        self.devicespec = trio_util.AsyncValue(value=None)
        self.connected = trio_util.AsyncBool(value=False)

    def _update_available_inputs(self):
        old_inputs = self.present_devices.value
        current_inputs = identify_inputs()
        devicespec = self.devicespec.value
        if devicespec is not None:
            for device in current_inputs:
                if device == devicespec:
                    # ensures we have the inputpath populated
                    self.devicespec.value = device

            self.connected.value = self.devicespec.value in current_inputs
        if old_inputs != current_inputs:
            self.present_devices.value = current_inputs

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        self._update_available_inputs()
        task_status.started()
        while True:
            devicespec = self.devicespec.value
            if self.connected.value:
                await self._read_events(devicespec.inputpath)
            elif devicespec is not None:
                # if devicespec has a value, but connected is false: keep checking available inputs
                # and waiting for the device to appear in present_devices
                self._update_available_inputs()
                wait_predicate = _contains_input_device_predicate(devicespec)
                with trio.move_on_after(0.2):
                    await self.present_devices.wait_value(wait_predicate)
            else:
                # if devicespec has no value: keep checking available inputs
                # and waiting for devicespec to have a value
                self._update_available_inputs()
                with trio.move_on_after(0.2):
                    await self.devicespec.await_transition()

    async def _read_events(self, eventpath):
        with open_device(eventpath) as d:
            while True:
                try:
                    for e in d.events():
                        await trio.sleep(0)
                        if e.matches(libevdev.EV_KEY):
                            ke = KeyEvent(
                                key=Key(e.code.value), press=KeyPress(e.value)
                            )
                            self.keyqueue.append(ke)
                    await trio.sleep(1 / 60)
                except OSError as e:
                    if e.errno == 19:
                        # device has gone away
                        self.connected.value = False
                        return
                    # some other kind of error, let it rise
                    raise

    async def keystream(self, devicespec):
        if devicespec != self.devicespec.value:
            self.keyqueue.clear()
            self.devicespec.value = devicespec
        while True:
            try:
                yield self.keyqueue.popleft()
                await trio.sleep(0)
            except IndexError:
                # No key events, sleep a bit longer.
                await trio.sleep(1 / 60)


def _print_event(e):
    print("Event: time {}.{:06d}, ".format(e.sec, e.usec), end="")
    if e.matches(libevdev.EV_SYN):
        if e.matches(libevdev.EV_SYN.SYN_MT_REPORT):
            print("++++++++++++++ {} ++++++++++++".format(e.code.name))
        elif e.matches(libevdev.EV_SYN.SYN_DROPPED):
            print(">>>>>>>>>>>>>> {} >>>>>>>>>>>>".format(e.code.name))
        else:
            print("-------------- {} ------------".format(e.code.name))
    else:
        print(
            "type {:02x} {} code {:03x} {:20s} value {:4d}".format(
                e.type.value, e.type.name, e.code.value, e.code.name, e.value
            )
        )


async def _devicewatch(eventpath, *, task_status=trio.TASK_STATUS_IGNORED):
    with open_device(eventpath) as d:
        task_status.started()
        print("It's time")
        while True:
            await trio.sleep(0)
            for e in d.events():
                await trio.sleep(0)
                _print_event(e)
