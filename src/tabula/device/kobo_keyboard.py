from __future__ import annotations

import contextlib
import errno
import logging
import pathlib
import typing

import msgspec
import trio
from trio_util import AsyncValue

from .deviceutil import DeviceGrabError, EventDevice
from .eventsource import EventType, KeyCode
from .hwtypes import DeviceBus, InputDeviceDetails, KeyboardDisconnect, KeyEvent, KeyPress, SetLed
from .proc_bus_input_devices_parser import DEVICES_PATH, parse_devices

logger = logging.getLogger(__name__)


def parse_eventnum(name):
    if not name.startswith("event"):
        return -1
    numstr = name[5:]
    try:
        return int(numstr)
    except ValueError:
        return -1


class EventDeviceDetails(msgspec.Struct, frozen=True, kw_only=True):
    name: str
    bus: DeviceBus
    identifier: str
    inputpaths: list[pathlib.Path]


def identify_inputs(min_input: int) -> tuple[EventDeviceDetails, ...]:
    found = []
    for inputpath in pathlib.Path("/dev/input").glob("event*"):
        eventnum = parse_eventnum(inputpath.name)
        if not eventnum >= min_input:
            continue
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
        except DeviceGrabError:
            continue
    if found:
        devices = parse_devices(DEVICES_PATH.open("r"))
        device_dict = {d["dev_path"]: d for d in devices}
        all_device_details = {}
        for inputpath in found:
            if inputpath not in device_dict:
                continue
            device_details = device_dict[inputpath]
            if device_details["identifier"] in all_device_details:
                all_device_details[device_details["identifier"]].inputpaths.append(inputpath)
            else:
                all_device_details[device_details["identifier"]] = EventDeviceDetails(
                    name=device_details["name"],
                    bus=DeviceBus.BLUETOOTH if device_details["bluetooth_mac"] is not None else DeviceBus.USB,
                    identifier=device_details["identifier"],
                    inputpaths=[inputpath],
                )
        return tuple(all_device_details.values())
    return found


class DeviceListener:
    def __init__(
        self,
        devicepath: pathlib.Path,
    ):
        self.devicepath = devicepath
        self.device = EventDevice(devicepath)
        self._device_send_channel, self.device_recv_channel = trio.open_memory_channel[EventDevice](0)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with contextlib.ExitStack() as stack:
            stack.enter_context(self.device)
            logger.debug("Getting events for %r to see if it's the user's keyboard", self.devicepath)
            task_status.started()
            while True:
                try:
                    for evt in self.device.events():
                        if evt.type is EventType.EV_KEY:
                            stack.pop_all()
                            await self._device_send_channel.send(self.device)
                            return
                    await trio.sleep(1 / 60)
                except OSError as exc:
                    if exc.errno == errno.ENODEV:
                        # device has gone away
                        logger.debug("Device went away")
                        return
                    # some other kind of error, let it rise
                    raise


class MaybeKeyboardListener:
    def __init__(self, device_details: EventDeviceDetails):
        self.device_details = device_details
        self._device_send_channel, self.device_recv_channel = trio.open_memory_channel[tuple[EventDeviceDetails, EventDevice]](0)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        logger.debug("Waiting for keystrokes from %r", self.device_details)
        task_status.started()
        async with trio.open_nursery() as nursery:
            listeners: list[DeviceListener] = []
            for inputpath in self.device_details.inputpaths:
                listener = DeviceListener(inputpath)
                listeners.append(listener)
                await nursery.start(listener.run)
            while True:
                for listener in listeners:
                    try:
                        successful_device = listener.device_recv_channel.receive_nowait()
                    except trio.WouldBlock:
                        continue
                    else:
                        logger.debug("Got key from %r", self.device_details)
                        await self._device_send_channel.send((self.device_details, successful_device))
                        nursery.cancel_scope.cancel()
                        return
                await trio.sleep(0.1)


