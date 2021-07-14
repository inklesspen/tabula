# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import codecs
import os
import pathlib
import typing

import attr
import pygtrie
import toml
import trio.lowlevel

from .device.types import InputDevice

SETTINGS = trio.lowlevel.RunVar("SETTINGS")


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


def _dump_input_device(v: InputDevice):
    fields = attr.fields(InputDevice)
    return attr.asdict(
        v,
        filter=attr.filters.include(
            fields.vendor_id, fields.product_id, fields.interface_id
        ),
    )


def _text_repr(c):
    d = ord(c)
    if d >= 0x10000:
        return "\\U{:08x}".format(d)
    else:
        return "\\u{:04x}".format(d)


def unicode_escape(ex):
    s, start, end = ex.object, ex.start, ex.end
    return "".join(_text_repr(c) for c in s[start:end]), end


codecs.register_error("unicode_escape", unicode_escape)


class TabulaTomlEncoder(toml.TomlPathlibEncoder):
    def __init__(self, _dict=dict, preserve=False):
        super(TabulaTomlEncoder, self).__init__(_dict, preserve)
        self.dump_funcs[InputDevice] = _dump_input_device


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
        settings_dict = toml.loads(data_file.read_text(encoding="utf-8"))
        if "compose_sequences" in settings_dict:
            settings_dict["compose_sequences"] = {
                tuple(k.split()): v
                for k, v in settings_dict["compose_sequences"].items()
            }
        settings = Settings(**settings_dict)
        return settings


def load_settings():
    SETTINGS.set(_load_settings())


def _save_settings(settings):
    settings_dict = attr.asdict(settings)
    if "compose_sequences" in settings_dict:
        # this way TOML will dump it as a table
        settings_dict["compose_sequences"] = {
            " ".join(k): v for k, v in settings_dict["compose_sequences"].items()
        }
    print(settings_dict)
    with _data_file().open("w", encoding="ascii", errors="unicode_escape") as outfile:
        toml.dump(settings_dict, outfile, encoder=TabulaTomlEncoder())


def change_settings(**changes):
    current = SETTINGS.get()
    changed = attr.evolve(current, **changes)
    # _save_settings(changed)
    SETTINGS.set(changed)
