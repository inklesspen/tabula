# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import markdown_it

from ._cairopango import ffi, lib  # type: ignore

# https://en.wikipedia.org/wiki/Macron_below
# https://en.wikipedia.org/wiki/Underscore
CURSOR = '<span alpha="50%">_</span>'

run_splitter = markdown_it.MarkdownIt("zero").enable("emphasis")


def make_markup(markdown):
    collect = []
    tokens = run_splitter.parseInline(markdown)
    if len(tokens) != 1 or tokens[0].type != "inline":
        raise TypeError("Expected single inline")
    tokens = tokens[0].children
    for token in tokens:
        if token.type == "em_open":
            collect.append(token.markup)
            collect.append("<i>")
        elif token.type == "em_close":
            collect.append("</i>")
            collect.append(token.markup)
        elif token.type == "strong_open":
            collect.append(token.markup)
            collect.append("<b>")
        elif token.type == "strong_close":
            collect.append("</b>")
            collect.append(token.markup)
        elif token.type == "text":
            collect.append(escape_for_markup(token.content))
        else:
            raise TypeError("Unexpected token type %r" % token)
    return "".join(collect)


def escape_for_markup(text):
    with ffi.gc(lib.g_markup_escape_text(text.encode("utf-8"), -1), lib.g_free) as result:
        return ffi.string(result).decode("utf-8")
