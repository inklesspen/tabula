import argparse
import pathlib
import pprint

import trio

from .device.hardware import Hardware
from .rendering.fontconfig import setup_fontconfig
from .rendering.pango import Pango
from .settings import Settings


def list_fonts(font_path):
    with setup_fontconfig(font_path):
        pango = Pango()
        fonts = {"all fonts": pango.list_available_fonts(), "drafting fonts": pango.list_drafting_fonts()}
        pprint.pprint(fonts)


list_fonts_parser = argparse.ArgumentParser()
list_fonts_config_group = list_fonts_parser.add_mutually_exclusive_group(required=True)
list_fonts_config_group.add_argument("--settings", type=pathlib.Path)
list_fonts_config_group.add_argument("--userfonts", type=pathlib.Path)


def list_fonts_cli():
    args = list_fonts_parser.parse_args()
    if args.settings is not None:
        settings = Settings.load(args.settings)
        font_path = settings.font_path
    else:
        font_path = args.userfonts
    list_fonts(font_path.absolute())


kobo_events_parser = argparse.ArgumentParser()
kobo_events_parser.add_argument("settings", type=pathlib.Path)


def print_kobo_events():
    settings = Settings.load(kobo_events_parser.parse_args().settings)

    async def runner():
        async with trio.open_nursery() as nursery:
            hardware = Hardware(settings=settings)
            await nursery.start(hardware.run)
            print(hardware.get_screen_info())
            await hardware.print_events()

    trio.run(runner)
