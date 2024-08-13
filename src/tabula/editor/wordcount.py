# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import deque
from itertools import count

from ._wordchars import WORD_CHARS

# Avoid constructing a deque each time
consumeall = deque(maxlen=0).extend


# based on a solution from https://stackoverflow.com/a/34404546
def count_plain_text(text: str) -> int:
    cnt = count()
    consumeall(zip(WORD_CHARS.finditer(text), cnt, strict=False))
    return next(cnt)


def format_wordcount(wordcount: int):
    return "1 word" if wordcount == 1 else "{:,} words".format(wordcount)
