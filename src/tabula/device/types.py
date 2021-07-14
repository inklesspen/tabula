# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc
import pathlib
import typing

import attr
import trio_typing
import trio_util

from .keyboard_consts import Key, KeyPress


@attr.frozen(kw_only=True, order=False)
class InputDevice:
    vendor_id: str
    product_id: str
    manufacturer: typing.Optional[str] = attr.field(default=None, eq=False)
    product: typing.Optional[str] = attr.field(default=None, eq=False)
    interface_id: str
    inputpath: typing.Optional[pathlib.Path] = attr.field(
        default=None, eq=False, repr=False
    )

    @classmethod
    def from_dict(self, v):
        if v is not None:
            return InputDevice(**v)


@attr.frozen(kw_only=True)
class ScreenInfo:
    width: int
    height: int
    dpi: int


@attr.frozen(kw_only=True)
class ScreenRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def pillow_size(self):
        return (self.width, self.height)

    @property
    def pillow_origin(self):
        return (self.x, self.y)


@attr.frozen(kw_only=True)
class KeyEvent:
    key: Key
    press: KeyPress


@attr.frozen(kw_only=True)
class TouchEvent:
    x: int
    y: int


@typing.runtime_checkable
class Runnable(typing.Protocol):
    async def run(self, *, task_status: trio_typing.TaskStatus):
        ...


class Display(typing.Protocol):
    def get_screen_info(self) -> ScreenInfo:
        ...

    def clear(self):
        ...

    def display_pixels(self, imagebytes: bytes, rect: ScreenRect):
        ...

    def save_screen(self) -> None:
        ...

    def restore_screen(self) -> None:
        ...


class Touchable(typing.Protocol):
    async def touchstream(self) -> collections.abc.AsyncIterable[TouchEvent]:
        ...


class Keyboard(typing.Protocol):
    presence: trio_util.AsyncBool

    async def keystream(self) -> collections.abc.AsyncIterable[KeyEvent]:
        ...
