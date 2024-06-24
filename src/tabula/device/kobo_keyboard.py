import pathlib
import typing

import msgspec
import libevdev
import trio

from .keyboard_consts import Key, KeyPress, Led
from .hwtypes import KeyEvent, KeyboardDisconnect
from .deviceutil import open_device

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


class InputDevice(msgspec.Struct, frozen=True, eq=False):
    vendor_id: str
    product_id: str
    manufacturer: typing.Optional[str]
    product: typing.Optional[str]
    interface_id: str
    inputpath: typing.Optional[pathlib.Path]

    @classmethod
    def from_dict(self, v):
        if v is not None:
            return InputDevice(**v)


class InputDeviceNotFound(Exception):
    def __init__(self, devicespec: InputDevice):
        self.devicespec = devicespec


def parse_eventnum(name):
    if not name.startswith("event"):
        return -1
    numstr = name[5:]
    try:
        return int(numstr)
    except ValueError:
        return -1


def identify_inputs() -> list[InputDevice]:
    found = []
    for input_symlink in pathlib.Path("/sys/class/input").iterdir():
        if parse_eventnum(inputname := input_symlink.name) < MIN_USB_INPUT:
            continue
        inputpath = pathlib.Path("/dev/input") / inputname
        # the inputpath may not exist immediately…
        if not inputpath.is_char_device():
            continue
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


async def listen_for_keys(
    device: InputDevice,
    channel: trio.MemorySendChannel,
    *,
    task_status=trio.TASK_STATUS_IGNORED,
):
    with open_device(device.inputpath) as d:
        task_status.started()
        while True:
            try:
                for e in d.events():
                    await trio.sleep(0)
                    if e.matches(libevdev.EV_KEY):
                        ke = KeyEvent(key=Key(e.code.value), press=KeyPress(e.value))
                        await channel.send(ke)
                await trio.sleep(1 / 60)
            except OSError as e:
                if e.errno == 19:
                    # device has gone away
                    channel.close()
                    return
                # some other kind of error, let it rise
                raise


class AllKeyboards:
    def __init__(self, hardware_send_channel: trio.MemorySendChannel):
        self.channel = hardware_send_channel
        self.present_devices = []

    def _update_available_inputs(self):
        old_inputs = self.present_devices
        current_inputs = identify_inputs()
        if old_inputs != current_inputs:
            self.present_devices = current_inputs

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        # this is a stupid way to do this. find a better way next time.
        notified_no_keyboard = False
        ever_had_keyboard = False
        while True:
            self._update_available_inputs()
            if len(self.present_devices) > 0:
                notified_no_keyboard = False
                ever_had_keyboard = True
                async with trio.open_nursery() as nursery:
                    for device in self.present_devices:
                        device_send_channel = self.channel.clone()
                        nursery.start_soon(
                            listen_for_keys,
                            device,
                            device_send_channel,
                            name=repr(device),
                        )
            else:
                if ever_had_keyboard and not notified_no_keyboard:
                    await self.channel.send(KeyboardDisconnect())
                    notified_no_keyboard = True

                await trio.sleep(0.2)

    def set_led(self, led: Led, state: bool):
        # https://python-libevdev.readthedocs.io/en/latest/libevdev.html#libevdev.device.Device.set_leds
        # We'll have to use the actual enums from libevdev, not our own.
        # libevdev.evbit('EV_LED', led)
        # libevdev.evbit('EV_LED', Led.LED_CAPSL)
        # also it needs to access the device, which is currently nested inside a listen_for_keys task
        print(f"Setting {libevdev.evbit('EV_LED', led)} to {state}")


# def _print_event(e):
#     print("Event: time {}.{:06d}, ".format(e.sec, e.usec), end="")
#     if e.matches(libevdev.EV_SYN):
#         if e.matches(libevdev.EV_SYN.SYN_MT_REPORT):
#             print("++++++++++++++ {} ++++++++++++".format(e.code.name))
#         elif e.matches(libevdev.EV_SYN.SYN_DROPPED):
#             print(">>>>>>>>>>>>>> {} >>>>>>>>>>>>".format(e.code.name))
#         else:
#             print("-------------- {} ------------".format(e.code.name))
#     else:
#         print(
#             "type {:02x} {} code {:03x} {:20s} value {:4d}".format(
#                 e.type.value, e.type.name, e.code.value, e.code.name, e.value
#             )
#         )


# async def _devicewatch(eventpath, *, task_status=trio.TASK_STATUS_IGNORED):
#     with open_device(eventpath) as d:
#         task_status.started()
#         print("It's time")
#         while True:
#             await trio.sleep(0)
#             for e in d.events():
#                 await trio.sleep(0)
#                 _print_event(e)
