import dataclasses
import datetime
import json
import operator
import pathlib
import typing

import cattrs
import pygtrie

from .commontypes import ScreenRotation
from .device.eventsource import KeyCode
from .durations import format_duration, parse_duration

COMPOSE_SEQUENCES = {
    "< <": "«",
    "> >": "»",
    "< '": "‘",
    "' <": "‘",
    "> '": "’",
    "' >": "’",
    '< "': "“",
    '" <': "“",
    '> "': "”",
    '" >': "”",
    "' '": "ʼ",
    ". .": "…",
    "- - -": "—",
    "- - .": "–",
    "! !": "¡",
    "? ?": "¿",
    "1 4": "¼",
    "1 2": "½",
    "3 4": "¾",
    "o x": "¤",
    "x o": "¤",
    "o c": "©",
    "o C": "©",
    "O c": "©",
    "O C": "©",
    "p !": "¶",
    "P !": "¶",
    "P P": "¶",
    "A E": "Æ",
    "a e": "æ",
    "O E": "Œ",
    "o e": "œ",
    "` A": "À",
    "' A": "Á",
    "- A": "Ā",
    "` a": "à",
    "' a": "á",
    "- a": "ā",
    ", C": "Ç",
    ", c": "ç",
    "` E": "È",
    "' E": "É",
    "- E": "Ē",
    "` e": "è",
    "' e": "é",
    "- e": "ē",
    "` I": "Ì",
    "' I": "Í",
    "- I": "Ī",
    "` i": "ì",
    "' i": "í",
    "- i": "ī",
    "~ N": "Ñ",
    "~ n": "ñ",
    "` O": "Ò",
    "' O": "Ó",
    "- O": "Ō",
    "` o": "ò",
    "' o": "ó",
    "- o": "ō",
    "` U": "Ù",
    "' U": "Ú",
    "- U": "Ū",
    "` u": "ù",
    "' u": "ú",
    "- u": "ū",
    '" u': "ü",
    "' Y": "Ý",
    "' y": "ý",
}

KEYMAPS = {
    "KEY_GRAVE": ["`", "~"],
    "KEY_1": ["1", "!"],
    "KEY_2": ["2", "@"],
    "KEY_3": ["3", "#"],
    "KEY_4": ["4", "$"],
    "KEY_5": ["5", "%"],
    "KEY_6": ["6", "^"],
    "KEY_7": ["7", "&"],
    "KEY_8": ["8", "*"],
    "KEY_9": ["9", "("],
    "KEY_0": ["0", ")"],
    "KEY_MINUS": ["-", "_"],
    "KEY_EQUAL": ["=", "+"],
    "KEY_Q": ["q", "Q"],
    "KEY_W": ["w", "W"],
    "KEY_E": ["e", "E"],
    "KEY_R": ["r", "R"],
    "KEY_T": ["t", "T"],
    "KEY_Y": ["y", "Y"],
    "KEY_U": ["u", "U"],
    "KEY_I": ["i", "I"],
    "KEY_O": ["o", "O"],
    "KEY_P": ["p", "P"],
    "KEY_LEFTBRACE": ["[", "{"],
    "KEY_RIGHTBRACE": ["]", "}"],
    "KEY_BACKSLASH": ["\\", "|"],
    "KEY_A": ["a", "A"],
    "KEY_S": ["s", "S"],
    "KEY_D": ["d", "D"],
    "KEY_F": ["f", "F"],
    "KEY_G": ["g", "G"],
    "KEY_H": ["h", "H"],
    "KEY_J": ["j", "J"],
    "KEY_K": ["k", "K"],
    "KEY_L": ["l", "L"],
    "KEY_SEMICOLON": [";", ":"],
    "KEY_APOSTROPHE": ["'", '"'],
    "KEY_Z": ["z", "Z"],
    "KEY_X": ["x", "X"],
    "KEY_C": ["c", "C"],
    "KEY_V": ["v", "V"],
    "KEY_B": ["b", "B"],
    "KEY_N": ["n", "N"],
    "KEY_M": ["m", "M"],
    "KEY_COMMA": [",", "<"],
    "KEY_DOT": [".", ">"],
    "KEY_SLASH": ["/", "?"],
    "KEY_SPACE": [" ", " "],
}

