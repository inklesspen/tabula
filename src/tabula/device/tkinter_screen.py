# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import collections.abc
import contextlib
import json
import random
import re
import tkinter
import tkinter.ttk
import _tkinter

import PIL.Image
import PIL.ImageTk
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
from ..util import tabula_data_dir


# support randomizing a fake vendor and product id
# to make the keyboard discovery testable


CLARA_SIZE = (1072, 1448)
DISPLAY_SIZE = (536, 724)
CLARA_DPI = 300
DISPLAY_DPI = 150


MISC_KEYS = {
    "space": Key.KEY_SPACE,
    "BackSpace": Key.KEY_BACKSPACE,
    "Return": Key.KEY_ENTER,
    "Tab": Key.KEY_TAB,
    "minus": Key.KEY_MINUS,
    "equal": Key.KEY_EQUAL,
    "quoteleft": Key.KEY_GRAVE,
    "grave": Key.KEY_GRAVE,
    "asciitilde": Key.KEY_GRAVE,
    "exclam": Key.KEY_1,
    "at": Key.KEY_2,
    "numbersign": Key.KEY_3,
    "dollar": Key.KEY_4,
    "percent": Key.KEY_5,
    "asciicircum": Key.KEY_6,
    "ampersand": Key.KEY_7,
    "asterisk": Key.KEY_8,
    "parenleft": Key.KEY_9,
    "parenright": Key.KEY_0,
    "underscore": Key.KEY_MINUS,
    "plus": Key.KEY_EQUAL,
    "bracketleft": Key.KEY_LEFTBRACE,
    "bracketright": Key.KEY_RIGHTBRACE,
    "backslash": Key.KEY_BACKSLASH,
    "braceleft": Key.KEY_LEFTBRACE,
    "braceright": Key.KEY_RIGHTBRACE,
    "bar": Key.KEY_BACKSLASH,
    "semicolon": Key.KEY_SEMICOLON,
    "quoteright": Key.KEY_APOSTROPHE,
    "colon": Key.KEY_SEMICOLON,
    "quotedbl": Key.KEY_APOSTROPHE,
    "apostrophe": Key.KEY_APOSTROPHE,
    "comma": Key.KEY_COMMA,
    "period": Key.KEY_DOT,
    "slash": Key.KEY_SLASH,
    "less": Key.KEY_COMMA,
    "greater": Key.KEY_DOT,
    "question": Key.KEY_SLASH,
    "Left": Key.KEY_LEFT,
    "Right": Key.KEY_RIGHT,
    "Up": Key.KEY_UP,
    "Down": Key.KEY_DOWN,
    "F1": Key.KEY_F1,
    "F2": Key.KEY_F2,
    "F3": Key.KEY_F3,
    "F4": Key.KEY_F4,
    "F5": Key.KEY_F5,
    "F6": Key.KEY_F6,
    "F7": Key.KEY_F7,
    "F8": Key.KEY_F8,
    "F9": Key.KEY_F9,
    "F10": Key.KEY_F10,
    "F11": Key.KEY_F11,
    "F12": Key.KEY_F12,
}

MODIFIER_KEYS = {
    "Meta_L": Key.KEY_LEFTMETA,
    "Alt_L": Key.KEY_LEFTALT,
    "Control_L": Key.KEY_LEFTCTRL,
    "Shift_L": Key.KEY_LEFTSHIFT,
    "Meta_R": Key.KEY_RIGHTMETA,
    "Alt_R": Key.KEY_RIGHTALT,
    "Control_R": Key.KEY_RIGHTCTRL,
    "Shift_R": Key.KEY_RIGHTSHIFT,
}

# key mapping in Tk is kind of a mess. but this is really only for dev work anyway.
def mapkeyevent(event) -> list[KeyEvent]:
    # somehow this happens when switching windows sometimes?
    if event.keycode == 0:
        return []
    # fn key, ignore
    if event.keysym == "Super_L":
        return []
    press = {"KeyPress": KeyPress.PRESSED, "KeyRelease": KeyPress.RELEASED}[
        event.type.name
    ]
    # alphanumeric
    if re.match("^[a-zA-Z0-9]$", event.keysym):
        return [KeyEvent(key=Key[f"KEY_{event.keysym.upper()}"], press=press)]

    if event.keysym in MISC_KEYS:
        return [KeyEvent(key=MISC_KEYS[event.keysym], press=press)]

    if event.keysym in MODIFIER_KEYS:
        return [KeyEvent(key=MODIFIER_KEYS[event.keysym], press=press)]

    if event.keysym == "Caps_Lock":
        # Capslock produces only a KeyPress when enabled, and only a KeyRelease when disabled.
        # So we have to emit both; the editor will track capslock state
        return [
            KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
            KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
        ]
    raise ValueError("Unhandled key event {!r}".format(event))


HEX_DIGITS = tuple("0123456789ABCDEF")


def hex_id():
    return "".join(random.choices(HEX_DIGITS, k=4))


