import logging
import typing

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase
from ..commontypes import Point, Size
from ..rendering.fonts import SERIF
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from ..rendering.rendertypes import Alignment, CairoColor

from .dialogs import Dialog
from .widgets import ButtonState, Button
from ..util import TABULA, Future

if typing.TYPE_CHECKING:
    from ..settings import Settings
    from ..commontypes import ScreenInfo


logger = logging.getLogger(__name__)


class KeyboardDetectDialog(Dialog):
    def __init__(self, *, settings: "Settings", screen_info: "ScreenInfo"):
        self.settings = settings
        self.future = Future()

        self.pango = Pango(dpi=screen_info.dpi)
        screen_size = screen_info.size

        button_size = Size(width=400, height=100)
        self.button = Button.create(
            self.pango,
            button_text="Exit",
            button_size=button_size,
            corner_radius=50,
            font="B612 10",
            screen_location=Point(x=(screen_size.width - button_size.width) // 2, y=960),
        )

        with Cairo(screen_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            cairo.move_to(Point(x=0, y=160))
            with PangoLayout(pango=self.pango, width=screen_size.width, alignment=Alignment.CENTER) as layout:
                layout.set_font(f"{SERIF} 48")
                layout.set_content("Tabula")
                layout.render(cairo)

            cairo.move_to(Point(x=50, y=640))
            with PangoLayout(pango=self.pango, width=screen_size.width - 100, alignment=Alignment.CENTER) as layout:
                layout.set_font(f"{SERIF} 12")
                layout.set_content("Connect a keyboard and press a key to continue, or tap the button to exit.")
                layout.render(cairo)

            cairo.move_to(Point(x=0, y=1280))
            with PangoLayout(pango=self.pango, width=screen_size.width, alignment=Alignment.CENTER) as layout:
                layout.set_font(f"{SERIF} 8")
                layout.set_content("Presented by Straylight Labs")
                layout.render(cairo)

            self.button.paste_onto_cairo(cairo)
            self.initial_screen = cairo.get_rendered(origin=Point.zeroes())

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=False)
        app.hardware.display_rendered(self.initial_screen)

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        self.future.finalize(None)

    async def handle_tap_event(self, event: TapEvent):
        app = TABULA.get()
        if event.phase is TapPhase.COMPLETED and event.location in self.button:
            app.hardware.display_rendered(self.button.render(override_state=ButtonState.PRESSED))
            await app.shutdown()
