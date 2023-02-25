import argparse
import decimal
import json
import pathlib

from .rendering._cairopango import ffi, lib as clib
from .settings import Settings

# Tabula Quattro 10: 54.166015625  -> 55
# Tabula Quattro 9.5: 51.45703125 -> 52
# Tabula Quattro 9: 48.7490234375 -> 49
# Tabula Quattro 8.5: 46.041015625 -> 46
# Tabula Quattro 8: 43.33203125 -> 43
# Tabula Quattro 7.5: 40.6240234375 -> 40
# Tabula Quattro 7: 37.916015625 -> 37
FONT_HEIGHT_STOPS = (37, 40, 43, 46, 49, 52, 55)


def _font_height(font_str, fontmap, context, language):
    with ffi.gc(
        clib.pango_font_description_from_string(font_str.encode("utf-8")),
        clib.pango_font_description_free,
    ) as font_description, ffi.gc(
        clib.pango_font_map_load_font(fontmap, context, font_description),
        clib.g_object_unref,
    ) as loaded_font, ffi.gc(
        clib.pango_font_get_metrics(loaded_font, language),
        clib.pango_font_metrics_unref,
    ) as font_metrics:
        return clib.pango_font_metrics_get_height(font_metrics) / clib.PANGO_SCALE


def font_sizes(font, dpi=300):
    fontmap = clib.pango_cairo_font_map_get_default()
    context = ffi.gc(clib.pango_font_map_create_context(fontmap), clib.g_object_unref)
    language = clib.pango_language_from_string("en-us".encode("ascii"))
    clib.pango_cairo_font_map_set_resolution(
        ffi.cast("PangoCairoFontMap *", fontmap), dpi
    )
    sizes = []
    size = decimal.Decimal("4")
    for height_stop in FONT_HEIGHT_STOPS:
        current_height = 0
        while current_height < height_stop:
            size += decimal.Decimal("0.1")
            current_height = _font_height(f"{font} {size}", fontmap, context, language)
        sizes.append(str(size))
    return sizes


font_sizes_parser = argparse.ArgumentParser()
font_sizes_parser.add_argument("font")
font_sizes_parser.add_argument("--dpi", type=int)


def font_sizes_cli():
    args = font_sizes_parser.parse_args()
    print(args.font)
    print(json.dumps(font_sizes(**vars(args))))


def write_settings_json(dest: pathlib.Path):
    Settings.for_test().save(dest)


write_settings_parser = argparse.ArgumentParser()
write_settings_parser.add_argument("dest", type=pathlib.Path)


def write_settings_json_cli():
    args = write_settings_parser.parse_args()
    write_settings_json(args.dest)