def _data_file():
    return tabula_data_dir() / "tkinter.json"


def load_json():
    return json.load(_data_file().open("r", encoding="utf-8"))


def save_json(data):
    with _data_file().open("w", encoding="utf-8") as out:
        json.dump(data, out)


class TkTouchScreen(contextlib.AbstractContextManager):
    def __init__(self):
        self.root = None
        self.label = None
        self.id_variable = None
        self.saved = None
        self.clear()
        self.present_devices = trio_util.AsyncValue(value=[])
        self.devicespec = trio_util.AsyncValue(value=None)
        self.connected = trio_util.AsyncBool(value=False)
        self.keyqueue = collections.deque(maxlen=50)
        self.touchqueue = collections.deque(maxlen=50)
        self.json_data = {}

    def _refresh_tk(self):
        if self.root is not None:
            self._tk_img = PIL.ImageTk.PhotoImage(self.screen.resize(DISPLAY_SIZE))
        if self.label is not None:
            self.label.reconfigure(image=self._tk_img)

    def key_handler(self, event):
        # print(["key_handler", event])
        mapped = mapkeyevent(event)
        print(["key_handler", mapped])
        self.keyqueue.extend(mapped)

    def touch_handler(self, event):
        self.touchqueue.append(TouchEvent(x=event.x * 2 - 1, y=event.y * 2 - 1))

    def randomize_handler(self):
        self._randomize_usb_ids()

    def connected_handler(self):
        self.connected.value = bool(self.connected_variable.get())

    def __enter__(self):
        try:
            self.json_data = load_json()
            self._update_device_presence()
        except FileNotFoundError:
            pass
        if not "vendor_id" in self.json_data or not "product_id" in self.json_data:
            self._randomize_usb_ids()
        self.root = tkinter.Tk()
        self.root.bind("<KeyPress>", self.key_handler)
        self.root.bind("<KeyRelease>", self.key_handler)
        self._refresh_tk()
        self.label = tkinter.Label(self.root, image=self._tk_img)
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self.touch_handler)

        self.id_variable = tkinter.StringVar()
        self.id_variable.set(self._describe_usb_ids())
        self.id_label = tkinter.Label(self.root, textvariable=self.id_variable)
        self.id_label.pack(side="left")
        self.randomize_button = tkinter.ttk.Button(
            self.root, text="Randomize IDs", command=self.randomize_handler
        )
        self.randomize_button.pack(side="left")
        self.connected_variable = tkinter.IntVar()
        self.connected_checkbox = tkinter.ttk.Checkbutton(
            self.root,
            text="Connected",
            command=self.connected_handler,
            variable=self.connected_variable,
        )
        self.connected_checkbox.pack(side="left")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.root.destroy()
        self.root = None
        self.label = None

    def _randomize_usb_ids(self):
        self.json_data["vendor_id"] = hex_id()
        self.json_data["product_id"] = hex_id()
        save_json(self.json_data)
        if self.id_variable is not None:
            self.id_variable.set(self._describe_usb_ids())
        self._update_device_presence()

    def _describe_usb_ids(self):
        return " ".join([self.json_data["vendor_id"], self.json_data["product_id"]])

    def _update_device_presence(self):
        if self.connected.value:
            self.present_devices.value = [
                InputDevice(
                    vendor_id=self.json_data["vendor_id"],
                    product_id=self.json_data["product_id"],
                    interface_id="00",
                    manufacturer="TkInter",
                    product=self.__describe_usb_ids(),
                )
            ]
        else:
            self.present_devices.value = []

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with self:
            task_status.started()
            while True:
                # do all pending things right away, but let other tasks run too
                while self.root.tk.dooneevent(_tkinter.DONT_WAIT):
                    await trio.sleep(0)

                # sleep just a little bit
                await trio.sleep(1 / 60)

    def get_screen_info(self) -> ScreenInfo:
        return ScreenInfo(width=CLARA_SIZE[0], height=CLARA_SIZE[1], dpi=CLARA_DPI)

    def clear(self):
        self.screen = PIL.Image.new("L", CLARA_SIZE, "white")
        self._refresh_tk()

    def display_pixels(self, imagebytes: bytes, rect: ScreenRect):
        new_image = PIL.Image.frombytes(
            "L", rect.pillow_size, imagebytes, "raw", "L", 0, 1
        )
        self.screen.paste(new_image, rect.pillow_origin)
        self._refresh_tk()

    def save_screen(self) -> None:
        self.saved = self.screen.copy()

    def restore_screen(self) -> None:
        if self.saved is None:
            raise ValueError("Cannot restore screen; nothing saved.")
        self.screen = self.saved
        self._refresh_tk()
        self.saved = None

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

    async def touchstream(self) -> collections.abc.AsyncIterable[TouchEvent]:
        while True:
            try:
                yield self.touchqueue.popleft()
                await trio.sleep(0)
            except IndexError:
                # No touch events, sleep a bit longer.
                await trio.sleep(1 / 60)
