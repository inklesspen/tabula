# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import codecs
import os
import pathlib
import typing

import attr
import pygtrie
import tomli
import trio.lowlevel

from .device.keyboard_consts import Key
from .device.types import InputDevice

SETTINGS = trio.lowlevel.RunVar("SETTINGS")

# TODO: allow reading/writing some settings (keyboard info, etc) to sqlite db


@attr.frozen(kw_only=True)
class Settings:
    drafting_fonts: list[str]
    export_path: pathlib.Path = attr.field(converter=pathlib.Path)
    evdev_keyboard: typing.Optional[InputDevice] = attr.field(
        default=None, converter=InputDevice.from_dict
    )
    compose_sequences: pygtrie.Trie = attr.field(
        converter=pygtrie.Trie, factory=pygtrie.Trie
    )
    keymaps: list[dict[Key, str]]


def _data_file():
    if "TABULA_DATA_DIR" in os.environ:
        data_dir = pathlib.Path(os.environ["TABULA_DATA_DIR"])
    else:
        data_dir = pathlib.Path.home() / ".local/share/tabula"
    data_file = data_dir / "config.toml"
    return data_file


def _load_settings():
    data_file = _data_file()
    if data_file.is_file():
        settings_dict = tomli.load(data_file.open(mode="rb"))
        if "keymaps" in settings_dict:
            for i, keymap in enumerate(settings_dict["keymaps"]):
                settings_dict["keymaps"][i] = {Key[k]: v for k, v in keymap.items()}
        if "compose_sequences" in settings_dict:
            settings_dict["compose_sequences"] = {
                tuple(k.split()): v
                for k, v in settings_dict["compose_sequences"].items()
            }
        settings = Settings(**settings_dict)
        return settings


def load_settings():
    SETTINGS.set(_load_settings())
