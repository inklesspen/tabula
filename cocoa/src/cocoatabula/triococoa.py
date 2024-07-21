import enum
import logging
import typing

import objc
import outcome
import trio
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSBitmapImageRep,
    NSClosableWindowMask,
    NSDeviceWhiteColorSpace,
    NSGraphicsContext,
    NSImage,
    NSImageRep,
    NSImageView,
    NSMenu,
    NSMenuItem,
    NSMiniaturizableWindowMask,
    NSResizableWindowMask,
    NSResponder,
    NSTitledWindowMask,
    NSViewFrameDidChangeNotification,
    NSWindow,
)
from Foundation import (
    NSMakePoint,
    NSMakeRect,
    NSMakeSize,
    NSNotificationCenter,
    NSPoint,
    NSSize,
)
from PyObjCTools import AppHelper
from tabula.app import Tabula, parser
from tabula.commontypes import Point, Rect, ScreenInfo, ScreenRotation, Size, TouchCoordinateTransform
from tabula.device.hwtypes import AnnotatedKeyEvent, KeyboardDisconnect, KeyEvent, SetLed, TapEvent, TapPhase
from tabula.device.keyboard_consts import Key, KeyPress
from tabula.device.keystreams import make_keystream
from tabula.settings import Settings

from .keycodes import KEYCODES, MODIFIER_MAP

if typing.TYPE_CHECKING:
    from tabula.rendering.rendertypes import Rendered

logger = logging.getLogger(__name__)

NSApplicationDelegate = objc.protocolNamed("NSApplicationDelegate")
NSWindowDelegate = objc.protocolNamed("NSWindowDelegate")

# CLARA_SCREEN = ScreenInfo(size=Size(width=1072, height=1448), dpi=300)
CLARA_SCREEN_LANDSCAPE = NSMakeSize(1448, 1072)
CLARA_SCREEN_PORTRAIT = NSMakeSize(1072, 1448)


class ScreenGeometry(enum.Enum):
    LANDSCAPE = Size(width=1448, height=1072)
    PORTRAIT = Size(width=1072, height=1448)

    @enum.property
    def ns_size(self):
        return NSMakeSize(self.value.width, self.value.height)

    @enum.property
    def rotation(self):
        return ScreenRotation.PORTRAIT if self is ScreenGeometry.PORTRAIT else ScreenRotation.LANDSCAPE_PORT_RIGHT


# https://trio.readthedocs.io/en/stable/reference-lowlevel.html#using-guest-mode-to-run-trio-on-top-of-other-event-loops
# https://github.com/python-trio/trio/blob/master/src/trio/_core/_tests/test_guest_mode.py


def make_grayscale_bir(size: Size, imagedata: memoryview | None = None):
    bir = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
        (imagedata, None, None, None, None),
        size.width,
        size.height,
        8,
        1,
        False,
        False,
        NSDeviceWhiteColorSpace,
        size.width,
        0,
    )
    return bir


def northwest_to_southwest(rect: Rect, screen_size: Size):
    # The rendering system assumes the origin is in the "northwest"; upper-left.
    # But Cocoa has the origin in the "southwest".
    new_y = screen_size.height - (rect.origin.y + rect.spread.height)
    return Point(rect.origin.x, new_y)


def southwest_to_northwest(point: Point, screen_size: Size):
    # This is for a mouseclick aka "touch"
    new_y = screen_size.height - point.y
    return Point(point.x, new_y)


# Hardware needs to:
# 1. dispatch hardware events (keyboard, touchscreen, power button, battery)
#    to the app
# 2. Provide hardware info (screen info)
# 3. Render screen updates


