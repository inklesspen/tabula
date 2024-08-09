from __future__ import annotations

import dataclasses
import logging
import re
import typing

from ..device.keyboard_consts import Key

if typing.TYPE_CHECKING:
    import pygtrie

    from ..device.hwtypes import AnnotatedKeyEvent

logger = logging.getLogger(__name__)


@dataclasses.dataclass(kw_only=True)
class ComposeFailed:
    key_events: list[AnnotatedKeyEvent]


@dataclasses.dataclass(kw_only=True)
class ComposeSucceeded:
    result: str


@dataclasses.dataclass(kw_only=True)
class ComposeOther:
    active_changed: bool = False
    show_help: bool = False
    absorb: bool = False


ComposeResult = ComposeFailed | ComposeSucceeded | ComposeOther

CODEPOINT_MATCHER = re.compile(r"^\+((?:[0-9A-Fa-f]){4})$")
PAD_FORMATTER = "{:0<5}".format


class ComposeState:
    active: bool
    devoured: list[AnnotatedKeyEvent]
    devoured_characters: list[str]

    def __init__(self, sequences: pygtrie.Trie):
        self.sequences = sequences
        self.active = False

    def actively_handle_key_event(self, event: AnnotatedKeyEvent) -> ComposeResult:
        # if key is compose and we have collected already, restart the collecting; if no collection, show help screen instead
        if event.key is Key.KEY_COMPOSE:
            if self.devoured:
                logging.debug("Restarting compose collecting")
                self.devoured = []
                self.devoured_characters = []
                self.can_be_codepoint = False
                self.can_be_compose_sequence = False
                return ComposeOther()
            else:  # noqa: RET505
                self.active = False
                return ComposeOther(active_changed=True, show_help=True)
        # if key is backspace, we should just cancel the compose without dumping out the captured keys
        if event.key is Key.KEY_BACKSPACE:
            self.devoured = []
            self.devoured_characters = []
            self.can_be_codepoint = False
            self.can_be_compose_sequence = False
            self.active = False
            return ComposeOther(active_changed=True, absorb=True)

        self.devoured.append(event)
        if event.is_modifier:
            return ComposeOther()
        still_matching = False
        if event.character is not None:
            self.devoured_characters.append(event.character)
            self.can_be_compose_sequence = bool(self.sequences.has_node(self.devoured_characters))
            self.can_be_codepoint = bool(CODEPOINT_MATCHER.match(PAD_FORMATTER("".join(self.devoured_characters))))
            still_matching = self.can_be_compose_sequence or self.can_be_codepoint
        if not (still_matching or event.is_modifier):
            # not a match
            self.active = False
            return ComposeFailed(key_events=self.devoured)
        if self.sequences.has_key(self.devoured_characters):
            # end of sequence
            self.active = False
            return ComposeSucceeded(result=self.sequences[self.devoured_characters])
        if codepoint_match := CODEPOINT_MATCHER.match("".join(self.devoured_characters)):
            self.active = False
            codepoint_str = codepoint_match.group(1)
            codepoint = int(codepoint_str, base=16)
            return ComposeSucceeded(result=chr(codepoint))
        return ComposeOther()

    def handle_key_event(self, event: AnnotatedKeyEvent) -> ComposeResult:
        if self.active:
            return self.actively_handle_key_event(event)
        if event.key is Key.KEY_COMPOSE:
            self.active = True
            self.devoured = []
            self.devoured_characters = []
            self.can_be_codepoint = False
            self.can_be_compose_sequence = False
            return ComposeOther(active_changed=True)
        return ComposeOther()

    @property
    def composing_chars(self):
        chars = ""
        if not self.active:
            return chars
        devoured_string = "".join(self.devoured_characters)
        if self.can_be_compose_sequence:
            chars = devoured_string
        elif self.can_be_codepoint:
            chars = "U+" + devoured_string[1:]
        return chars