COMPOSE_KEY = "KEY_RIGHTMETA"
COMPOSE_KEY_DESCRIPTION = "the right-hand Meta key"


def timedelta_seconds(seconds: datetime.timedelta | int | str):
    if isinstance(seconds, datetime.timedelta):
        return seconds
    if isinstance(seconds, int):
        return datetime.timedelta(seconds=seconds)
    return parse_duration(seconds)


settings_converter = cattrs.Converter()
settings_converter.register_unstructure_hook(datetime.timedelta, format_duration)
settings_converter.register_structure_hook(datetime.timedelta, lambda d, _: parse_duration(d))


def unstructure_trie(t: pygtrie.Trie):
    return {" ".join(k): v for k, v in t.items()}


def structure_trie(d: dict, typ: type[pygtrie.Trie]):
    return pygtrie.Trie({tuple(k.split()): v for k, v in d.items()})


settings_converter.register_unstructure_hook(pygtrie.Trie, unstructure_trie)
settings_converter.register_structure_hook(pygtrie.Trie, structure_trie)
settings_converter.register_unstructure_hook(KeyCode, operator.attrgetter("name"))
settings_converter.register_structure_hook(KeyCode, lambda v, _: KeyCode[v])


def unstructure_screen_rotation(sr: ScreenRotation):
    return {
        ScreenRotation.PORTRAIT: "PORTRAIT",
        ScreenRotation.INVERTED_PORTRAIT: "PORTRAIT",
        ScreenRotation.LANDSCAPE_PORT_LEFT: "LANDSCAPE",
        ScreenRotation.LANDSCAPE_PORT_RIGHT: "LANDSCAPE",
    }[sr]


def structure_screen_rotation(v: str, typ: type[ScreenRotation]):
    if v != "PORTRAIT" and v != "LANDSCAPE":
        raise ValueError(f"Unexpected value {v}")
    return ScreenRotation.PORTRAIT if v == "PORTRAIT" else ScreenRotation.LANDSCAPE_PORT_RIGHT


settings_converter.register_unstructure_hook(ScreenRotation, unstructure_screen_rotation)
settings_converter.register_structure_hook(ScreenRotation, structure_screen_rotation)


@dataclasses.dataclass(kw_only=True)
class Settings:
    _path: pathlib.Path
    current_font: str
    current_font_size: float
    current_line_spacing: float
    compose_key: KeyCode
    compose_key_description: str
    compose_sequences: pygtrie.Trie
    compose_examples: list[dict[str, str]]
    keymaps: dict[KeyCode, list[str]]
    db_path: pathlib.Path
    export_path: pathlib.Path
    font_path: pathlib.Path
    max_editable_age: datetime.timedelta
    sprint_lengths: list[datetime.timedelta]
    default_screen_rotation: ScreenRotation
    enable_bluetooth: bool

    def set_current_font(self, new_current_font: str, new_size: float, new_line_spacing: float):
        self.current_font = new_current_font
        self.current_font_size = new_size
        self.current_line_spacing = new_line_spacing

    def save(self, dest: typing.Optional[pathlib.Path] = None):
        if dest is None:
            dest = self._path
        raw = settings_converter.unstructure(self)
        del raw["_path"]
        json.dump(raw, dest.open("w"), indent=2)

    @classmethod
    def load(cls, src: pathlib.Path):
        raw = json.load(src.open())
        raw["_path"] = src
        return settings_converter.structure(raw, cls)

    @classmethod
    def for_test(cls):
        return settings_converter.structure(
            {
                "_path": "test.settings.json",
                "current_font": "Tabula Quattro",
                "current_font_size": 8.0,
                "current_line_spacing": 1.0,
                "compose_key": COMPOSE_KEY,
                "compose_key_description": COMPOSE_KEY_DESCRIPTION,
                "compose_sequences": COMPOSE_SEQUENCES,
                "keymaps": KEYMAPS,
                "db_path": "test.db",
                "export_path": "test_export",
                "font_path": "bogus_font_path",
                "max_editable_age": "1h",
                "sprint_lengths": ["5m", "10m", "15m", "30m"],
                "default_screen_rotation": "PORTRAIT",
                "enable_bluetooth": False,
            },
            cls,
        )


settings_converter.register_structure_hook(Settings, cattrs.gen.make_dict_structure_fn(Settings, settings_converter))
