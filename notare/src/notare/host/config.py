# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import pathlib
import typing

from pydantic import BaseSettings, Field, IPvAnyAddress
from pydantic.env_settings import SettingsSourceCallable, SettingsError
from pydantic.fields import ModelField
from pydantic.schema import encode_default
import toml
import xdg

from ..protocol import TABULA_IP, TABULA_PORT


logger = logging.getLogger(__name__)


def toml_config_settings_source(settings: BaseSettings) -> typing.Dict[str, typing.Any]:
    toml_path: pathlib.Path = settings.__config__.toml_path
    try:
        with toml_path.open("r", encoding="utf-8") as toml_file:
            return toml.load(toml_file)
    except FileNotFoundError:
        logger.warning("Unable to read TOML configuration", exc_info=True)
        return {}
    except (OSError, toml.TomlDecodeError) as e:
        logger.warning("Unable to read TOML configuration", exc_info=True)
        raise SettingsError from e


def prepare_toml_config(fields: typing.Dict[str, ModelField]) -> str:
    output = ["# Tabula config"]
    for fieldname, field in fields.items():
        if field.field_info.extra.get("hidden", False):
            continue
        output.append("")
        title = field.field_info.title
        if title is None:
            title = fieldname.title()
        if (desc := field.field_info.description) is not None:
            output.append(f"# {title}: {desc}")
        else:
            output.append(f"# {title}:")
        if (default := field.default) is not None:
            tomldump = toml.dumps({fieldname: encode_default(default)}).strip()
            output.append(f"# {tomldump}")
        else:
            tomldump = toml.dumps(
                {fieldname: field.field_info.extra.get("sample", "REQUIRED")}
            ).strip()
            output.append(tomldump)
    return "\n".join(output)


class Settings(BaseSettings):
    ip: IPvAnyAddress = Field(TABULA_IP, title="IP address")
    port: int = Field(TABULA_PORT)

    compose_key: str = Field(
        ...,
        title="Compose key",
        description="a brief explanation of which key is the compose key",
        sample="the Any key",
    )
    drafting_fonts: typing.List[str] = Field(
        ...,
        title="Drafting fonts",
        description="in Pango's FontDescription format",
        sample=["Palatino 8", "Helvetica 8"],
    )

    allow_setting_time: bool = Field(False, description="Handy if host lacks a RTC")
    allow_markdown_export_to_device: bool = Field(False)
    shutdown_host_on_exit: bool = Field(False)

    log_keys: bool = Field(False, hidden=True)
    systemd_notify: bool = Field(False, hidden=True)

    @classmethod
    def create_toml_file(cls):
        toml_path: pathlib.Path = cls.__config__.toml_path
        toml_path.parent.mkdir(parents=True, exist_ok=True)
        toml_path.write_text(prepare_toml_config(cls.__fields__), encoding="utf-8")

    class Config:
        env_prefix = "tabula_"
        toml_path = xdg.xdg_config_home() / "tabula" / "config.toml"

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> typing.Tuple[SettingsSourceCallable, ...]:
            return init_settings, env_settings, toml_config_settings_source
