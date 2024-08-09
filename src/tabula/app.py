from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from typing import Optional, cast

import trio
import trio_util

from .db import make_db
from .device.bluetooth.bluez import BluezContext
from .device.bluetooth.clara2e import hciattach, kmods
from .device.hardware import Hardware, KoboHardware
from .device.hwtypes import AnnotatedKeyEvent, KeyboardDisconnect, TabulaEvent, TapEvent
from .editor.document import DocumentModel
from .rendering.fontconfig import setup_fontconfig
from .screens import DIALOGS, SCREENS
from .screens.base import Responder, ResponderMetadata, Screen, TargetDialog, TargetScreen
from .screens.dialogs import Dialog
from .settings import Settings
from .util import TABULA, AwaitableCallback, Future, invoke, invoke_if_present, removing, replacing_last

logger = logging.getLogger(__name__)


class Tabula:
    hardware: Hardware
    screen_stack: trio_util.AsyncValue[tuple[Screen]]
    tick_receivers: list[AwaitableCallback]
    modal_stack: trio_util.AsyncValue[tuple[Dialog]]
    current_responder_metadata: Optional[ResponderMetadata]

    def __init__(self, hardware: Hardware, settings: Settings):
        self.hardware = hardware
        self.settings = settings
        self.db = make_db(settings.db_path)
        self.document = DocumentModel()
        self.screen_stack = trio_util.AsyncValue(tuple())
        self.modal_stack = trio_util.AsyncValue(tuple())
        self.tick_receivers = []
        self._nursery = None
        self.current_responder_metadata = None

    @property
    def current_screen(self) -> Optional[Responder]:
        if self.modal_stack.value:
            return self.modal_stack.value[-1]
        if len(self.screen_stack.value) == 0:
            return None
        return self.screen_stack.value[-1]

    def invoke_screen(self, screen: TargetScreen, **additional_kwargs) -> Screen:
        screen_type = SCREENS[screen]
        screen_obj = invoke(
            screen_type,
            settings=self.settings,
            hardware=self.hardware,
            db=self.db,
            document=self.document,
            screen_info=self.screen_info,
            **additional_kwargs,
        )
        return screen_obj

    def rotate(self):
        self.hardware.set_rotation(self.screen_info.rotation.next)
        self.screen_info = self.hardware.get_screen_info()
        self.hardware.clear_screen()

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        TABULA.set(self)
        with setup_fontconfig(self.settings.font_path):
            async with trio.open_nursery() as nursery:
                self._nursery = nursery
                nursery.start_soon(self.dispatch_events, self.hardware.event_receive_channel, nursery)
                await nursery.start(self.hardware.run)

                starting_rotation = self.hardware.get_screen_info().rotation
                if starting_rotation != self.settings.default_screen_rotation:
                    self.hardware.set_rotation(self.settings.default_screen_rotation)

                self.screen_info = self.hardware.get_screen_info()
                self.hardware.clear_screen()
                nursery.start_soon(self.ticks, trio_util.periodic(5))

                await self.show_dialog(TargetDialog.KeyboardDetect)
                self.screen_stack.value = (self.invoke_screen(TargetScreen.SystemMenu),)
                task_status.started()
            self._nursery = None
        logger.debug("goodbye")

    async def ticks(self, trigger):
        async for _ in trigger:
            for receiver in self.tick_receivers:
                await receiver()

    async def show_dialog(self, target_dialog: TargetDialog, **additional_kwargs):
        dialog_cls = DIALOGS[target_dialog]
        dialog = cast(
            Dialog,
            invoke(
                dialog_cls,
                settings=self.settings,
                screen_info=self.screen_info,
                document=self.document,
                **additional_kwargs,
            ),
        )

        if self.current_responder_metadata is not None and self.current_responder_metadata.responder is self.current_screen:
            await invoke_if_present(self.current_screen, "resign_responder")
        saved_metadata = self.current_responder_metadata
        self.current_responder_metadata = None
        self.modal_stack.value += tuple([dialog])

        async def modal_wait(inner_future: Future, *, task_status: trio.TaskStatus):
            outer_future = Future()
            task_status.started(outer_future)
            await inner_future._event.wait()
            if self.current_responder_metadata.responder is not dialog:
                raise Exception("expected %r to be responder; it was instead %r", dialog, self.current_responder_metadata.responder)
            self.current_responder_metadata.cancel()
            await invoke_if_present(dialog, "resign_responder")
            self.modal_stack.value = removing(self.modal_stack.value, dialog)
            self.current_responder_metadata = saved_metadata
            if saved_metadata is not None:
                # it might be None if this is the KeyboardDetect modal launched at startup
                # because the SystemMenu hadn't been invoked yet.
                await invoke_if_present(saved_metadata.responder, "become_responder")
            outer_future.finalize(inner_future._outcome)

        return cast(Future, await self._nursery.start(modal_wait, dialog.future))

    async def shutdown(self):
        if self.current_responder_metadata is not None:
            await invoke_if_present(self.current_responder_metadata.responder, "resign_responder")
            self.current_responder_metadata.cancel()

        self.settings.save()
        # TODO: clean shutdown tasks?
        self.hardware.event_receive_channel.close()
        self._nursery.cancel_scope.cancel()
        logger.warn("Shutting down…")
        self.hardware.clear_screen()

    async def change_screen(self, target_screen: TargetScreen, **kwargs):
        if self.modal_stack.value:
            raise Exception("this is not the right way to close a modal")
        if self.current_responder_metadata.responder is not self.current_screen:
            raise Exception("attempted to change screen when not current responder")

        await invoke_if_present(self.current_screen, "resign_responder")
        self.current_responder_metadata.cancel()
        self.current_responder_metadata = None
        new_screen = self.invoke_screen(target_screen, **kwargs)
        self.screen_stack.value = replacing_last(self.screen_stack.value, new_screen)

    async def dispatch_events(
        self,
        receive_channel: trio.MemoryReceiveChannel[TabulaEvent],
        nursery: trio.Nursery,
        *,
        task_status=trio.TASK_STATUS_IGNORED,
    ):
        task_status.started()

        await self.screen_stack.wait_value(lambda v: len(v) > 0)
        while True:
            await trio.lowlevel.checkpoint()

            if self.current_screen is None:
                raise Exception("no current screen, which shouldn't ever happen")
            if self.current_responder_metadata is None or self.current_screen is not self.current_responder_metadata.responder:
                self.current_responder_metadata = cast(ResponderMetadata, await nursery.start(self.current_screen.run))
                await invoke_if_present(self.current_screen, "become_responder")

            try:
                event = receive_channel.receive_nowait()
            except trio.WouldBlock:
                await trio.sleep(1 / 60)
                continue

            match event:
                case AnnotatedKeyEvent():
                    await self.current_responder_metadata.event_channel.send(event)
                case TapEvent():
                    await self.current_responder_metadata.event_channel.send(event)
                case KeyboardDisconnect():
                    await self.current_responder_metadata.event_channel.send(event)
                    await self.show_dialog(TargetDialog.KeyboardDetect)
                case _:
                    raise NotImplementedError(f"Don't know how to handle {type(event)}.")


async def start_tabula(settings_path: pathlib.Path):
    settings = Settings.load(settings_path)
    hardware = KoboHardware(settings)
    # this isn't the proper location but we'll try it like this anyway.
    async with kmods(), BluezContext() as bluezcontext:
        _hci = await bluezcontext.nursery.start(hciattach, bluezcontext.nursery)
        try:
            with trio.fail_after(5):
                await bluezcontext.ensure_adapter_powered_on()
        except trio.TooSlowError:
            hardware.fbink.emergency_print("Unable to activate Bluetooth; giving up.")
        else:
            app = Tabula(hardware, settings)
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
    # this ensures we import the rendering c extension ASAP
    from .rendering import cairo  # noqa: F401

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("markdown_it").setLevel(logging.ERROR)
    parsed = parser.parse_args(argv[1:])
    trio.run(start_tabula, parsed.settings)
    return 0
