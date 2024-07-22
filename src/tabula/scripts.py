import argparse
import pathlib
import pprint

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
