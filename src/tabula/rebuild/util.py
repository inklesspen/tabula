from typing import TYPE_CHECKING

import msgspec
import trio

if TYPE_CHECKING:
    from .app import Tabula
    from .hardware import Hardware
    from .settings import Settings

APP_CONTROLLER = trio.lowlevel.RunVar("APP_CONTROLLER")


async def checkpoint():
    await trio.sleep(0)


def hardware() -> "Hardware":
    app: "Tabula" = APP_CONTROLLER.get()
    return app.hardware


def settings() -> "Settings":
    app: "Tabula" = APP_CONTROLLER.get()
    return app.settings


def evolve(obj: msgspec.Struct, **changes):
    cls = obj.__class__
    for field_name in cls.__struct_fields__:
        if field_name not in changes:
            changes[field_name] = getattr(obj, field_name)
    return cls(**changes)
