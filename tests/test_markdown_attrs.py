import pytest
from tabula.rendering._cairopango import ffi, lib  # type: ignore
from tabula.rendering.markup import CURSOR

OPEN_ATTR_END = 4294967295
PARKED_CURSOR_ALPHA = "0 0 foreground-alpha 32767"
PARKED_COMPOSE_UNDERLINE = "0 0 underline single"
PARKED_ATTRS = [PARKED_CURSOR_ALPHA, PARKED_COMPOSE_UNDERLINE]


def split_attr_string(attrstring):
    return [attr.strip() for attr in attrstring.splitlines()]


def get_split_attrs(attr_list):
    return split_attr_string(ffi.string(ffi.gc(lib.pango_attr_list_to_string(attr_list), lib.g_free)).decode("utf-8"))


def test_basic_string():
    gstr = ffi.gc(lib.g_string_new("hello beaſts!".encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    assert gstr.len == 14

    lib.markdown_attrs(mstate, gstr)

    assert mstate.pos == 13
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS


@pytest.mark.parametrize(
    "test_string,expected",
    [
        pytest.param("hello _world_!", ["6 13 style italic"], id="middle"),
        pytest.param("_hello_ world!", ["0 7 style italic"], id="beginning"),
        pytest.param("hello world_!_", ["11 14 style italic"], id="ending"),
    ],
)
def test_closed_italics(test_string, expected):
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert mstate.italic == ffi.NULL
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS + expected


def test_open_italics():
    gstr = ffi.gc(lib.g_string_new("hello _wor".encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == 10
    assert mstate.italic != ffi.NULL
    assert mstate.italic.start_index == 6
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS + [f"6 {OPEN_ATTR_END} style italic"]


@pytest.mark.parametrize(
    "test_string,expected",
    [
        pytest.param("hello **world**!", ["6 15 weight semibold"], id="middle"),
        pytest.param("**hello** world!", ["0 9 weight semibold"], id="beginning"),
        pytest.param("hello world**!**", ["11 16 weight semibold"], id="ending"),
    ],
)
def test_closed_bold(test_string, expected):
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert mstate.bold == ffi.NULL
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS + expected


@pytest.mark.parametrize(
    "test_string,expected",
    [
        pytest.param("hello **w_orl_d**!", ["6 17 weight semibold", "9 14 style italic"], id="bold_outside"),
        pytest.param("_**hello**_ world!", ["0 11 style italic", "1 10 weight semibold"], id="italic_outside"),
    ],
)
def test_nested(test_string, expected):
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert mstate.bold == ffi.NULL
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS + expected


def test_multibyte():
    test_string = "**½** — Behold _the☃ beaſts!_ — _«**Pay attention ☭ now!**»_"
    markup_string = (
        '<span weight="600">**½**</span> — Behold <i>_the☃ beaſts!_</i> — <i>_«<span weight="600">**Pay attention ☭ now!**</span>»_</i>'
    )
    fontmap = lib.pango_cairo_font_map_get_default()
    context = ffi.gc(lib.pango_font_map_create_context(fontmap), lib.g_object_unref)
    layout = ffi.gc(lib.pango_layout_new(context), lib.g_object_unref)
    lib.pango_layout_set_markup(layout, markup_string.encode("utf-8"), -1)
    markup_attrs = PARKED_ATTRS + get_split_attrs(lib.pango_layout_get_attributes(layout))

    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    lib.markdown_attrs(mstate, gstr)
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == markup_attrs


@pytest.mark.parametrize(
    "test_string,expected_attrs",
    [
        pytest.param(
            "We slowly go back.",
            [],
            id="unstyled",
        ),
        pytest.param("There were **two** lights", ["11 18 weight semibold"], id="style unchanged"),
        pytest.param("This is _only_", [f"8 {OPEN_ATTR_END} style italic"], id="closed italic reopened"),
        pytest.param("This **is** only _", ["5 11 weight semibold"], id="open italic removed"),
        pytest.param(
            "Let us now **_un_bold**",
            [f"11 {OPEN_ATTR_END} weight semibold", "13 17 style italic"],
            id="closed bold reopened",
        ),
        pytest.param("And now _the_ **", ["8 13 style italic"], id="open bold removed"),
        pytest.param("**Multibyte**: ☭", ["0 13 weight semibold"], id="multibyte backspace"),
    ],
)
def test_backspace(test_string, expected_attrs):
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert gstr.len == len(test_string.encode("utf-8"))

    lib.markdown_attrs_backspace(mstate, gstr)
    assert mstate.pos == len(test_string[:-1])
    assert gstr.len == len(test_string[:-1].encode("utf-8"))
    assert ffi.string(gstr.str).decode("utf-8") == test_string[:-1]
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS + expected_attrs


def test_cursor():
    test_string = "You should be writing."

    markup_string = test_string + CURSOR
    fontmap = lib.pango_cairo_font_map_get_default()
    context = ffi.gc(lib.pango_font_map_create_context(fontmap), lib.g_object_unref)
    layout = ffi.gc(lib.pango_layout_new(context), lib.g_object_unref)
    lib.pango_layout_set_markup(layout, markup_string.encode("utf-8"), -1)
    markup_attrs = get_split_attrs(lib.pango_layout_get_attributes(layout)) + [PARKED_COMPOSE_UNDERLINE]

    gstr = ffi.gc(lib.g_string_new_len(test_string.encode("utf-8"), len(test_string.encode("utf-8"))), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    lib.markdown_attrs(mstate, gstr)

    lib.setup_cursor(mstate, gstr)
    combined_string = ffi.string(gstr.str).decode("utf-8")
    assert combined_string == "You should be writing._"

    combined_attrs = get_split_attrs(mstate.attr_list)
    assert combined_attrs == markup_attrs
    lib.cleanup_cursor(mstate, gstr)
    orig_string = ffi.string(gstr.str).decode("utf-8")
    assert orig_string == "You should be writing."
    assert gstr.len == 22
    orig_attrs = get_split_attrs(mstate.attr_list)
    assert orig_attrs == PARKED_ATTRS
