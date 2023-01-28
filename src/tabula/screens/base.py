import abc
import typing

import msgspec
import trio

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer


class Switch(msgspec.Struct, frozen=True):
    new_screen: typing.Type["Screen"]
    kwargs: dict = {}


class Modal(msgspec.Struct, frozen=True):
    modal: typing.Type["Screen"]
    kwargs: dict = {}


class Close(msgspec.Struct, frozen=True):
    pass


class Shutdown(msgspec.Struct, frozen=True):
    pass


RetVal = Switch | Shutdown | Modal | Close


class Screen(abc.ABC):
    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        self.settings = settings
        self.renderer = renderer
        self.hardware = hardware

    @abc.abstractmethod
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        ...
