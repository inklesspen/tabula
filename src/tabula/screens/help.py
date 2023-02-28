# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later OR CC-BY-SA-4.0

import typing

import trio

from ..device.hwtypes import (
    AnnotatedKeyEvent,
    TapEvent,
    TapPhase,
    Key,
    KeyboardDisconnect,
)
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, CairoColor
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout

from .base import Modal, RetVal, TargetScreen, Screen, Close, Switch

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer

ROMAN_FACE = "B612 8"
# Pango Markup has the attribute <tt>, which has the effect of setting font-family to Monospace.
# So we can just do `<span face="Some Monospace Family">Something</span>`
TT_FACE = "B612 Mono"
# There's a compose key symbol in unicode (U+2384) but most fonts don't have a glyph for it.
# One such font is Noto Sans Symbols; alpine package 'font-noto'
SYMBOL_FACE = "Noto Sans Symbols"

HELP = """\
Tabula is a portable prose-oriented distraction-free drafting tool.

The cursor is locked at the end of the document. You can delete characters with Backspace, but only within the current paragraph; once you hit Enter, you canʼt go back.

You can enter special characters through the use of <b>compose sequences</b>. Press <span face="{TT_FACE}">TBD</span> for examples of common compose sequences.

Press <span face="{TT_FACE}">TBD</span> to start or end a writing sprint.

Press <span face="{TT_FACE}">F12</span> to open the system menu.

<small>This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.</small>
"""

COMPOSES_TEMPLATE = f"""\
To enter a compose sequence, press and release the Compose key (<span face="{SYMBOL_FACE}">\u2384</span>), followed by each key of the sequence. You donʼt need to hold down the keys.

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

<span face="{SYMBOL_FACE}">\u2384</span><span face="{TT_FACE}"> ' '</span> → \u02BC (modifier letter apostrophe)
"""


class Help(Screen):
    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.pango = Pango(dpi=renderer.screen_info.dpi)
        self.screen_size = self.renderer.screen_info.size

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=False)
        screen = self.render()
        await self.hardware.display_rendered(screen)
        while True:
            event = await event_channel.receive()
            match event:
                # TODO: handle a tap on the X
                case AnnotatedKeyEvent():
                    if event.key is Key.KEY_ESC:
                        return Close()
                    if event.key is Key.KEY_F2:
                        # or whatever key we use for composehelp
                        return Switch(TargetScreen.ComposeHelp)
                case KeyboardDisconnect():
                    return Modal(TargetScreen.KeyboardDetect)

    def render(self) -> Rendered:
        # TODO: render an X in the corner or something
        with Cairo(self.screen_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            text_width = self.screen_size.width - 20
            with PangoLayout(pango=self.pango, width=text_width) as layout:
                layout.set_font(ROMAN_FACE)
                layout.set_content(HELP, is_markup=True)
                cairo.move_to(Point(x=10, y=10))
                cairo.set_draw_color(CairoColor.BLACK)
                layout.render(cairo)
            rendered = Rendered(
                image=cairo.get_image_bytes(),
                extent=Rect(origin=Point.zeroes(), spread=self.screen_size),
            )
        return rendered


class ComposeHelp(Screen):
    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.pango = Pango(dpi=renderer.screen_info.dpi)
        self.screen_size = self.renderer.screen_info.size

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=False)
        screen = self.render()
        await self.hardware.display_rendered(screen)
        while True:
            event = await event_channel.receive()
            match event:
                # TODO: handle a tap on the X
                case AnnotatedKeyEvent():
                    if event.key is Key.KEY_ESC:
                        return Close()
                    if event.key is Key.KEY_F1:
                        return Modal(TargetScreen.Help)
                case KeyboardDisconnect():
                    return Modal(TargetScreen.KeyboardDetect)

    def render(self) -> Rendered:
        # TODO: render an X in the corner or something
        text = COMPOSES_TEMPLATE.format(
            composekey=self.settings.compose_key_description
        )
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
