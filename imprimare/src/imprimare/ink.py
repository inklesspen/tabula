# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import abc
import contextlib

import attr


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class DeviceInfo:
    width: int
    height: int
    dpi: int
    device_name: str
    code_name: str


class Ink(contextlib.AbstractContextManager):
    @abc.abstractmethod
    def clear(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_device_info(self) -> DeviceInfo:
        raise NotImplementedError()

    @abc.abstractmethod
    def display_png(self, path: str, x: int, y: int) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def display_pixels(
        self, imagebytes: bytes, x: int, y: int, width: int, height: int
    ) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def save_screen(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def restore_screen(self) -> None:
        raise NotImplementedError()
