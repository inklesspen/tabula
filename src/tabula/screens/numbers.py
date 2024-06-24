from ..device.keyboard_consts import Key

# https://en.wikipedia.org/wiki/Enclosed_Alphanumerics
# U+24EA is zero; it's out of order from the rest
# U+2460 is 1, U+2468 is 9
# U+24CE is Y; U+24C3 is N
# these are all in Noto Sans Symbols.
# B612 has similar glyphs but in a different block:
# https://en.wikipedia.org/wiki/Dingbats_(Unicode_block)
CIRCLED_ALPHANUMERICS = {
    "0": "\u24ea",
    "1": "\u2460",
    "2": "\u2461",
    "3": "\u2462",
    "4": "\u2463",
    "5": "\u2464",
    "6": "\u2465",
    "7": "\u2466",
    "8": "\u2467",
    "9": "\u2468",
    "Y": "\u24ce",
    "N": "\u24c3",
}

B612_CIRCLED_DIGITS = {
    1: "\u2780",
    2: "\u2781",
    3: "\u2782",
    4: "\u2783",
    5: "\u2784",
    6: "\u2785",
    7: "\u2786",
    8: "\u2787",
    9: "\u2788",
    0: "\u2789",
}

NUMBER_KEYS = {
    1: Key.KEY_1,
    2: Key.KEY_2,
    3: Key.KEY_3,
    4: Key.KEY_4,
    5: Key.KEY_5,
    6: Key.KEY_6,
    7: Key.KEY_7,
    8: Key.KEY_8,
    9: Key.KEY_9,
    0: Key.KEY_0,
}
