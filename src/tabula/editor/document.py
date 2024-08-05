# SPDX-FileCopyrightText: 2023 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
import typing
import unicodedata

import timeflake

from ..durations import format_duration
from ..util import now
from . import wordcount
from .doctypes import Paragraph, Sprint

if typing.TYPE_CHECKING:
    import datetime
    import pathlib
    from collections.abc import Sequence

    from ..db import TabulaDb


logger = logging.getLogger(__name__)

# https://faultlore.com/blah/text-hates-you/
# https://lord.io/text-editing-hates-you-too/
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
        self.sprint: typing.Optional[Sprint] = None
        self.sprint_start_para: typing.Optional[int] = None
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

    @staticmethod
    def _wordcount_paras(paras: Sequence[Paragraph]):
        return wordcount.count_plain_text(wordcount.make_plain_text("\n\n".join([p.markdown for p in paras])))

    @property
    def wordcount(self):
        return self._wordcount_paras(self.contents)

    @property
    def sprint_wordcount(self):
        if not self.has_sprint:
            return None
        return self._wordcount_paras(list(self.contents)[self.sprint_start_para :])

    def __len__(self):
        return len(self._contents_by_id)

    def __getitem__(self, key: typing.Union[timeflake.Timeflake, int]):
        if isinstance(key, timeflake.Timeflake):
            return self._contents_by_id[key]
        return self._contents_by_index[key]

    def load_session(self, session_id: timeflake.Timeflake, db: TabulaDb):
        paras = db.load_session_paragraphs(session_id)
        new_para_needed = paras[-1].markdown != ""
        if new_para_needed:
            new_para = Paragraph(
                id=timeflake.random(),
                session_id=session_id,
                index=len(paras),
                markdown="",
            )
            paras.append(new_para)
        self.contents = paras
        self.currently = paras[-1]
        self.session_id = session_id
        self.sprint_id = None
        self.unsaved_changes = False

    def save_session(self, db: TabulaDb, called_from=None):
        if not self.has_session or not self.unsaved_changes:
            return
        logger.debug("(called from %s) actually saving session", called_from)
        db.save_session(self.session_id, self.wordcount, self.contents)
        self.unsaved_changes = False

    def delete_session(self, db: TabulaDb):
        db.delete_session(self.session_id)
        self.contents = []
        self.currently = None
        self.session_id = None
        self.sprint_id = None
        self.unsaved_changes = None

    def begin_sprint(self, db: TabulaDb, duration: datetime.timedelta):
        assert self.has_session and not self.has_sprint
        self.sprint_id = db.new_sprint(self.session_id, duration)
        self.sprint = db.load_sprint_info(self.sprint_id)
        self.new_para()
        start_time = self.sprint.started_at.strftime("%H:%M")
        self.currently.markdown = f"# Started {format_duration(self.sprint.intended_duration)} sprint at {start_time}."
        self.sprint_start_para = self.currently.index
        self.new_para()

    def end_sprint(self, db: TabulaDb):
        assert self.has_session and self.has_sprint
        db.update_sprint(self.sprint_id, wordcount=self.sprint_wordcount, ended=True)
        self.sprint = db.load_sprint_info(self.sprint_id)
        self.new_para()
        self.currently.markdown = (
            f"# Sprint ended after {format_duration(self.sprint.actual_duration)} with {wordcount.format_wordcount(self.sprint.wordcount)}."
        )
        self.sprint_id = None
        self.sprint = None
        self.sprint_start_para = None
        self.new_para()

    def keystroke(self, keystroke: str):
        self.currently.markdown += keystroke
        self.unsaved_changes = True

    def backspace(self):
        if len(self.currently.markdown) == 0:
            # no going back
            return
        self.currently.markdown = self.currently.markdown[:-1]

        self.unsaved_changes = True

    def new_para(self):
        if self.currently and len(self.currently.markdown) == 0:
            return
        self.currently = Paragraph(
            id=timeflake.random(),
            session_id=self.session_id,
            index=len(self.contents),
            sprint_id=self.sprint_id,
            markdown="",
        )
        self._contents_by_id[self.currently.id] = self.currently
        self._contents_by_index[self.currently.index] = self.currently

        self.unsaved_changes = True

    def export_markdown(self):
        return "\n\n".join(p.markdown for p in self.contents)

    def export_session(self, db: TabulaDb, export_path: pathlib.Path):
        export_path.mkdir(parents=True, exist_ok=True)
        timestamp = now()
        session_id = self.session_id
        export_filename = f"{session_id} - {timestamp} - {self.wordcount} words.md"
        export_file = export_path / export_filename
        with export_file.open(mode="w", encoding="utf-8") as out:
            out.write(self.export_markdown())
        db.set_exported_time(session_id, timestamp)

    @staticmethod
    def graphical_char(c: typing.Optional[str]):
        if c is None:
            return False
        category = unicodedata.category(c)
        return category == "Zs" or category[0] in ("L", "M", "N", "P", "S")

    @staticmethod
    def whitespace_char(c: typing.Optional[str]):
        if c is None:
            return False
        category = unicodedata.category(c)
        return category.startswith("Z")
