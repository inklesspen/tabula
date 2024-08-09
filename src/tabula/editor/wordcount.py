# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import deque
from itertools import count
from typing import Any, MutableMapping, Sequence, Text

import markdown_it
import markdown_it.renderer
from markdown_it.token import Token
from markdown_it.utils import OptionsDict

from ._wordchars import WORD_CHARS

# Avoid constructing a deque each time
consumeall = deque(maxlen=0).extend


class PlainRenderer(markdown_it.renderer.RendererProtocol):
    # convert markdown to plain text, stripping out all tags
    # additionally strips out the contents of <h1> etc tags
    __output__ = "txt"

    def __init__(self, parser: markdown_it.main.MarkdownIt):
        pass

    def render(self, tokens: Sequence[Token], options: OptionsDict, env: MutableMapping) -> Any:
        result = ""

        skip = False
        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                skip = True
            elif token.type == "heading_close":
                skip = False
            elif skip or token.type == "paragraph_open":
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
    return markdown_it.MarkdownIt("commonmark", renderer_cls=PlainRenderer).render(markdown).rstrip("\n")


# based on a solution from https://stackoverflow.com/a/34404546
def count_plain_text(text: Text) -> int:
    cnt = count()
    consumeall(zip(WORD_CHARS.finditer(text), cnt, strict=False))
    return next(cnt)


def format_wordcount(wordcount: int):
    return "1 word" if wordcount == 1 else "{:,} words".format(wordcount)
