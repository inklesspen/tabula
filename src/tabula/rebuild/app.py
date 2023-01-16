import collections.abc
import sys
import typing

import trio
import trio_util

from .hardware import Hardware, RpcHardware
from .settings import load_settings, Settings
from ..rendering.renderer2 import Renderer
from .screens import Screen, KeyboardDetect, SystemMenu, Switch, Modal, Close, Shutdown
from .util import invoke
from .db import make_db
from .document import DocumentModel


class Tabula:
    hardware: Hardware
    renderer: Renderer
    screen_stack: trio_util.AsyncValue[list[Screen]]

    def __init__(self, settings: Settings):
        # TODO: pick a subclass of Hardware based on some config knob
        self.settings = settings
        self.db = make_db(settings.db_path)
        self.document = DocumentModel(self.db)
        self.screen_stack = trio_util.AsyncValue([])

    def invoke_screen(self, screen: typing.Type[Screen], **additional_kwargs):
        return invoke(
            screen,
            settings=self.settings,
            renderer=self.renderer,
            hardware=self.hardware,
            db=self.db,
            document=self.document,
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
            screen_info = await self.hardware.get_screen_info()
            self.renderer = Renderer(screen_info)
            self.screen_stack.value = [
                self.invoke_screen(KeyboardDetect, on_startup=True)
            ]
            await self.hardware.clear_screen()
            task_status.started()

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
                case Switch():
                    new_screen = self.invoke_screen(
                        next_action.new_screen, **next_action.kwargs
                    )
                    self.screen_stack.value[-1] = new_screen
                case Modal():
                    print(next_action)
                    modal_screen = self.invoke_screen(
                        next_action.modal, **next_action.kwargs
                    )
                    self.screen_stack.value.append(modal_screen)
                case Close():
                    print(next_action)
                    self.screen_stack.value.pop()
                case Shutdown():
                    # TODO: clean shutdown tasks?
                    print("Shutting down…")
                    # This RPC never actually gets sent because of the cancel callback.
                    # Waiting a few seconds allows it to get sent, but there must be a better way.
                    await self.hardware.clear_screen()
                    await trio.sleep(0.5)
                    cancel_callback()

        # incoming events need to be filtered and processed
        # KeyEvent -> AnnotatedKeyEvent
        # TouchReport -> ???
        # PowerButtonPress -> ???
        # once processed, events need to be dispatched to the facing screen
        # maybe screens should be able to choose not to get composes though?

        # continue to handle keymaps and composes in the Hardware object, but each screen can choose to disable or enable composes when becoming front
        # when enabling composes (because a screen became front), throw away any in-progress compose state and start fresh

        # titlebar/statusbar/etc only needs to be shown on drafting screen, so that does not have to be independent

    @classmethod
    async def start_app(cls):
        settings = await load_settings()
        app = cls(settings)
        await app.run()


def main(argv=sys.argv):
    """
    Args:
        argv (list): List of arguments

    Returns:
        int: A return code

    Does stuff.
    """
    trio.run(Tabula.start_app)
    return 0
