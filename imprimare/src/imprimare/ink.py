# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import abc


class Ink(abc.ABC):
    @abc.abstractmethod
    def clear(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def display_pixels(
        self, imagebytes: bytes, x: int, y: int, width: int, height: int
    ):
        raise NotImplementedError()
