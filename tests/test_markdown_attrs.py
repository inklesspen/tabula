import pytest
from tabula.rendering._cairopango import ffi, lib  # type: ignore

OPEN_ATTR_END = 4294967295


def fully_free_gstring(gstring):
    lib.g_string_free(gstring, True)


def split_attr_string(attrstring):
    return [attr.strip() for attr in attrstring.splitlines()]


def test_basic_string():
    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new("hello beaſts!".encode("utf-8")), fully_free_gstring)
    assert gstr.len == 14

    lib.markdown_attrs(mstate, gstr)

    assert mstate.pos == 13
    attrs = ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8")
    assert attrs == ""


@pytest.mark.parametrize(
    "test_string,expected",
    [
        pytest.param("hello _world_!", "6 13 style italic", id="middle"),
        pytest.param("_hello_ world!", "0 7 style italic", id="beginning"),
        pytest.param("hello world_!_", "11 14 style italic", id="ending"),
    ],
)
def test_closed_italics(test_string, expected):
    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), fully_free_gstring)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert mstate.italic == ffi.NULL
    attrs = ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8")
    assert attrs == expected


def test_open_italics():
    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new("hello _wor".encode("utf-8")), fully_free_gstring)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == 10
    assert mstate.italic != ffi.NULL
    assert mstate.italic.start_index == 6
    attrs = ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8")
    assert attrs == f"6 {OPEN_ATTR_END} style italic"


@pytest.mark.parametrize(
    "test_string,expected",
    [
        pytest.param("hello **world**!", "6 15 weight semibold", id="middle"),
        pytest.param("**hello** world!", "0 9 weight semibold", id="beginning"),
        pytest.param("hello world**!**", "11 16 weight semibold", id="ending"),
    ],
)
def test_closed_bold(test_string, expected):
    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), fully_free_gstring)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert mstate.bold == ffi.NULL
    attrs = ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8")
    assert attrs == expected


@pytest.mark.parametrize(
    "test_string,expected",
    [
        pytest.param("hello **w_orl_d**!", ["6 17 weight semibold", "9 14 style italic"], id="bold_outside"),
        pytest.param("_**hello**_ world!", ["0 11 style italic", "1 10 weight semibold"], id="italic_outside"),
    ],
)
def test_nested(test_string, expected):
    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), fully_free_gstring)

    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert mstate.bold == ffi.NULL
    attrs = split_attr_string(ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8"))
    assert attrs == expected


def test_multibyte():
    test_string = "**½** — Behold _the☃ beaſts!_ — _«**Pay attention ☭ now!**»_"
    markup_string = (
        '<span weight="600">**½**</span> — Behold <i>_the☃ beaſts!_</i> — <i>_«<span weight="600">**Pay attention ☭ now!**</span>»_</i>'
    )
    fontmap = lib.pango_cairo_font_map_get_default()
    context = ffi.gc(lib.pango_font_map_create_context(fontmap), lib.g_object_unref)
    layout = ffi.gc(lib.pango_layout_new(context), lib.g_object_unref)
    lib.pango_layout_set_markup(layout, markup_string.encode("utf-8"), -1)
    markup_attrs = ffi.string(ffi.gc(lib.pango_attr_list_to_string(lib.pango_layout_get_attributes(layout)), lib.g_free)).decode("utf-8")

    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), fully_free_gstring)
    lib.markdown_attrs(mstate, gstr)
    attrs = ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8")

    assert attrs == markup_attrs


@pytest.mark.parametrize(
    "test_string,expected_attrs",
    [
        pytest.param("We slowly go back.", [], id="unstyled"),
        pytest.param("There were **two** lights", ["11 18 weight semibold"], id="style unchanged"),
        pytest.param("This is _only_", [f"8 {OPEN_ATTR_END} style italic"], id="closed italic reopened"),
        pytest.param("This **is** only _", ["5 11 weight semibold"], id="open italic removed"),
        pytest.param("Let us now **_un_bold**", [f"11 {OPEN_ATTR_END} weight semibold", "13 17 style italic"], id="closed bold reopened"),
        pytest.param("And now _the_ **", ["8 13 style italic"], id="open bold removed"),
        pytest.param("**Multibyte**: ☭", ["0 13 weight semibold"], id="multibyte backspace"),
    ],
)
def test_backspace(test_string, expected_attrs):
    mstate = ffi.new("MarkdownState*")
    gstr = ffi.gc(lib.g_string_new(test_string.encode("utf-8")), fully_free_gstring)
    lib.markdown_attrs(mstate, gstr)
    assert mstate.pos == len(test_string)
    assert gstr.len == len(test_string.encode("utf-8"))

    lib.markdown_attrs_backspace(mstate, gstr)
    assert mstate.pos == len(test_string[:-1])
    assert gstr.len == len(test_string[:-1].encode("utf-8"))
    assert ffi.string(gstr.str).decode("utf-8") == test_string[:-1]
    attrs = split_attr_string(ffi.string(ffi.gc(lib.pango_attr_list_to_string(mstate.attr_list), lib.g_free)).decode("utf-8"))
    assert attrs == expected_attrs