class CocoaHardware:
    def __init__(self, settings: Settings, appdelegate: "TabulaAppDelegate", screen_geometry: ScreenGeometry):
        self.settings = settings
        self.appdelegate = appdelegate
        self.screen_geometry = screen_geometry
        self.event_channel, self.event_receive_channel = trio.open_memory_channel(1)
        self.capslock_led = False
        self.compose_led = False
        self.keystream_cancel_scope = trio.CancelScope()
        self.keystream = None
        self.keystream_send_channel = None
        self.reset_keystream()
        self.touchstream_cancel_scope = trio.CancelScope()
        self.touchstream_receive_channel = None
        self.touchstream_send_channel = None
        self.reset_touchstream()

    def handle_key_event(self, key_event: KeyEvent):
        self.keystream_send_channel.send_nowait(key_event)

    def handle_mouseclick(self, ns_point: NSPoint, down: bool):
        point = southwest_to_northwest(Point(int(ns_point.x), int(ns_point.y)), self.screen_geometry.value)
        phase = TapPhase.INITIATED if down else TapPhase.COMPLETED
        self.touchstream_send_channel.send_nowait((TapEvent(location=point, phase=phase)))

    def disconnect_keyboard(self):
        self.event_channel.send_nowait(KeyboardDisconnect())

    def get_screen_info(self) -> ScreenInfo:
        val = ScreenInfo(
            size=self.screen_geometry.value,
            dpi=300,
            rotation=self.screen_geometry.rotation,
            touch_coordinate_transform=TouchCoordinateTransform.IDENTITY,  # handled in handle_mouseclick
        )
        return val

    def set_rotation(self, sr: ScreenRotation):
        desired = (
            ScreenGeometry.LANDSCAPE
            if sr is ScreenRotation.LANDSCAPE_PORT_LEFT or sr is ScreenRotation.LANDSCAPE_PORT_RIGHT
            else ScreenGeometry.PORTRAIT
        )
        self.screen_geometry = desired
        self.appdelegate.geometryChanged()

    def display_pixels(self, imagebytes: bytes, rect: Rect):
        origin = northwest_to_southwest(rect, self.screen_geometry.value)
        # logger.info("Point %r transformed to %r", rect.origin, origin)
        point = NSMakePoint(origin.x, origin.y)
        imageview = memoryview(imagebytes)  # must live until bir is consumed
        bir = make_grayscale_bir(rect.spread, imageview)
        # We need to transform the point, actually, because Cocoa's origin is lower left
        self.appdelegate.view.drawImageRepAtPoint(bir, point)

    def display_rendered(self, rendered: "Rendered"):
        self.display_pixels(rendered.image, rendered.extent)

    def clear_screen(self):
        self.appdelegate.view.clearScreen()

    def set_led_state(self, state: SetLed):
        logger.debug("set led: %r", state)

    async def _handle_keystream(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.keystream is None:
                await trio.lowlevel.checkpoint()
                continue
            with trio.CancelScope() as cancel_scope:
                self.keystream_cancel_scope = cancel_scope
                async with self.keystream as keystream:
                    event: AnnotatedKeyEvent
                    async for event in keystream:
                        if event.is_led_able:
                            if event.annotation.capslock != self.capslock_led:
                                self.capslock_led = event.annotation.capslock
                            if event.annotation.compose != self.compose_led:
                                self.compose_led = event.annotation.compose
                        await self.event_channel.send(event)

    async def _handle_touchstream(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.touchstream_receive_channel is None:
                await trio.lowlevel.checkpoint()
                continue
            with trio.CancelScope() as cancel_scope:
                self.touchstream_cancel_scope = cancel_scope
                async for event in self.touchstream_receive_channel:
                    await self.event_channel.send(event)

    def reset_keystream(self):
        # This needs redesign.
        old_send_channel = self.keystream_send_channel
        (
            new_keystream_send_channel,
            new_keystream_receive_channel,
        ) = trio.open_memory_channel(10)
        self.keystream = make_keystream(new_keystream_receive_channel, self.settings)
        self.keystream_send_channel = new_keystream_send_channel
        if old_send_channel is not None:
            old_send_channel.close()
        self.keystream_cancel_scope.cancel()

    def reset_touchstream(self):
        # we would reset it when changing screens, for instance
        old_send_channel = self.touchstream_send_channel
        (
            new_touchstream_send_channel,
            new_touchstream_receive_channel,
        ) = trio.open_memory_channel(10)
        self.touchstream_receive_channel = new_touchstream_receive_channel
        self.touchstream_send_channel = new_touchstream_send_channel
        if old_send_channel is not None:
            old_send_channel.close()
        self.touchstream_cancel_scope.cancel()

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with trio.open_nursery() as nursery:
            task_status.started()
            nursery.start_soon(self._handle_keystream)
            nursery.start_soon(self._handle_touchstream)


class KoboView(NSImageView):
    hardware: CocoaHardware
    current_size: NSSize

    @classmethod
    def newWithHardware_(cls, hardware: CocoaHardware) -> "KoboView":
        obj = cls.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 100))
        obj.setImage_(NSImage.alloc().initWithSize_(NSMakeSize(100, 100)))
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            obj,
            objc.selector(obj.frameSizeUpdate_),
            NSViewFrameDidChangeNotification,
            obj,
        )
        obj.hardware = hardware
        return obj

    def frameSizeUpdate_(self, unused):
        # For some reason this method has to exist or else the app crashes.
        # It doesn't have to do anything, though.
        pass

    @objc.python_method
    def setTabulaScreenSize(self, size: Size):
        logger.info(f"setTabulaScreenSize: {size}")
        self.current_size = NSMakeSize(size.width, size.height)
        self.image().setSize_(self.current_size)
        self.clearScreen()

    @objc.python_method
    def drawImageRepAtPoint(self, imageRep: NSImageRep, point: NSPoint):
        img = self.image()
        mainbir = img.representations()[0]
        nsgc = NSGraphicsContext.graphicsContextWithBitmapImageRep_(mainbir)
        assert nsgc is not None
        NSGraphicsContext.setCurrentContext_(nsgc)
        imageRep.drawAtPoint_(point)
        self.setNeedsDisplayInRect_(NSMakeRect(point.x, point.y, imageRep.pixelsWide(), imageRep.pixelsHigh()))

    @objc.python_method
    def clearScreen(self):
        for rep in self.image().representations():
            self.image().removeRepresentation_(rep)
        mainbir = make_grayscale_bir(self.current_size, imagedata=None)
        # TODO: use bitmapData selector instead
        gray, _, _, _, _ = mainbir.getBitmapDataPlanes_()
        gray[:] = b"\xff" * len(gray)
        self.image().addRepresentation_(mainbir)

    def acceptsFirstResponder(self):
        return True

    def canBecomeKeyView(self):
        return True

    @objc.python_method
    def convert_window_point(self, window_point: NSPoint):
        window_size = typing.cast(NSSize, self.frame().size)
        image_size = self.current_size
        image_point = NSMakePoint(
            window_point.x * image_size.width / window_size.width, window_point.y * image_size.height / window_size.height
        )
        return image_point

    def mouseDown_(self, theEvent):
        self.hardware.handle_mouseclick(self.convert_window_point(theEvent.locationInWindow()), down=True)

    def mouseUp_(self, theEvent):
        self.hardware.handle_mouseclick(self.convert_window_point(theEvent.locationInWindow()), down=False)

    def keyDown_(self, theEvent):
        key_event = KeyEvent.pressed(KEYCODES[theEvent.keyCode()])
        self.hardware.handle_key_event(key_event)

    def keyUp_(self, theEvent):
        key_event = KeyEvent.released(KEYCODES[theEvent.keyCode()])
        self.hardware.handle_key_event(key_event)

    def flagsChanged_(self, theEvent):
        key = KEYCODES[theEvent.keyCode()]
        if key not in MODIFIER_MAP:
            return
        modifier_mask = MODIFIER_MAP[key]
        key_event = KeyEvent.pressed(key) if modifier_mask & theEvent.modifierFlags() else KeyEvent.released(key)
        self.hardware.handle_key_event(key_event)
        if key is Key.KEY_CAPSLOCK:
            # if the key was capslock, we need to synthesize the counterpart event
            # because in Cocoa we only get it once; pressed when enabled, released otherwise
            counterpart = KeyEvent.released(key) if key_event.press is KeyPress.PRESSED else KeyEvent.pressed(key)
            self.hardware.handle_key_event(counterpart)


