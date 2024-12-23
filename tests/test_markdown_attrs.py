import pytest

from tabula.rendering._cairopango import ffi, lib  # type: ignore
from tabula.rendering.pango import markdown_attrs_backspace as python_markdown_attrs_backspace

OPEN_ATTR_END = 4294967295
PARKED_CURSOR_ALPHA = "0 0 foreground-alpha 32767"
PARKED_COMPOSE_UNDERLINE = "0 0 underline single"
PARKED_ATTRS = [PARKED_COMPOSE_UNDERLINE, PARKED_CURSOR_ALPHA]
MARKUP_CURSOR = '<span alpha="50%">_</span>'


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
    assert attrs == [*PARKED_ATTRS, f"6 {OPEN_ATTR_END} style italic"]


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
    "backspace_func",
    [pytest.param(lib.markdown_attrs_backspace, id="c impl"), pytest.param(python_markdown_attrs_backspace, id="python impl")],
)
@pytest.mark.parametrize(
    "test_string,expected_attrs,should_have_bold,should_have_italic",
    [
        pytest.param("We slowly go back.", [], False, False, id="unstyled"),
        pytest.param("There were **two** lights", ["11 18 weight semibold"], False, False, id="style unchanged"),
        pytest.param("This is _only_", [f"8 {OPEN_ATTR_END} style italic"], False, True, id="closed italic reopened"),
        pytest.param("This **is** only _", ["5 11 weight semibold"], False, False, id="open italic removed"),
        pytest.param(
            "Let us now **_un_bold**", [f"11 {OPEN_ATTR_END} weight semibold", "13 17 style italic"], True, False, id="closed bold reopened"
        ),
        pytest.param("And now _the_ **", ["8 13 style italic"], False, False, id="open bold removed"),
        pytest.param("**Multibyte**: ☭", ["0 13 weight semibold"], False, False, id="multibyte backspace"),
        pytest.param("This is _only_,", ["8 14 style italic"], False, False, id="closed italic should stay closed"),
        pytest.param("This is **only**,", ["8 16 weight semibold"], False, False, id="closed bold should stay closed"),
    ],
)
def test_backspace(backspace_func, test_string, expected_attrs, should_have_bold, should_have_italic):
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert gstr.len == len(test_string.encode("utf-8"))

    backspace_func(mstate, gstr)
    assert mstate.pos == len(test_string[:-1])
    assert gstr.len == len(test_string[:-1].encode("utf-8"))
    assert ffi.string(gstr.str).decode("utf-8") == test_string[:-1]
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == PARKED_ATTRS + expected_attrs
    assert bool(mstate.bold) == should_have_bold
    assert bool(mstate.italic) == should_have_italic


@pytest.mark.parametrize(
    "backspace_func",
    [pytest.param(lib.markdown_attrs_backspace, id="c impl"), pytest.param(python_markdown_attrs_backspace, id="python impl")],
)
def test_reopen_then_close(backspace_func):
    test_string = "Let us now **_un_bold**"
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), lib.fully_free_g_string)
    mstate = ffi.gc(lib.markdown_state_new(gstr), lib.markdown_state_free)
    lib.markdown_attrs(mstate, gstr)

    backspace_func(mstate, gstr)
    assert mstate.pos == len(test_string[:-1])
    assert gstr.len == len(test_string[:-1].encode("utf-8"))
    assert ffi.string(gstr.str).decode("utf-8") == test_string[:-1]
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == [*PARKED_ATTRS, f"11 {OPEN_ATTR_END} weight semibold", "13 17 style italic"]

    # now close it again!
    lib.g_string_append_unichar(gstr, ord("*"))
    lib.markdown_attrs(mstate, gstr)
    attrs = get_split_attrs(mstate.attr_list)
    assert attrs == [*PARKED_ATTRS, "11 23 weight semibold", "13 17 style italic"]


def test_cursor():
    test_string = "You should be writing."

    markup_string = test_string + MARKUP_CURSOR
    fontmap = lib.pango_cairo_font_map_get_default()
    context = ffi.gc(lib.pango_font_map_create_context(fontmap), lib.g_object_unref)
    layout = ffi.gc(lib.pango_layout_new(context), lib.g_object_unref)
    lib.pango_layout_set_markup(layout, markup_string.encode("utf-8"), -1)
    markup_attrs = [PARKED_COMPOSE_UNDERLINE, *get_split_attrs(lib.pango_layout_get_attributes(layout))]

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
