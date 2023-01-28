# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any, MutableMapping, Sequence, Text

import cardinality
import markdown_it
import markdown_it.renderer
from markdown_it.token import Token
from markdown_it.utils import OptionsDict

from ._wordchars import WORD_CHARS


class PlainRenderer(markdown_it.renderer.RendererProtocol):
    # convert markdown to plain text, stripping out all tags
    # additionally strips out the contents of <h1> etc tags
    __output__ = "txt"

    def __init__(self, parser: markdown_it.main.MarkdownIt):
        pass

    def render(
        self, tokens: Sequence[Token], options: OptionsDict, env: MutableMapping
    ) -> Any:
        result = ""

        skip = False
        for i, token in enumerate(tokens):

            if token.type == "heading_open":
                skip = True
            elif token.type == "heading_close":
                skip = False
            elif skip:
                continue
            elif token.type == "paragraph_open":
                continue
            elif token.type == "paragraph_close":
                result += "\n\n"
            elif token.type == "inline":
                assert token.children is not None
                result += self.renderInline(token.children)
            else:
                result += self.renderToken(tokens, i)

        return result

    def renderInline(self, tokens: Sequence[Token]) -> str:
        result = ""

        for i, token in enumerate(tokens):
            if token.type == "text":
                result += tokens[i].content
            else:
                result += self.renderToken(tokens, i)

        return result

    def renderToken(self, tokens: Sequence[Token], i: int) -> str:
        token = tokens[i]
        return "\n" if token.block else ""


def make_plain_text(markdown: Text) -> Text:
    return (
        markdown_it.MarkdownIt("commonmark", renderer_cls=PlainRenderer)
        .render(markdown)
        .rstrip("\n")
    )


def count_plain_text(text: Text) -> int:
    return cardinality.count(WORD_CHARS.finditer(text))
