# SPDX-FileCopyrightText: 2023 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing
import unicodedata

import timeflake

from .doctypes import Paragraph
from . import wordcount

if typing.TYPE_CHECKING:
    from .db import TabulaDb


# https://gankra.github.io/blah/text-hates-you/
# Cursor movement is fairly complicated. If we were gonna do everything the proper way, our
# document model would need to know about Unicode scalars, grapheme clusters, and all that jazz.
# After all, if I have a grapheme cluster composed of U+0065 (LATIN SMALL LETTER E) and U+0301
# (COMBINING ACCUTE ACCENT), these render as é (LATIN SMALL LETTER E WITH ACUTE). However, if I
# insert U+0302 (COMBINING CIRCUMFLEX ACCENT) into the middle of this cluster, I instead get ế
# (LATIN SMALL LETTER E WITH CIRCUMFLEX AND ACUTE). This example may sound contrived, but it
# happens all the time with non-Latin scripts.
# Tabula currently handles attributed text by wrapping portions of the Markdown text in
# Pango Markup (HTML-ish tags). If we wanted to know about the grapheme clusters and glyphs,
# we'd have to switch to using PangoAttrList. So we're not going to do that.
# The cursor is always at the end of the final paragraph. That's it. That's all there is.


# We keep track of Sessions and Sprints. A session is a single markdown document. A sprint
# is a subsection of the document (starting and ending between paragraphs, so a paragraph
# is always completely in the sprint or completely out of it)
class DocumentModel:
    def __init__(self):
        self.session_id: timeflake.Timeflake = None
        self.sprint_id: timeflake.Timeflake = None
        self.currently: typing.Optional[Paragraph] = None
        self.buffer: list[str] = []
        self._contents_by_id: dict[timeflake.Timeflake, Paragraph] = {}
        self._contents_by_index: dict[int, Paragraph] = {}
        self.unsaved_changes = False

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
        self._contents_by_id = {}
        self._contents_by_index = {}
        for p in value:
            self._contents_by_id[p.id] = p
            self._contents_by_index[p.index] = p

    @property
    def cursor_para_id(self):
        if self.currently is None:
            raise ValueError("The cursor para does not exist.")
        return self.currently.id

    def __len__(self):
        return len(self._contents_by_id)

    def __getitem__(self, key: typing.Union[timeflake.Timeflake, int]):
        if isinstance(key, timeflake.Timeflake):
            return self._contents_by_id[key]
        return self._contents_by_index[key]

    def load_session(self, session_id, db: "TabulaDb"):
        paras = db.load_session_paragraphs(session_id)
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
        self.sprint_id = None
        self.unsaved_changes = False

    def save_session(self, db: "TabulaDb"):
        if not self.has_session or not self.unsaved_changes:
            return
        paras = self.contents
        doc_wc = wordcount.count_plain_text(
            wordcount.make_plain_text("\n".join([p.markdown for p in paras]))
        )
        db.save_session(self.session_id, doc_wc, paras)

    def _update_currently(self, evolve=True):
        if evolve:
            self.currently = self.currently.evolve("".join(self.buffer))
        self._contents_by_id[self.currently.id] = self.currently
        self._contents_by_index[self.currently.index] = self.currently

    def keystroke(self, keystroke) -> tuple[timeflake.Timeflake, ...]:
        self.buffer.append(keystroke)
        self._update_currently()

        self.unsaved_changes = True
        changed = (self.currently.id,)
        return changed

    def backspace(self) -> tuple[timeflake.Timeflake, ...]:
        if len(self.buffer) == 0:
            # no going back
            return tuple()
        del self.buffer[-1]
        self._update_currently()

        self.unsaved_changes = True
        changed = (self.currently.id,)
        return changed

    def new_para(self) -> tuple[timeflake.Timeflake, ...]:
        if len(self.buffer) == 0:
            return tuple()
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

        self.unsaved_changes = True
        changed = (prev.id, self.currently.id)
        return changed

    def get_markups(self):
        return [p.markup for p in self.contents]

    def get_markup(self, i: int) -> str:
        return self.contents[i].markup

    @staticmethod
    def graphical_char(c: typing.Optional[str]):
        if c is None:
            return False
        category = unicodedata.category(c)
        return category == "Zs" or category[0] in ("L", "M", "N", "P", "S")
