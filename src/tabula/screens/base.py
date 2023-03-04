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
    SessionChoices = enum.auto()
    Drafting = enum.auto()
    Fonts = enum.auto()
    Help = enum.auto()
    ComposeHelp = enum.auto()


class ScreenStackBehavior(enum.Enum):
    REPLACE_ALL = enum.auto()
    REPLACE_LAST = enum.auto()
    APPEND = enum.auto()


class ChangeScreen(msgspec.Struct, frozen=True):
    new_screen: TargetScreen
    kwargs: dict = {}
    screen_stack_behavior: ScreenStackBehavior = ScreenStackBehavior.REPLACE_ALL


class Close(msgspec.Struct, frozen=True):
    pass


class Shutdown(msgspec.Struct, frozen=True):
    pass


class DialogResult(msgspec.Struct, frozen=True):
    value: typing.Optional[typing.Any]


RetVal = ChangeScreen | Shutdown | Close | DialogResult


class Screen(abc.ABC):
    @abc.abstractmethod
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        ...
