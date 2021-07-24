# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import collections.abc
import contextlib
import re
import tkinter
import _tkinter

import PIL.Image
import PIL.ImageTk
import trio
import trio_util

from .keyboard_consts import Key, KeyPress
from .types import ScreenInfo, ScreenRect, KeyEvent, TouchEvent


CLARA_SIZE = (1072, 1448)
DISPLAY_SIZE = (536, 724)


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


class TkTouchScreen(contextlib.AbstractContextManager):
    def __init__(self):
        self.root = None
        self.label = None
        self.saved = None
        self.clear()
        self.presence = trio_util.AsyncBool(value=True)
        self.keyqueue = collections.deque(maxlen=50)
        self.touchqueue = collections.deque(maxlen=50)

    def _refresh_tk(self):
        if self.root is not None:
            self._tk_img = PIL.ImageTk.PhotoImage(self.screen.resize(DISPLAY_SIZE))
        if self.label is not None:
            self.label.reconfigure(image=self._tk_img)

    def key_handler(self, event):
        # print(["key_handler", event])
        self.keyqueue.extend(mapkeyevent(event))

    def touch_handler(self, event):
        self.touchqueue.append(TouchEvent(x=event.x * 2 - 1, y=event.y * 2 - 1))

    def __enter__(self):
        self.root = tkinter.Tk()
        self.root.bind("<KeyPress>", self.key_handler)
        self.root.bind("<KeyRelease>", self.key_handler)
        self._refresh_tk()
        self.label = tkinter.Label(self.root, image=self._tk_img)
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self.touch_handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.root.destroy()
        self.root = None
        self.label = None

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            # do all pending things right away, but let other tasks run too
            while self.root.tk.dooneevent(_tkinter.DONT_WAIT):
                await trio.sleep(0)

            # sleep just a little bit
            await trio.sleep(1 / 60)

    def get_screen_info(self) -> ScreenInfo:
        return ScreenInfo(width=CLARA_SIZE[0], height=CLARA_SIZE[1], dpi=300)

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

    async def keystream(self) -> collections.abc.AsyncIterable[KeyEvent]:
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
