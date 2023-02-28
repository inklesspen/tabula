import abc
import typing

import trio

from ..device.hwtypes import TapEvent, TapPhase, KeyboardDisconnect
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, Alignment, WrapMode

from .base import Modal, RetVal, DialogResult, TargetScreen

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..rendering.renderer import Renderer


class Dialog(abc.ABC):
    def __init__(
        self,
        *,
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        self.renderer = renderer
        self.hardware = hardware

    @abc.abstractmethod
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        ...


class OkDialog(Dialog):
    def __init__(
        self,
        *,
        renderer: "Renderer",
        hardware: "Hardware",
        message: str,
    ):
        super().__init__(
            renderer=renderer,
            hardware=hardware,
        )
        self.message = message

        screen_size = self.renderer.screen_info.size
        spread = Size(width=400, height=100)
        origin = Point(x=(screen_size.width - spread.width) / 2, y=960)
        self.button_rect = Rect(origin=origin, spread=spread)

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        result = DialogResult(value=None)
        screen = self.make_screen()
        await self.hardware.display_pixels(screen.image, screen.extent)
        while True:
            event = await event_channel.receive()
            match event:
                case TapEvent():
                    if (
                        event.location in self.button_rect
                        and event.phase is TapPhase.COMPLETED
                    ):
                        return result
                case KeyboardDisconnect():
                    # wait until we get a tap in the right place, then
                    # close this dialog and switch to keyboard detect
                    result = Modal(TargetScreen.KeyboardDetect)

    def make_screen(self):
        # TODO: consider making it smaller and adding a border box?
        screen_size = self.renderer.screen_info.size
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)

            self.renderer.move_to(cairo_context, Point(x=0, y=160))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 48",
                "Tabula",
                alignment=Alignment.CENTER,
                width=screen_size.width,
            )

            self.renderer.move_to(cairo_context, Point(x=0, y=640))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 12",
                self.message,
                alignment=Alignment.CENTER,
                wrap=WrapMode.WORD,
                width=screen_size.width,
            )

            self.renderer.button(
                cairo_context, text="OK", font="B612 10", rect=self.button_rect
            )

            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point.zeroes(), spread=screen_size)
        )


class YesNoDialog(Dialog):
    def __init__(
        self,
        *,
        renderer: "Renderer",
        hardware: "Hardware",
        message: str,
    ):
        super().__init__(
            renderer=renderer,
            hardware=hardware,
        )
        self.message = message

        button_size = Size(width=400, height=100)
        self.no_rect = Rect(origin=Point(x=100, y=960), spread=button_size)
        self.yes_rect = Rect(
            origin=Point(x=self.renderer.screen_info.size.width - 500, y=960),
            spread=button_size,
        )

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        screen = self.make_screen()
        await self.hardware.display_pixels(screen.image, screen.extent)
        while True:
            event = await event_channel.receive()
            match event:
                case TapEvent():
                    if event.phase is TapPhase.COMPLETED:
                        if event.location in self.no_rect:
                            return DialogResult(value=False)
                        if event.location in self.yes_rect:
                            return DialogResult(value=True)
                case KeyboardDisconnect():
                    # return the keyboarddetect right away, instead of
                    # waiting for a result.
                    return Modal(TargetScreen.KeyboardDetect)

    def make_screen(self):
        # TODO: consider making it smaller and adding a border box?
        screen_size = self.renderer.screen_info.size
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)

            self.renderer.move_to(cairo_context, Point(x=0, y=160))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 48",
                "Tabula",
                alignment=Alignment.CENTER,
                width=screen_size.width,
            )

            self.renderer.move_to(cairo_context, Point(x=0, y=640))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 12",
                self.message,
                alignment=Alignment.CENTER,
                wrap=WrapMode.WORD,
                width=screen_size.width,
            )

            self.renderer.button(
                cairo_context, text="No", font="B612 10", rect=self.no_rect
            )
            self.renderer.button(
                cairo_context, text="Yes", font="B612 10", rect=self.yes_rect
            )

            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point.zeroes(), spread=screen_size)
        )