class KoboWindowDelegate(NSResponder, protocols=[NSWindowDelegate]):
    def initWithCancelScope_(self, app_cancel_scope: trio.CancelScope):
        self = objc.super(KoboWindowDelegate, self).init()
        if self is None:
            return self

        self.app_cancel_scope = app_cancel_scope

        return self

    def windowShouldClose_(self, aWindow):
        self.app_cancel_scope.cancel()
        return True


class TabulaAppDelegate(NSResponder, protocols=[NSApplicationDelegate]):
    view: KoboView
    hardware: CocoaHardware

    def initWithCancelScope_(self, app_cancel_scope: trio.CancelScope):
        self = objc.super(TabulaAppDelegate, self).init()
        if self is None:
            return self

        self.app_cancel_scope = app_cancel_scope

        return self

    def applicationDidFinishLaunching_(self, aNotification):
        geometry = self.hardware.screen_geometry
        styleMask = NSClosableWindowMask | NSTitledWindowMask | NSMiniaturizableWindowMask | NSResizableWindowMask
        self.mainWindow = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, geometry.value.width * 0.75, geometry.value.height * 0.75), styleMask, NSBackingStoreBuffered, False
        )
        self.mainWindow.setTitle_("Tabula")
        self.mainWindowDelegate = KoboWindowDelegate.alloc().initWithCancelScope_(self.app_cancel_scope)
        self.mainWindow.setDelegate_(self.mainWindowDelegate)

        # TODO: if we add orientation flipping, remember to adjust this.
        aspect_ratio = geometry.ns_size
        # logger.info("Setting window aspect ratio to %r", aspect_ratio)
        self.mainWindow.setAspectRatio_(aspect_ratio)

        self.view = KoboView.newWithHardware_(self.hardware)
        self.view.setTabulaScreenSize(geometry.value)
        self.mainWindow.setContentView_(self.view)

        self.mainWindow.cascadeTopLeftFromPoint_(NSMakePoint(20, 20))
        self.mainWindow.makeKeyAndOrderFront_(self)
        self.mainWindow.makeFirstResponder_(self.view)
        # self.doDraw()

    @objc.python_method
    def geometryChanged(self):
        geometry = self.hardware.screen_geometry
        new_content_rect = NSMakeRect(0, 0, geometry.value.width * 0.75, geometry.value.height * 0.75)
        new_frame_rect = self.mainWindow.frameRectForContentRect_(new_content_rect)
        aspect_ratio = geometry.ns_size
        self.mainWindow.setAspectRatio_(aspect_ratio)
        self.view.setTabulaScreenSize(geometry.value)
        self.mainWindow.setFrame_display_(new_frame_rect, True)

    def requestQuit_(self, param):
        # print(f"requestQuit:{param}")
        self.app_cancel_scope.cancel()

    def disconnectKeyboard_(self, param):
        self.hardware.disconnect_keyboard()

    @objc.python_method
    @classmethod
    def start(cls, argv):
        parsed = parser.parse_args(argv[1:])
        settings = Settings.load(parsed.settings)
        appscope = trio.CancelScope()
        appdelegate = cls.alloc().initWithCancelScope_(appscope)

        hardware = CocoaHardware(settings, appdelegate, ScreenGeometry.PORTRAIT)
        appdelegate.hardware = hardware

        async def wrapped_async_fn():
            with appscope:
                app = Tabula(hardware, settings)
                await app.run()

        def done_callback(outcome: outcome.Outcome):
            try:
                print("outcome: %r" % outcome.unwrap())
            except Exception:
                logger.exception("done_callback outcome")
            AppHelper.stopEventLoop()

        trio.lowlevel.start_guest_run(
            wrapped_async_fn,
            run_sync_soon_threadsafe=AppHelper.callAfter,
            done_callback=done_callback,
        )

        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

        # menubar
        menubar = NSMenuItem.new()
        mainmenu = NSMenu.new()
        appmenu = NSMenu.new()
        menubar.setSubmenu_(appmenu)
        quititem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit Tabula", objc.selector(appdelegate.requestQuit_), "q")
        keyboarditem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Disconnect Keyboard", objc.selector(appdelegate.disconnectKeyboard_), ""
        )
        # swapitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Swap", objc.selector(appdelegate.swapOrientation_), "")
        appmenu.addItem_(quititem)
        appmenu.addItem_(keyboarditem)
        mainmenu.addItem_(menubar)
        app.setMainMenu_(mainmenu)

        app.setDelegate_(appdelegate)
        app.run()  # never returns until the end


def configure_logging(root_level=logging.DEBUG):
    handler = logging.StreamHandler()
    handler.setLevel(root_level)
    logging.basicConfig(handlers=[handler])
    logging.getLogger("tabula").setLevel(root_level)


def start():
    configure_logging()
    AppHelper.runEventLoop(main=TabulaAppDelegate.start)
