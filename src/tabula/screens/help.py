# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later OR CC-BY-SA-4.0

import typing

from ..device.hwtypes import AnnotatedKeyEvent, Key
from ..commontypes import Point, Rect
from ..rendering.rendertypes import Rendered, CairoColor
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout

from .base import TargetDialog
from .dialogs import Dialog
from ..util import TABULA, Future

if typing.TYPE_CHECKING:
    from ..settings import Settings
    from ..commontypes import ScreenInfo

ROMAN_FACE = "B612 8"
# Pango Markup has the attribute <tt>, which has the effect of setting font-family to Monospace.
# So we can just do `<span face="Some Monospace Family">Something</span>`
TT_FACE = "B612 Mono"
# There's a compose key symbol in unicode (U+2384) but most fonts don't have a glyph for it.
# One such font is Noto Sans Symbols; alpine package 'font-noto'
SYMBOL_FACE = "Noto Sans Symbols"

HELP_TEMPLATE = f"""\
Tabula is a portable prose-oriented distraction-free drafting tool.

The cursor is locked at the end of the document. You can delete characters with Backspace, but only within the current paragraph; once you \
hit Enter, you canʼt go back.

You can enter special characters through the use of the Compose key and <b>compose sequences</b>. On this machine, the Compose key is \
{{composekey}}. Double-tap the Compose key for examples of common compose sequences.

Press <span face="{TT_FACE}">F8</span> to start or end a writing sprint.

Press <span face="{TT_FACE}">F12</span> to open the system menu.

<small>This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as \
published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.</small>
"""

COMPOSES_TEMPLATE = f"""\
To enter a compose sequence, press and release the Compose key (<span face="{SYMBOL_FACE}">\u2384</span>), followed by each key of the \
sequence. You donʼt need to hold down the keys.

On this machine, the Compose key (<span face="{SYMBOL_FACE}">\u2384</span>) is {{composekey}}.

Here are some commonly used compose sequences:
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> - a</span> → ā (and similar for other vowels)
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> ^ a</span> → â (and similar for other vowels)
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> ' a</span> → á (and similar for other vowels)
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> ` a</span> → à (and similar for other vowels)
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> ~ n</span> → ñ

<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> &#60; '</span> → \u2018 (can be given in either order)
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> &#62; '</span> → \u2019
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> &#60; "</span> → \u201C (can be given in either order)
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> &#62; "</span> → \u201D
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> &#60; &#60;</span> → \u00AB
<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> &#62; &#62;</span> → \u00BB
"""

# We now use U+02BC by default for the apostrophe key, since we want to always use it.
# <span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> ' '</span> → \u02BC (modifier letter apostrophe)


class Help(Dialog):
    def __init__(
        self,
        *,
        settings: "Settings",
        screen_info: "ScreenInfo",
    ):
        self.settings = settings
        self.pango = Pango(dpi=screen_info.dpi)
        self.screen_size = screen_info.size
        self.future = Future()

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=False)
        screen = self.render()
        app.hardware.display_rendered(screen)

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        if event.key is Key.KEY_ESC:
            self.future.finalize(None)
        if event.key is Key.KEY_F2 or event.key is Key.SYNTHETIC_COMPOSE_DOUBLETAP:
            self.future.finalize(TargetDialog.ComposeHelp)

    def render(self) -> Rendered:
        # TODO: render an X in the corner or something
        text = HELP_TEMPLATE.format(composekey=self.settings.compose_key_description)
        with Cairo(self.screen_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            text_width = self.screen_size.width - 20
            with PangoLayout(pango=self.pango, width=text_width) as layout:
                layout.set_font(ROMAN_FACE)
                layout.set_content(text, is_markup=True)
                cairo.move_to(Point(x=10, y=10))
                cairo.set_draw_color(CairoColor.BLACK)
                layout.render(cairo)
            rendered = Rendered(
                image=cairo.get_image_bytes(),
                extent=Rect(origin=Point.zeroes(), spread=self.screen_size),
            )
        return rendered


class ComposeHelp(Dialog):
    def __init__(
        self,
        *,
        settings: "Settings",
        screen_info: "ScreenInfo",
    ):
        self.settings = settings
        self.pango = Pango(dpi=screen_info.dpi)
        self.screen_size = screen_info.size
        self.future = Future()

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=False)
        screen = self.render()
        app.hardware.display_rendered(screen)

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        if event.key is Key.KEY_ESC:
            self.future.finalize(None)
        if event.key is Key.KEY_F1:
            self.future.finalize(TargetDialog.Help)

    def render(self) -> Rendered:
        # TODO: render an X in the corner or something
        text = COMPOSES_TEMPLATE.format(composekey=self.settings.compose_key_description)
        with Cairo(self.screen_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            text_width = self.screen_size.width - 20
            with PangoLayout(pango=self.pango, width=text_width) as layout:
                layout.set_font(ROMAN_FACE)
                layout.set_content(text, is_markup=True)
                cairo.move_to(Point(x=10, y=10))
                cairo.set_draw_color(CairoColor.BLACK)
                layout.render(cairo)
            rendered = Rendered(
                image=cairo.get_image_bytes(),
                extent=Rect(origin=Point.zeroes(), spread=self.screen_size),
            )
        return rendered
