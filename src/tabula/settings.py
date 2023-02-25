import datetime
import pathlib
import typing

import attrs
import msgspec
import pygtrie

from .device.keyboard_consts import Key
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

DRAFTING_FONTS = {
    "Tabula Quattro": ["6.9", "7.4", "8", "8.5", "9.1", "9.7", "10.2"],
    "Comic Neue": ["8.9", "9.7", "10.4", "11.1", "11.8", "12.5", "13.2"],
    "Special Elite": ["8.9", "9.7", "10.4", "11.1", "11.8", "12.5", "13.2"],
    "Atkinson Hyperlegible": ["7.5", "8.1", "8.7", "9.3", "9.9", "10.5", "11.1"],
}

# TODO: redo these values; I wasn't using the proper font sizes yet when I determined these the first time.
LINE_SPACING = {
    "Tabula Quattro": 1.0,
    "Comic Neue": 1.3,
    "Special Elite": 1.4,
    "Atkinson Hyperlegible": 1.1,
}


class SettingsData(msgspec.Struct):
    drafting_fonts: dict[str, list[str]]
    current_font: str
    current_font_size: int
    compose_key: str
    compose_sequences: dict[str, str]
    keymaps: dict[str, list[str]]
    db_path: str
    export_path: str
    max_editable_age: datetime.timedelta


def _enc_hook(obj: typing.Any) -> typing.Any:
    if isinstance(obj, datetime.timedelta):
        return format_duration(obj)
    else:
        raise TypeError(f"Objects of type {type(obj)} are not supported")


def _dec_hook(type: typing.Type, obj: typing.Any) -> typing.Any:
    if type is datetime.timedelta:
        return parse_duration(obj)
    else:
        raise TypeError(f"Objects of type {type} are not supported")


settings_encoder = msgspec.json.Encoder(enc_hook=_enc_hook)
settings_decoder = msgspec.json.Decoder(SettingsData, dec_hook=_dec_hook)


@attrs.define(kw_only=True, init=False)
class Settings:
    _data: SettingsData = attrs.field(repr=False)
    _path: pathlib.Path = attrs.field(repr=False, eq=False, order=False)
    drafting_fonts: dict[str, list[str]] = attrs.field(eq=False, order=False)
    current_font: str = attrs.field(eq=False, order=False)
    current_font_size: int = attrs.field(eq=False, order=False)
    compose_key: Key = attrs.field(eq=False, order=False)
    compose_sequences: pygtrie.Trie = attrs.field(eq=False, order=False)
    keymaps: dict[Key, list[str]] = attrs.field(eq=False, order=False)
    db_path: pathlib.Path = attrs.field(eq=False, order=False)
    export_path: pathlib.Path = attrs.field(eq=False, order=False)
    max_editable_age: datetime.timedelta = attrs.field(eq=False, order=False)

    def __init__(self, data: SettingsData, path: pathlib.Path):
        self.__attrs_init__(
            data=data,
            path=path,
            drafting_fonts=data.drafting_fonts,
            current_font=data.current_font,
            current_font_size=data.current_font_size,
            compose_key=Key[data.compose_key],
            compose_sequences=pygtrie.Trie(
                {tuple(k.split()): v for k, v in data.compose_sequences.items()}
            ),
            keymaps={Key[k]: v for k, v in data.keymaps.items()},
            db_path=pathlib.Path(data.db_path),
            export_path=pathlib.Path(data.export_path),
            max_editable_age=data.max_editable_age,
        )

    def set_current_font(self, new_current_font: str, new_size: int):
        new_data = msgspec.structs.replace(
            self._data, current_font=new_current_font, current_font_size=new_size
        )
        self._data = new_data
        self.current_font = new_current_font
        self.current_font_size = new_size

    def save(self, dest: pathlib.Path = None):
        if dest is None:
            dest = self._path
        dest.write_bytes(msgspec.json.format(settings_encoder.encode(self._data)))

    @classmethod
    def load(cls, src: pathlib.Path):
        return cls(settings_decoder.decode(src.read_bytes()), src)

    @classmethod
    def for_test(cls):
        return cls(
            SettingsData(
                drafting_fonts=DRAFTING_FONTS,
                current_font="Tabula Quattro",
                current_font_size=2,
                compose_key=COMPOSE_KEY,
                compose_sequences=COMPOSE_SEQUENCES,
                keymaps=KEYMAPS,
                db_path="test.db",
                export_path="test_export",
                max_editable_age=datetime.timedelta(hours=1),
            ),
            pathlib.Path("test.settings.json"),
        )
