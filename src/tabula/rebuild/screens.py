import abc

import msgspec
import trio

from .hwtypes import KeyEvent, TouchReport


class Screen(abc.ABC):
    async def on_raw_key(self, event: KeyEvent):
        pass

    async def on_touch(self, report: TouchReport):
        pass


class KeyboardDetect(Screen):
    """Displays on startup or if the keyboards vanish. User must press a key to continue, or tap a screen button to quit."""

    pass


class Drafting(Screen):
    pass


class Help(Screen):
    pass
