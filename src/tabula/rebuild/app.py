import sys

import trio

from .hardware import Hardware, RpcHardware
from .settings import load_settings, Settings
from .util import APP_CONTROLLER, checkpoint


class Tabula:
    hardware: Hardware

    def __init__(self, settings: Settings):
        # TODO: pick a subclass of Hardware based on some config knob
        self.settings = settings

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        event_send_channel, event_receive_channel = trio.open_memory_channel(0)
        self.hardware = RpcHardware(event_send_channel.clone())

        async with trio.open_nursery() as nursery:
            nursery.start_soon(self.dispatch_events, event_receive_channel)
            await nursery.start(self.hardware.run)
            await self.hardware.clear_screen()
            task_status.started()

    async def dispatch_events(
        self,
        receive_channel: trio.MemoryReceiveChannel,
        *,
        task_status=trio.TASK_STATUS_IGNORED
    ):
        task_status.started()
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
        APP_CONTROLLER.set(app)
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
