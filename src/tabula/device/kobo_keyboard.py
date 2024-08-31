from __future__ import annotations

import logging
import pathlib
import typing

import msgspec
import trio
from trio_util import AsyncValue

from .deviceutil import EventDevice
from .eventsource import EventType, KeyCode
from .hwtypes import (
    KEYBOARD_SEND_CHANNEL,
    DeviceBus,
    DeviceDisconnectedError,
    DeviceGrabError,
    InputDeviceDetails,
    KeyboardDisconnect,
    KeyEvent,
    KeyPress,
    SetLed,
)
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


def identify_inputs(min_input: int, already_grabbed: tuple[pathlib.Path, ...]) -> tuple[EventDeviceDetails, ...]:
    found = []
    for inputpath in pathlib.Path("/dev/input").glob("event*"):
        if inputpath in already_grabbed:
            found.append(inputpath)
            continue
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
        except (DeviceDisconnectedError, DeviceGrabError):
            continue
    if found:
        devices = parse_devices(DEVICES_PATH.open("r"))
        device_dict = {d["dev_path"]: d for d in devices}
        all_device_details = {}
        for inputpath in found:
            if inputpath not in device_dict:
                if inputpath in already_grabbed:
                    logger.warning("%r is already grabbed, but not found in proc device info %r", inputpath, devices)
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
    return ()


class InputDeviceScanner:
    _found: AsyncValue[tuple[EventDeviceDetails, ...]]
    listeners_by_path: dict[pathlib.Path, KeyboardListener]
    all_listeners: list[KeyboardListener]

    def __init__(self, min_input: int, listener_nursery: trio.Nursery):
        self.min_input = min_input
        self.listener_nursery = listener_nursery
        self._found = AsyncValue(())
        self.listeners_by_path = {}
        self.listeners_added = trio.Event()

    async def keep_checking(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            current_paths = tuple(self.listeners_by_path.keys())
            val = identify_inputs(self.min_input, current_paths)
            self._found.value = val
            await trio.sleep(1)

    async def update_listeners(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        async for devices_found in self._found.eventual_values():
            logger.debug("Updating listeners for devices_found %r", devices_found)
            current_paths = set(self.listeners_by_path.keys())
            seen_paths = set()
            added_paths = set()
            for device_details in devices_found:
                logger.debug("Now seeing %r", device_details)
                for inputpath in device_details.inputpaths:
                    seen_paths.add(inputpath)
                    if inputpath not in self.listeners_by_path:
                        logger.debug("Starting listener(s) for %r, %r", device_details, inputpath)
                        listener = KeyboardListener(device_path=inputpath, device_details=device_details)
                        await self.listener_nursery.start(listener.run)
                        self.listeners_by_path[inputpath] = listener
                        added_paths.add(inputpath)
            current_paths = set(self.listeners_by_path.keys())

            missing_paths = current_paths - seen_paths
            for path in missing_paths:
                listener = self.listeners_by_path.pop(path)
                logger.debug("Canceling listener for %r", listener.device_details)
                listener.cancel_scope.cancel()
            if added_paths:
                self.listeners_added.set()
            current_paths = set(self.listeners_by_path.keys())

    async def process(self):
        while True:
            current_listeners = list(self.listeners_by_path.values())

            async def wait(event: trio.Event, cancel_scope: trio.CancelScope):
                await event.wait()
                cancel_scope.cancel()

            async with trio.open_nursery() as nursery:
                new_event = trio.Event()
                nursery.start_soon(wait, new_event, nursery.cancel_scope)
                self.listeners_added = new_event
                for listener in current_listeners:
                    nursery.start_soon(wait, listener.keys_detected, nursery.cancel_scope)
            # either it's the listeners_added event, or it's one of the listeners keys_detected
            detected_listener = None
            for listener in current_listeners:
                if listener.keys_detected.is_set():
                    detected_listener = listener
                    break
            if detected_listener:
                logger.debug("Detected listener: %r on %r", detected_listener, detected_listener.device.device_path)
                return detected_listener
            await trio.sleep(0.001)

    async def scan(self):
        async with trio.open_nursery() as nursery:
            await nursery.start(self.keep_checking)
            await nursery.start(self.update_listeners)
            detected_listener = await self.process()
            nursery.cancel_scope.cancel()
            # cancel all the ones that _weren't_ detected, then return
            for listener in self.listeners_by_path.values():
                if listener is not detected_listener:
                    listener.cancel_scope.cancel()

            return detected_listener


class KeyboardListener:
    def __init__(
        self,
        device_path: pathlib.Path,
        device_details: InputDeviceDetails,
    ):
        self.device = EventDevice(device_path)
        self.device_details = device_details
        self.keys_detected = trio.Event()
        self.cancel_scope = trio.CancelScope()

    def set_led_state(self, state: SetLed):
        self.device.set_led(state.led, state.state)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with self.cancel_scope, self.device:
            logger.debug("Getting events for %r, %r", self.device.device_path, self)
            task_status.started()
            while True:
                try:
                    for evt in self.device.events():
                        if self.cancel_scope.cancel_called:
                            return
                        await trio.lowlevel.checkpoint()
                        if evt.type is EventType.EV_KEY:
                            self.keys_detected.set()
                            ke = KeyEvent(key=evt.code, press=KeyPress(evt.value))
                            await KEYBOARD_SEND_CHANNEL.get().send(ke)
                    await trio.sleep(1 / 60)
                except DeviceDisconnectedError:
                    logger.debug("Device went away")
                    self.cancel_scope.cancel()
                    return
                except (trio.BrokenResourceError, trio.ClosedResourceError):
                    logger.debug(
                        "Somehow outdated keyboard send channel %r, in %r for %r",
                        KEYBOARD_SEND_CHANNEL.get(),
                        self,
                        self.device.device_path,
                        exc_info=True,
                    )


class LibevdevKeyboard:
    active_listener: AsyncValue[typing.Optional[KeyboardListener]]
    scanner: typing.Optional[InputDeviceScanner]

    def __init__(self, disconnected_send_channel: trio.MemorySendChannel, min_input: int):
        self.disconnected_send_channel = disconnected_send_channel
        self.min_input = min_input
        self.active_listener = AsyncValue(None)
        self.scanner = None

    def set_led_state(self, state: SetLed):
        if self.active_listener.value is not None:
            self.active_listener.value.set_led_state(state)

    async def _launch_listeners(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            async with trio.open_nursery() as nursery:
                if self.active_listener.value is None:
                    logger.debug("About to scan")
                    self.scanner = InputDeviceScanner(self.min_input, nursery)
                    detected_listener = await self.scanner.scan()
                    logger.debug("Scanner found %r, %r", detected_listener.device_details, detected_listener.device.device_path)
                    if len(nursery.child_tasks) != 1:
                        logger.warning("Nursery is currently holding %r", nursery.child_tasks)
                    self.active_listener.value = detected_listener
                    self.scanner = None
            # the nursery won't exit until the last task (Which should only be the running KeyboardListener) has exited
            # now we lost the keyboard, so clear the listener and send the disconnected event
            self.active_listener.value = None
            await self.disconnected_send_channel.send(KeyboardDisconnect())
            await trio.sleep(0.001)
