import msgspec
import pygtrie
import trio

from tabula.device.keyboard_consts import Key

# Eventually these will be stored in a config file, hence the async load_settings()
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

DRAFTING_FONTS = ["Tabula Quattro 8", "Comic Neue 8", "Special Elite 8"]

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


class Settings(msgspec.Struct, frozen=True):
    drafting_fonts: list[str]
    compose_key: Key
    compose_sequences: pygtrie.Trie
    keymaps: dict[Key, list[str]]


def _load_settings():
    return Settings(
        drafting_fonts=DRAFTING_FONTS,
        compose_key=Key[COMPOSE_KEY],
        compose_sequences=pygtrie.Trie(
            {tuple(k.split()): v for k, v in COMPOSE_SEQUENCES.items()}
        ),
        keymaps={Key[k]: v for k, v in KEYMAPS.items()},
    )


async def load_settings():
    await trio.sleep(0)
    return _load_settings()
