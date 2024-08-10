from ..device.eventsource import KeyCode

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
    1: KeyCode.KEY_1,
    2: KeyCode.KEY_2,
    3: KeyCode.KEY_3,
    4: KeyCode.KEY_4,
    5: KeyCode.KEY_5,
    6: KeyCode.KEY_6,
    7: KeyCode.KEY_7,
    8: KeyCode.KEY_8,
    9: KeyCode.KEY_9,
    0: KeyCode.KEY_0,
}
