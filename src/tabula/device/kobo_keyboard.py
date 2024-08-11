from __future__ import annotations

import errno
import itertools
import logging
import pathlib

import libevdev
import trio

from .deviceutil import EventDevice
from .eventsource import EventType, KeyCode
from .hwtypes import KeyboardDisconnect, KeyEvent, KeyPress, SetLed

# Evdev keyboard class should represent the concept of an evdev keyboard, not a specific
# input path. Same class can handle enumerating keyboards and delivering input from chosen
# keyboard. This means that the app object can take an instance and not just the class.


# hardware buttons are 0, touchscreen is 1 (on clara hd; it seems a bit different on clara 2e, so make this hardware-specific)
MIN_USB_INPUT = 2

logger = logging.getLogger(__name__)


def parse_eventnum(name):
    if not name.startswith("event"):
        return -1
    numstr = name[5:]
    try:
        return int(numstr)
    except ValueError:
        return -1


def identify_inputs() -> list[pathlib.Path]:
    found = []
    for inputpath in pathlib.Path("/dev/input").glob("event*"):
        if not inputpath.is_char_device():
            continue
        # check if inputpath can actually produce keyboard events
        try:
            with EventDevice(inputpath) as d:
                if not d.has_code(EventType.EV_KEY, KeyCode.KEY_Q):
                    continue
            found.append(inputpath)
        except OSError as exc:
            if exc.errno == errno.ENODEV:
                # device went away while we were trying to open it. ignore.
                logger.debug("Device went away while trying to check it", exc_info=True)
                continue
            raise
        except libevdev.device.DeviceGrabError:
            continue
    return found


class DeviceListener:
    def __init__(
        self,
        devicepath: pathlib.Path,
    ):
        self.device = EventDevice(devicepath)
        self.cancelscope = trio.CancelScope()
        self._device_send_channel, self.device_recv_channel = trio.open_memory_channel[KeyEvent](0)

    def set_led_state(self, state: SetLed):
        # https://python-libevdev.readthedocs.io/en/latest/libevdev.html#libevdev.device.Device.set_leds
        # We'll have to use the actual enums from libevdev, not our own.
        # libevdev.evbit('EV_LED', led)
        # libevdev.evbit('EV_LED', Led.LED_CAPSL)
        logger.info("Would set %r to %r", state.led, state.state)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with self.cancelscope, self.device:
            logger.debug("Getting events for %r", self.device.device_path)
            task_status.started()
            while True:
                try:
                    for evt in self.device.events():
                        await trio.lowlevel.checkpoint()
                        if evt.type is EventType.EV_KEY:
                            ke = KeyEvent(key=evt.code, press=KeyPress(evt.value))
                            await self._device_send_channel.send(ke)
                    await trio.sleep(1 / 60)
                except OSError as exc:
                    if exc.errno == errno.ENODEV:
                        # device has gone away
                        self._device_send_channel.close()
                        return
                    # some other kind of error, let it rise
                    raise


class LibevdevKeyboard:
    present_devices: list[pathlib.Path]
    device_listeners: dict[int, DeviceListener]
    active_listener: DeviceListener | None

    def __init__(self, hardware_send_channel: trio.MemorySendChannel, keyboard_send_channel: trio.MemorySendChannel):
        self.disconnected_send_channel = hardware_send_channel
        self.keyboard_send_channel = keyboard_send_channel
        self.present_devices = []
        self.device_counter = itertools.count()
        self.device_listeners = {}
        self.active_listener = None

    def _update_available_inputs(self):
        old_inputs = self.present_devices
        current_inputs = identify_inputs()
        if old_inputs != current_inputs:
            self.present_devices = current_inputs

    def cancel_listeners(self, except_for: int | None = None):
        for device_id, listener in self.device_listeners.items():
            if device_id == except_for:
                continue
            listener.cancelscope.cancel()

    async def wait_for_keys(self, *, task_status=trio.TASK_STATUS_IGNORED):
        # This doesn't currently handle the state where a new keyboard is connected while we're already in the stage1 loop.
        task_status.started()
        # stage 1: real keyboard unidentified, check if any of them are sending keys
        active_device_id = None
        while active_device_id is None:
            for device_id, listener in self.device_listeners.items():
                try:
                    event = listener.device_recv_channel.receive_nowait()
                except trio.WouldBlock:
                    continue
                except trio.EndOfChannel:
                    # the device has gone away, which means available devices have changed.
                    self.cancel_listeners()
                    return
                active_device_id = device_id
                await self.keyboard_send_channel.send(event)
            if active_device_id is None:
                await trio.sleep(0.1)
        # now we have a device, so kill everything that's not it
        self.cancel_listeners(except_for=active_device_id)
        # stage 2: copy keys from selected device into output
        self.active_listener = self.device_listeners[active_device_id]
        async for event in self.active_listener.device_recv_channel:
            await self.keyboard_send_channel.send(event)
        # stage 3: selected device has gone away, so move on
        self.active_listener = None
        await self.disconnected_send_channel.send(KeyboardDisconnect())

    async def run(self, nursery: trio.Nursery, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()

        while True:
            logger.debug("Checking for keyboards")
            self._update_available_inputs()
            if self.present_devices:
                self.device_listeners = {}
                for devicepath in self.present_devices:
                    logger.debug("Listening to %r", devicepath)
                    device_id = next(self.device_counter)
                    listener = DeviceListener(devicepath)
                    self.device_listeners[device_id] = listener
                    nursery.start_soon(listener.run)
                await self.wait_for_keys()
            else:
                await trio.sleep(0.2)

    def set_led_state(self, state: SetLed):
        if self.active_listener is not None:
            self.active_listener.set_led_state(state)
