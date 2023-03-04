import typing

import trio

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase
from ..commontypes import Point, Size, Rect
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from ..rendering.rendertypes import Rendered, Alignment, CairoColor

from .base import Close, Shutdown, Screen
from .widgets import ButtonState, Button

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..commontypes import ScreenInfo


class KeyboardDetect(Screen):
    """Displays on startup or if the keyboards vanish. User must press a key to continue, or tap a screen button to quit."""

    def __init__(
        self,
        *,
        settings: "Settings",
        hardware: "Hardware",
        screen_info: "ScreenInfo",
    ):
        self.settings = settings
        self.hardware = hardware
        self.pango = Pango(dpi=screen_info.dpi)
        screen_size = screen_info.size

        button_size = Size(width=400, height=100)
        self.button = Button(
            self.pango,
            button_text="Exit",
            button_size=button_size,
            corner_radius=50,
            font="B612 10",
            screen_location=Point(
                x=(screen_size.width - button_size.width) // 2, y=960
            ),
        )

        with Cairo(screen_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            cairo.move_to(Point(x=0, y=160))
            with PangoLayout(
                pango=self.pango, width=screen_size.width, alignment=Alignment.CENTER
            ) as layout:
                layout.set_font("Crimson Pro 48")
                layout.set_content("Tabula")
                layout.render(cairo)

            cairo.move_to(Point(x=50, y=640))
            with PangoLayout(pango=self.pango, width=screen_size.width - 100) as layout:
                layout.set_font("Crimson Pro 12")
                layout.set_content(
                    "Connect a keyboard and press a key to continue, or tap the button to exit."
                )
                layout.render(cairo)

            cairo.move_to(Point(x=0, y=1280))
            with PangoLayout(
                pango=self.pango, width=screen_size.width, alignment=Alignment.CENTER
            ) as layout:
                layout.set_font("Crimson Pro 8")
                layout.set_content("Presented by Straylight Labs")
                layout.render(cairo)

            self.button.paste_onto_cairo(cairo)
            self.initial_screen = Rendered(
                image=cairo.get_image_bytes(),
                extent=Rect(origin=Point.zeroes(), spread=screen_size),
            )

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        await self.hardware.display_rendered(self.initial_screen)
        while True:
            event = await event_channel.receive()
            match event:
                case AnnotatedKeyEvent():
                    return Close()
                case TapEvent():
                    if (
                        event.phase is TapPhase.COMPLETED
                        and event.location in self.button
                    ):
                        await self.hardware.display_rendered(
                            self.button.render(override_state=ButtonState.PRESSED)
                        )
                        return Shutdown()
