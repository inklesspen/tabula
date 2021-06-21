# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later OR CC-BY-SA-4.0

HELP = """
Tabula is a portable prose-oriented distraction-free drafting tool.

The cursor is locked at the end of the document. You can delete characters with Backspace, but only within the current paragraph; once you hit Enter, you canʼt go back.

You can enter special characters through the use of <b>compose sequences</b>. Press <span font="Noto Sans Mono">F2</span> for examples of common compose sequences.

Press <span font="Noto Sans Mono">TBD</span> to start or end a writing sprint.

Press <span font="Noto Sans Mono">F12</span> to open the system menu.

<small>This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.</small>
""".strip()

# There's a compose key symbol in unicode (U+2384) but most fonts don't have a glyph for it.
# One such font is Noto Sans Symbols; alpine package 'font-noto'
COMPOSES_TEMPLATE = """
To enter a compose sequence, press and release the Compose key (<span font="Noto Sans Symbols">\u2384</span>), followed by each key of the sequence. You donʼt need to hold down the keys.

On this machine, the Compose key (<span font="Noto Sans Symbols">\u2384</span>) is {composekey}.

Here are some commonly used compose sequences:
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> - a</span> → ā (and similar for other vowels)
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> ^ a</span> → â (and similar for other vowels)
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> ' a</span> → á (and similar for other vowels)
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> ` a</span> → à (and similar for other vowels)
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> ~ n</span> → ñ

<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> &#60; '</span> → \u2018 (can be given in either order)
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> &#62; '</span> → \u2019
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> &#60; "</span> → \u201C (can be given in either order)
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> &#62; "</span> → \u201D
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> &#60; &#60;</span> → \u00AB
<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> &#62; &#62;</span> → \u00BB

<span font="Noto Sans Symbols">\u2384</span><span font="Noto Sans Mono"> ' '</span> → \u02BC (modifier letter apostrophe)
""".strip()
