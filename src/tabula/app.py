import argparse
import collections.abc
import pathlib
import sys
import typing

import trio
import trio_util

from .device.hardware import Hardware, RpcHardware
from .settings import Settings
from .rendering.renderer import Renderer
from .screens.base import (
    Screen,
    ChangeScreen,
    ScreenStackBehavior,
    Close,
    Shutdown,
    TargetScreen,
)
from .screens import SCREENS
from .util import invoke
from .db import make_db
from .editor.document import DocumentModel


class Tabula:
    hardware: Hardware
    renderer: Renderer
    screen_stack: trio_util.AsyncValue[list[Screen]]

    def __init__(self, settings: Settings):
        # TODO: pick a subclass of Hardware based on some config knob
        self.settings = settings
        self.db = make_db(settings.db_path)
        self.document = DocumentModel()
        self.screen_stack = trio_util.AsyncValue([])

    def invoke_screen(self, screen: TargetScreen, **additional_kwargs):
        screen_type = SCREENS[screen]
        return invoke(
            screen_type,
            settings=self.settings,
            renderer=self.renderer,
            hardware=self.hardware,
            db=self.db,
            document=self.document,
            screen_info=self.screen_info,
            **additional_kwargs
        )

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        event_send_channel, event_receive_channel = trio.open_memory_channel(0)
        self.hardware = RpcHardware(event_send_channel.clone(), self.settings)

        async with trio.open_nursery() as nursery:
            nursery.start_soon(
                self.dispatch_events, event_receive_channel, nursery.cancel_scope.cancel
            )
            await nursery.start(self.hardware.run)
            self.screen_info = await self.hardware.get_screen_info()
            self.renderer = Renderer(self.screen_info)
            self.screen_stack.value = [
                self.invoke_screen(TargetScreen.SystemMenu),
                self.invoke_screen(TargetScreen.KeyboardDetect),
            ]
            await self.hardware.clear_screen()
            nursery.start_soon(self.periodic_save_doc, trio_util.periodic(5))

            task_status.started()

    async def periodic_save_doc(self, trigger):
        async for _ in trigger:
            self.document.save_session(self.db)

    async def dispatch_events(
        self,
        receive_channel: trio.MemoryReceiveChannel,
        cancel_callback: collections.abc.Callable[[], None],
        *,
        task_status=trio.TASK_STATUS_IGNORED
    ):
        task_status.started()
        while True:
            await self.screen_stack.wait_value(lambda v: len(v) > 0)
            current_screen = self.screen_stack.value[-1]
            next_action = await current_screen.run(receive_channel)
            match next_action:
                case ChangeScreen():
                    new_screen = self.invoke_screen(
                        next_action.new_screen, **next_action.kwargs
                    )
                    match next_action.screen_stack_behavior:
                        case ScreenStackBehavior.REPLACE_ALL:
                            self.screen_stack.value = [new_screen]
                        case ScreenStackBehavior.REPLACE_LAST:
                            self.screen_stack.value[-1] = new_screen
                        case ScreenStackBehavior.APPEND:
                            self.screen_stack.value.append(new_screen)
                case Close():
                    self.screen_stack.value.pop()
                case Shutdown():
                    self.settings.save()
                    # TODO: clean shutdown tasks?
                    print("Shutting down…")
                    # This RPC never actually gets sent because of the cancel callback.
                    # Waiting a few seconds allows it to get sent, but there must be a better way.
                    # otoh it won't be an issue when actually running on the kobo, so.
                    await self.hardware.clear_screen()
                    await trio.sleep(0.5)
                    cancel_callback()

    @classmethod
    async def start_app(cls, settings_path):
        settings = Settings.load(settings_path)
        app = cls(settings)
        await app.run()


parser = argparse.ArgumentParser(prog="tabula")
parser.add_argument("settings", type=pathlib.Path)


def main(argv=sys.argv):
    """
    Args:
        argv (list): List of arguments

    Returns:
        int: A return code

    Does stuff.
    """
    parsed = parser.parse_args(argv[1:])
    trio.run(Tabula.start_app, parsed.settings)
    return 0
