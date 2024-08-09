import collections.abc
import dataclasses
import enum
import logging
import typing

import msgspec
import trio

from ..commontypes import TabulaError
from ..device.hwtypes import AnnotatedKeyEvent, KeyboardDisconnect, TabulaEvent, TapEvent
from ..util import invoke_if_present

logger = logging.getLogger(__name__)


class TargetScreen(enum.Enum):
    SystemMenu = enum.auto()
    SessionList = enum.auto()
    SessionActions = enum.auto()
    Drafting = enum.auto()
    Fonts = enum.auto()


class TargetDialog(enum.Enum):
    Ok = enum.auto()
    YesNo = enum.auto()
    Help = enum.auto()
    ComposeHelp = enum.auto()
    SprintControl = enum.auto()
    KeyboardDetect = enum.auto()


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


class ScreenError(TabulaError):
    pass


@dataclasses.dataclass(frozen=True)
class ResponderMetadata:
    responder: "Responder"
    event_channel: trio.MemorySendChannel[TabulaEvent]
    cancel: collections.abc.Callable[[], None]


class Responder:
    async def run(self, *, task_status: trio.TaskStatus):
        event_send_channel, event_receive_channel = trio.open_memory_channel[TabulaEvent](0)
        with trio.CancelScope() as cancel_scope:
            task_status.started(ResponderMetadata(responder=self, event_channel=event_send_channel, cancel=cancel_scope.cancel))

            async with event_receive_channel:
                logger.debug("Listening for events in %r", self)
                while True:
                    match event := await event_receive_channel.receive():
                        case AnnotatedKeyEvent():
                            await invoke_if_present(self, "handle_key_event", event=event)
                        case TapEvent():
                            await invoke_if_present(self, "handle_tap_event", event=event)
                        case KeyboardDisconnect():
                            await invoke_if_present(self, "handle_keyboard_disconnect")


class Screen(Responder):
    pass
