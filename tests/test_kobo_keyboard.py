# The only way we can do this AT ALL is with some fairly extensive mocking/fakes. But it's worth doing.
from __future__ import annotations

import collections
import contextlib
import copy
import datetime
import errno
import logging
import pathlib
from typing import TYPE_CHECKING

import pytest
import trio
from trio_util import AsyncBool, AsyncValue

import tabula.device.kobo_keyboard  # important to preserve the namespace for monkeypatching
from tabula.device.eventsource import Event, EventType, KeyCode
from tabula.device.hwtypes import DeviceBus, KeyboardDisconnect

if TYPE_CHECKING:
    from typing import ClassVar


logger = logging.getLogger(__name__)


class ClockFilter(logging.Filter):
    def filter(self, record):
        record.trio_time = trio.current_time()
        return record


@pytest.fixture(scope="module", autouse=True)
def install_filter():
    clock_filter = ClockFilter()
    tabula.device.kobo_keyboard.logger.addFilter(clock_filter)
    logger.addFilter(clock_filter)
    yield
    tabula.device.kobo_keyboard.logger.removeFilter(clock_filter)
    logger.removeFilter(clock_filter)


class IdentifyInputsMocker:
    current: tuple[tabula.device.kobo_keyboard.EventDeviceDetails, ...]

    def __init__(self):
        self.current = ()

    def identify_inputs(self, min_input: int, known_good: tuple[pathlib.Path, ...]):
        return self.current


class FakeEventDevice(contextlib.AbstractContextManager):
    devices: ClassVar[AsyncValue[dict[pathlib.Path, FakeEventDevice]]] = AsyncValue({})
    grabbed: AsyncBool

    def __new__(cls, device_path: pathlib.Path):
        if device_path not in cls.devices.value:
            dev = super().__new__(cls)
            dev.setup(device_path)
            new_devices = copy.copy(cls.devices.value)
            new_devices[device_path] = dev
            cls.devices.value = new_devices
        return cls.devices.value[device_path]

    def setup(self, device_path: pathlib.Path):
        self.device_path = device_path
        self.eventqueue = collections.deque()
        self.grabbed = AsyncBool(False)
        self.throw_next_time = False

    def grab(self):
        self.grabbed.value = True

    def ungrab(self):
        self.grabbed.value = False
        self.throw_next_time = False
        self.eventqueue.clear()

    def __enter__(self):
        self.grab()

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.ungrab()
        return False

    def events(self) -> collections.abc.Iterator[Event]:
        if not self.grabbed.value:
            return
        while True:
            try:
                if self.throw_next_time:
                    raise OSError(errno.ENODEV, "bye!")
                yield self.eventqueue.popleft()
            except IndexError:
                return


@pytest.fixture(autouse=True)
def clear_fake_event_devices():
    FakeEventDevice.devices.value = {}


async def test_device_listener(monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock):
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    samplepath = pathlib.Path("/test/kbd/sample")
    listener = tabula.device.kobo_keyboard.DeviceListener(samplepath)
    assert samplepath in FakeEventDevice.devices.value
    fakedevice = FakeEventDevice.devices.value[samplepath]
    assert not fakedevice.grabbed.value
    await nursery.start(listener.run)
    await fakedevice.grabbed.wait_value(True)
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    device_path = None
    with trio.move_on_after(1):
        device_path = await listener.device_recv_channel.receive()
    assert device_path is samplepath


async def test_maybe_keyboard_listener(monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock):
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    samplepath = pathlib.Path("/test/kbd/sample")
    details = tabula.device.kobo_keyboard.EventDeviceDetails(
        name="Sample Keyboard", bus=DeviceBus.USB, identifier="sample", inputpaths=[samplepath]
    )
    listener = tabula.device.kobo_keyboard.MaybeKeyboardListener(details)
    await nursery.start(listener.run)
    await FakeEventDevice.devices.wait_value(lambda d: samplepath in d)
    fakedevice = FakeEventDevice.devices.value[samplepath]
    await fakedevice.grabbed.wait_value(True)
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    with trio.move_on_after(1):
        found_details, found_device_path = await listener.device_recv_channel.receive()
    assert found_device_path is samplepath
    assert found_details is details