class InputDeviceScanner:
    _found: AsyncValue[tuple[EventDeviceDetails, ...]]
    _listeners: dict[str, MaybeKeyboardListener]

    def __init__(self, min_input: int):
        self.min_input = min_input
        self._found = AsyncValue(())
        self._listeners = {}

    async def keep_checking(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            val = identify_inputs(self.min_input)
            self._found.value = val
            await trio.sleep(1)

    async def update_listeners(self, nursery: trio.Nursery, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        async for devices_found in self._found.eventual_values():
            current_ids = set(self._listeners.keys())
            seen_ids = set()
            for device_details in devices_found:
                seen_ids.add(device_details.identifier)
                if device_details.identifier not in self._listeners:
                    logger.debug("Starting listener for %r", device_details.identifier)
                    listener = MaybeKeyboardListener(device_details)
                    await nursery.start(listener.run)
                    self._listeners[device_details.identifier] = listener
            missing_ids = current_ids - seen_ids
            for identifier in missing_ids:
                del self._listeners[identifier]

    async def process(self):
        while True:
            for listener in self._listeners.values():
                try:
                    return listener.device_recv_channel.receive_nowait()
                except trio.WouldBlock:
                    continue
            await trio.sleep(0.001)

    async def scan(self):
        async with trio.open_nursery() as nursery:
            await nursery.start(self.keep_checking)
            await nursery.start(self.update_listeners, nursery)
            device_details, device = await self.process()
            nursery.cancel_scope.cancel()
        logger.debug("Scan completed: %r", device_details)
        return device_details, device


class KeyboardListener:
    def __init__(
        self,
        device: EventDevice,
        device_details: InputDeviceDetails,
        disconnected_send_channel: trio.MemorySendChannel,
        keyboard_send_channel: trio.MemorySendChannel,
    ):
        self.device = device
        self.device_details = device_details
        self.disconnected_send_channel = disconnected_send_channel
        self.keyboard_send_channel = keyboard_send_channel

    def set_keyboard_send_channel(self, keyboard_send_channel: trio.MemorySendChannel):
        self.keyboard_send_channel = keyboard_send_channel

    def set_led_state(self, state: SetLed):
        self.device.set_led(state.led, state.state)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with contextlib.ExitStack() as stack:
            stack.callback(self.device.ungrab)
            logger.debug("Getting events for %r", self.device.device_path)
            task_status.started()
            while True:
                try:
                    for evt in self.device.events():
                        await trio.lowlevel.checkpoint()
                        if evt.type is EventType.EV_KEY:
                            ke = KeyEvent(key=evt.code, press=KeyPress(evt.value))
                            await self.keyboard_send_channel.send(ke)
                    await trio.sleep(1 / 60)
                except OSError as exc:
                    if exc.errno == errno.ENODEV:
                        # device has gone away
                        logger.debug("Device went away")
                        await self.disconnected_send_channel.send(KeyboardDisconnect())
                        return
                    # some other kind of error, let it rise
                    raise


class LibevdevKeyboard:
    active_listener: typing.Optional[KeyboardListener]
    scanner: typing.Optional[InputDeviceScanner]

    def __init__(
        self, disconnected_send_channel: trio.MemorySendChannel, keyboard_send_channel: trio.MemorySendChannel[KeyEvent], min_input: int
    ):
        self.disconnected_send_channel = disconnected_send_channel
        self.keyboard_send_channel = keyboard_send_channel
        self.min_input = min_input
        self.active_listener = None
        self.scanner = None

    def set_keyboard_send_channel(self, keyboard_send_channel: trio.MemorySendChannel[KeyEvent]):
        self.keyboard_send_channel = keyboard_send_channel
        if self.active_listener is not None:
            self.active_listener.set_keyboard_send_channel(keyboard_send_channel)

    def set_led_state(self, state: SetLed):
        if self.active_listener is not None:
            self.active_listener.set_led_state(state)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.active_listener is None:
                self.scanner = InputDeviceScanner(self.min_input)
                logger.debug("About to scan")
                device_details, device = await self.scanner.scan()
                logger.debug("Scanner found %r, %r", device_details, device)
                self.active_listener = KeyboardListener(
                    device=device,
                    device_details=device_details,
                    disconnected_send_channel=self.disconnected_send_channel,
                    keyboard_send_channel=self.keyboard_send_channel,
                )
                self.scanner = None
            else:
                # need to send a fake keypress so the app knows a keyboard is identified
                await self.keyboard_send_channel.send(KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.PRESSED))
                await self.keyboard_send_channel.send(KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.RELEASED))
                await self.active_listener.run()
                # now we lost the keyboard, so clear the listener; the disconnected event is sent by the listener
                self.active_listener = None
            await trio.sleep(0.001)
