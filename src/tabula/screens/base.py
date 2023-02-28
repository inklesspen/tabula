import abc
import enum
import typing

import msgspec
import trio

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer


class TargetScreen(enum.Enum):
    KeyboardDetect = enum.auto()
    SystemMenu = enum.auto()
    SessionList = enum.auto()
    Drafting = enum.auto()
    Fonts = enum.auto()
    Help = enum.auto()
    ComposeHelp = enum.auto()


class Switch(msgspec.Struct, frozen=True):
    new_screen: TargetScreen
    kwargs: dict = {}


class Modal(msgspec.Struct, frozen=True):
    # Modal is used only for KeyboardDetect, so see if we can just handle that specially
    # Except I'm also using it for Help and ComposeHelp.
    modal: TargetScreen
    kwargs: dict = {}


class Close(msgspec.Struct, frozen=True):
    pass


class Shutdown(msgspec.Struct, frozen=True):
    pass


class DialogResult(msgspec.Struct, frozen=True):
    value: typing.Optional[typing.Any]


RetVal = Switch | Shutdown | Modal | Close | DialogResult


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
