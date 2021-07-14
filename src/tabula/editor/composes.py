# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import pygtrie

from .consts import Printables

COMPOSES = pygtrie.CharTrie()
# Guillemets
COMPOSES[(Printables.LESS_THAN_SIGN.value, Printables.LESS_THAN_SIGN.value)] = "\u00AB"
COMPOSES[
    (Printables.GREATER_THAN_SIGN.value, Printables.GREATER_THAN_SIGN.value)
] = "\u00BB"
# "Smart" quotes
COMPOSES[(Printables.LESS_THAN_SIGN.value, Printables.APOSTROPHE.value)] = "\u2018"
COMPOSES[(Printables.APOSTROPHE.value, Printables.LESS_THAN_SIGN.value)] = "\u2018"
COMPOSES[(Printables.GREATER_THAN_SIGN.value, Printables.APOSTROPHE.value)] = "\u2019"
COMPOSES[(Printables.APOSTROPHE.value, Printables.GREATER_THAN_SIGN.value)] = "\u2019"
COMPOSES[(Printables.LESS_THAN_SIGN.value, Printables.QUOTATION_MARK.value)] = "\u201C"
COMPOSES[(Printables.QUOTATION_MARK.value, Printables.LESS_THAN_SIGN.value)] = "\u201C"
COMPOSES[
    (Printables.GREATER_THAN_SIGN.value, Printables.QUOTATION_MARK.value)
] = "\u201D"
COMPOSES[
    (Printables.QUOTATION_MARK.value, Printables.GREATER_THAN_SIGN.value)
] = "\u201D"
# Modifier Letter Apostrophe
COMPOSES[(Printables.APOSTROPHE.value, Printables.APOSTROPHE.value)] = "\u02BC"
