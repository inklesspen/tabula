from ..rendering._cairopango import ffi, lib  # type: ignore

DRACULA = """_3 May. Bistritz._⁠—Left Munich at 8:35 p.m., on 1st May, arriving at Vienna early next morning; should have arrived at 6:46, but train was an hour late. Buda-Pesth seems a wonderful place, from the glimpse which I got of it from the train and the little I could walk through the streets. I feared to go very far from the station, as we had arrived late and would start as near the correct time as possible. The impression I had was that we were leaving the West and entering the East; the most western of splendid bridges over the Danube, which is here of noble width and depth, took us among the traditions of Turkish rule."""  # noqa: E501

fontmap = lib.pango_cairo_font_map_get_default()
context = ffi.gc(lib.pango_font_map_create_context(fontmap), lib.g_object_unref)
layout = ffi.gc(lib.pango_layout_new(context), lib.g_object_unref)


def undertest():
    gstr = ffi.gc(lib.g_string_sized_new(len(DRACULA)), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    for letter in DRACULA:
        lib.g_string_append_unichar(gstr, ord(letter))
        lib.markdown_attrs(mstate, gstr)
        lib.setup_cursor(mstate, gstr)
        lib.pango_layout_set_text(layout, gstr.str, gstr.len)
        lib.pango_layout_set_attributes(layout, mstate.attr_list)
        lib.cleanup_cursor(mstate, gstr)
