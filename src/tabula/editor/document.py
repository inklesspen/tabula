# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing

import timeflake
import trio

from .types import Paragraph


# https://gankra.github.io/blah/text-hates-you/
# Cursor movement is fairly complicated. If we were gonna do everything the proper way, our
# document model would need to know about Unicode scalars, grapheme clusters, and all that jazz.
# After all, if I have a grapheme cluster composed of U+0065 (LATIN SMALL LETTER E) and U+0301
# (COMBINING ACCUTE ACCENT), these render as é (LATIN SMALL LETTER E WITH ACUTE). However, if I
# insert U+0302 (COMBINING CIRCUMFLEX ACCENT) into the middle of this cluster, I instead get ế
# (LATIN SMALL LETTER E WITH CIRCUMFLEX AND ACUTE). This example may sound contrived, but it
# happens all the time with non-Latin scripts.
# Notare currently handles attributed text by wrapping portions of the Markdown text in
# Pango Markup (HTML-ish tags). If we wanted to know about the grapheme clusters and glyphs,
# we'd have to switch to using PangoAttrList. So we're not going to do that.
# The cursor is always at the end of the final paragraph. That's it. That's all there is.


# We keep track of Sessions and Sprints. A session is a single markdown document. A sprint
# is a subsection of the document (starting and ending between paragraphs, so a paragraph
# is always completely in the sprint or completely out of it)
class DocumentModel:
    def __init__(self, dispatch_channel: trio.abc.SendChannel):
        self.dispatch_channel = dispatch_channel
        self.session_id: timeflake.Timeflake = None
        self.sprint_id: timeflake.Timeflake = None
        self.currently: typing.Optional[Paragraph] = None
        self.buffer: typing.List[str] = []
        self._contents_by_id: typing.Mapping[timeflake.Timeflake, Paragraph] = {}
        self._contents_by_index: typing.Mapping[int, Paragraph] = {}

    @property
    def has_session(self):
        return self.session_id is not None

    @property
    def has_sprint(self):
        return self.sprint_id is not None

    @property
    def contents(self):
        return self._contents_by_id.values()

    @contents.setter
    def contents(self, value: typing.List[Paragraph]):
        p: Paragraph
        self._contents_by_id = {}
        self._contents_by_index = {}
        for p in value:
            self._contents_by_id[p.id] = p
            self._contents_by_index[p.index] = p

    @property
    def cursor_para_id(self):
        return self.currently.id

    def __getitem__(self, key: typing.Union[timeflake.Timeflake, int]):
        if isinstance(key, timeflake.Timeflake):
            return self._contents_by_id[key]
        return self._contents_by_index[key]

    async def load_session(self, session_id, paras):
        # paras = self.db.load_session_paragraphs(session_id)
        new_para_needed = paras[-1].markdown != ""
        if new_para_needed:
            new_para = Paragraph(
                id=timeflake.random(),
                session_id=session_id,
                index=len(self.contents),
                markdown="",
            )
            paras.append(new_para)
        self.contents = paras
        self.buffer = []
        self.currently = paras[-1]
        self.session_id = session_id
        await self.dispatch_channel.send([p.id for p in self.contents])

    def _update_currently(self, evolve=True):
        if evolve:
            self.currently = self.currently.evolve("".join(self.buffer))
        self._contents_by_id[self.currently.id] = self.currently
        self._contents_by_index[self.currently.index] = self.currently

    async def keystroke(self, keystroke):
        self.buffer.append(keystroke)
        self._update_currently()

        changed = (self.currently.id,)
        await self.dispatch_channel.send(changed)

    async def backspace(self):
        if len(self.buffer) == 0:
            # no going back
            return
        del self.buffer[-1]
        self._update_currently()
        changed = (self.currently.id,)
        await self.dispatch_channel.send(changed)

    async def new_para(self):
        if len(self.buffer) == 0:
            return
        prev = self.currently
        self.buffer = []
        self.currently = Paragraph(
            id=timeflake.random(),
            session_id=self.session_id,
            index=len(self.contents),
            sprint_id=self.sprint_id,
            markdown="",
        )
        self._update_currently(evolve=False)
        changed = (prev.id, self.currently.id)
        await self.dispatch_channel.send(changed)

    def get_markups(self):
        return [p.markup for p in self.contents]

    def get_markup(self, i: int) -> str:
        return self.contents[i].markup
