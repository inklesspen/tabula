# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import typing

from .device.types import Display, Touchable, Keyboard


class Tabula:
    def __init__(
        self,
        *,
        display_cls: typing.Type[Display],
        touchable_cls: typing.Type[Touchable],
        keyboard_cls: typing.Type[Keyboard]
    ):
        self.display_cls = display_cls
        self.touchable_cls = touchable_cls
        self.keyboard_cls = keyboard_cls


def kobo():
    from .device.kobo_keyboard import EventKeyboard

    keyboard_cls = EventKeyboard
    pass


def mac_tkinter():
    from .device.tkinter_screen import TkTouchScreen

    Tabula(
        display_cls=TkTouchScreen,
        touchable_cls=TkTouchScreen,
        keyboard_cls=TkTouchScreen,
    )
