# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

__version__ = "0.0.0"

from .ink import Ink


def get_ink() -> Ink:
    try:
        from .fbink import FbInk

        return FbInk()
    except ModuleNotFoundError:
        print("Falling back to DummyInk")
        from .dummyink import DummyInk

        return DummyInk()