async def test_scanner(monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock):
    iim = IdentifyInputsMocker()
    monkeypatch.setattr(tabula.device.kobo_keyboard, "identify_inputs", iim.identify_inputs)
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    scanner = tabula.device.kobo_keyboard.InputDeviceScanner(0)
    found = AsyncValue(None)

    async def do_scan(*, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        found.value = await scanner.scan()

    await nursery.start(do_scan)
    assert found.value is None
    samplepath = pathlib.Path("/test/kbd/sample")
    iim.current = (
        tabula.device.kobo_keyboard.EventDeviceDetails(
            name="Sample Keyboard", bus=DeviceBus.USB, identifier="sample", inputpaths=[samplepath]
        ),
    )
    with trio.fail_after(2):
        await FakeEventDevice.devices.wait_value(lambda d: samplepath in d)
    fakedevice = FakeEventDevice.devices.value[samplepath]
    with trio.fail_after(2):
        await fakedevice.grabbed.wait_value(True)
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    with trio.fail_after(1):
        await found.wait_value(lambda d: d is not None)
    found_details, found_device_path = found.value
    assert found_details == iim.current[0]
    assert found_device_path is samplepath


async def test_single_keyboard_discovery(monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock):
    iim = IdentifyInputsMocker()
    monkeypatch.setattr(tabula.device.kobo_keyboard, "identify_inputs", iim.identify_inputs)
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    disconnected_send_channel, disconnected_receive_channel = trio.open_memory_channel(1)
    keyboard_send_channel, keyboard_receive_channel = trio.open_memory_channel(100)
    keyboard = tabula.device.kobo_keyboard.LibevdevKeyboard(disconnected_send_channel, keyboard_send_channel, 0)
    await nursery.start(keyboard.run)
    assert keyboard.scanner is not None
    samplepath = pathlib.Path("/test/kbd/sample")
    iim.current = (
        tabula.device.kobo_keyboard.EventDeviceDetails(
            name="Sample Keyboard", bus=DeviceBus.USB, identifier="sample", inputpaths=[samplepath]
        ),
    )
    await FakeEventDevice.devices.wait_value(lambda d: samplepath in d)
    fakedevice = FakeEventDevice.devices.value[samplepath]
    assert keyboard.active_listener is None
    await fakedevice.grabbed.wait_value(True)
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    with trio.fail_after(2):
        await keyboard_receive_channel.receive()
    assert keyboard.active_listener is not None
    assert keyboard.active_listener.device_details.name == "Sample Keyboard"


async def test_single_keyboard_goes_away(monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock):
    iim = IdentifyInputsMocker()
    samplepath = pathlib.Path("/test/kbd/sample")
    iim.current = (
        tabula.device.kobo_keyboard.EventDeviceDetails(
            name="Sample Keyboard", bus=DeviceBus.USB, identifier="sample", inputpaths=[samplepath]
        ),
    )
    monkeypatch.setattr(tabula.device.kobo_keyboard, "identify_inputs", iim.identify_inputs)
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    disconnected_send_channel, disconnected_receive_channel = trio.open_memory_channel(1)
    keyboard_send_channel, keyboard_receive_channel = trio.open_memory_channel(100)
    keyboard = tabula.device.kobo_keyboard.LibevdevKeyboard(disconnected_send_channel, keyboard_send_channel, 0)
    await nursery.start(keyboard.run)
    assert keyboard.scanner is not None
    await FakeEventDevice.devices.wait_value(lambda d: samplepath in d)
    fakedevice = FakeEventDevice.devices.value[samplepath]
    await fakedevice.grabbed.wait_value(True)
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    with trio.fail_after(2):
        await fakedevice.grabbed.wait_value(False)
        await keyboard_receive_channel.receive()
    await fakedevice.grabbed.wait_value(True)
    assert keyboard.active_listener is not None
    assert keyboard.active_listener.device_details.name == "Sample Keyboard"

    fakedevice.throw_next_time = True
    with trio.fail_after(2):
        await fakedevice.grabbed.wait_value(False)
        recv = await disconnected_receive_channel.receive()
    assert isinstance(recv, KeyboardDisconnect)


async def test_single_keyboard_multiple_device_discovery(
    monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock
):
    iim = IdentifyInputsMocker()
    monkeypatch.setattr(tabula.device.kobo_keyboard, "identify_inputs", iim.identify_inputs)
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    disconnected_send_channel, disconnected_receive_channel = trio.open_memory_channel(1)
    keyboard_send_channel, keyboard_receive_channel = trio.open_memory_channel(100)
    keyboard = tabula.device.kobo_keyboard.LibevdevKeyboard(disconnected_send_channel, keyboard_send_channel, 0)
    await nursery.start(keyboard.run)
    assert keyboard.scanner is not None
    samplepath_1 = pathlib.Path("/test/kbd/sample_1")
    samplepath_2 = pathlib.Path("/test/kbd/sample_2")
    iim.current = (
        tabula.device.kobo_keyboard.EventDeviceDetails(
            name="Sample Keyboard", bus=DeviceBus.USB, identifier="sample", inputpaths=[samplepath_1, samplepath_2]
        ),
    )
    await FakeEventDevice.devices.wait_value(lambda d: samplepath_1 in d and samplepath_2 in d)
    fakedevice_1 = FakeEventDevice.devices.value[samplepath_1]
    fakedevice_2 = FakeEventDevice.devices.value[samplepath_2]
    assert keyboard.active_listener is None
    await fakedevice_1.grabbed.wait_value(True)
    await fakedevice_2.grabbed.wait_value(True)
    fakedevice_1.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice_1.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    with trio.fail_after(2):
        await fakedevice_1.grabbed.wait_value(False)
        await fakedevice_2.grabbed.wait_value(False)
        await keyboard_receive_channel.receive()
        await fakedevice_1.grabbed.wait_value(True)
    assert keyboard.active_listener is not None
    assert keyboard.active_listener.device_details.name == "Sample Keyboard"
    assert fakedevice_1.grabbed.value
    assert not fakedevice_2.grabbed.value


async def test_multiple_keyboard_discovery(monkeypatch: pytest.MonkeyPatch, nursery: trio.Nursery, autojump_clock: trio.testing.MockClock):
    iim = IdentifyInputsMocker()
    monkeypatch.setattr(tabula.device.kobo_keyboard, "identify_inputs", iim.identify_inputs)
    monkeypatch.setattr(tabula.device.kobo_keyboard, "EventDevice", FakeEventDevice)
    disconnected_send_channel, disconnected_receive_channel = trio.open_memory_channel(1)
    keyboard_send_channel, keyboard_receive_channel = trio.open_memory_channel(100)
    keyboard = tabula.device.kobo_keyboard.LibevdevKeyboard(disconnected_send_channel, keyboard_send_channel, 0)
    await nursery.start(keyboard.run)
    assert keyboard.scanner is not None
    samplepath_1 = pathlib.Path("/test/kbd/sample_1")
    samplepath_2 = pathlib.Path("/test/kbd/sample_2")
    samplepath_3 = pathlib.Path("/test/kbd/sample_3")
    iim.current = (
        tabula.device.kobo_keyboard.EventDeviceDetails(
            name="Sample Keyboard", bus=DeviceBus.USB, identifier="sample", inputpaths=[samplepath_1, samplepath_2]
        ),
    )
    await FakeEventDevice.devices.wait_value(lambda d: samplepath_1 in d and samplepath_2 in d)
    assert samplepath_3 not in FakeEventDevice.devices.value
    fakedevice_1 = FakeEventDevice.devices.value[samplepath_1]
    fakedevice_2 = FakeEventDevice.devices.value[samplepath_2]
    assert keyboard.active_listener is None
    await fakedevice_1.grabbed.wait_value(True)
    await fakedevice_2.grabbed.wait_value(True)

    iim.current += (
        tabula.device.kobo_keyboard.EventDeviceDetails(
            name="Sample BT Keyboard", bus=DeviceBus.BLUETOOTH, identifier="btsample", inputpaths=[samplepath_3]
        ),
    )
    await FakeEventDevice.devices.wait_value(lambda d: samplepath_3 in d)
    fakedevice_3 = FakeEventDevice.devices.value[samplepath_3]
    await fakedevice_3.grabbed.wait_value(True)

    fakedevice_3.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=1, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    fakedevice_3.eventqueue.append(
        Event(type=EventType.EV_KEY, code=KeyCode.KEY_SPACE, value=0, timestamp=datetime.timedelta(seconds=autojump_clock.current_time()))
    )
    with trio.fail_after(2):
        await fakedevice_3.grabbed.wait_value(False)
        await keyboard_receive_channel.receive()
    await fakedevice_3.grabbed.wait_value(True)
    assert keyboard.active_listener is not None
    assert keyboard.active_listener.device_details.name == "Sample BT Keyboard"
    assert not fakedevice_1.grabbed.value
    assert not fakedevice_2.grabbed.value
    assert fakedevice_3.grabbed.value
