from ..rendering._cairopango import ffi, lib  # type: ignore
from ..rendering.markup import CURSOR, make_markup


def fully_free_gstring(gstring):
    lib.g_string_free(gstring, True)


DRACULA = """_3 May. Bistritz._⁠—Left Munich at 8:35 p.m., on 1st May, arriving at Vienna early next morning; should have arrived at 6:46, but train was an hour late. Buda-Pesth seems a wonderful place, from the glimpse which I got of it from the train and the little I could walk through the streets. I feared to go very far from the station, as we had arrived late and would start as near the correct time as possible. The impression I had was that we were leaving the West and entering the East; the most western of splendid bridges over the Danube, which is here of noble width and depth, took us among the traditions of Turkish rule."""  # noqa: E501


fontmap = lib.pango_cairo_font_map_get_default()
context = ffi.gc(lib.pango_font_map_create_context(fontmap), lib.g_object_unref)
layout = ffi.gc(lib.pango_layout_new(context), lib.g_object_unref)


def undertest():
    mystr = ""
    for letter in DRACULA:
        mystr += letter
        markup = make_markup(mystr + CURSOR)
        lib.pango_layout_set_markup(layout, markup.encode("utf-8"), -1)
