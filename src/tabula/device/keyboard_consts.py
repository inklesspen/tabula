# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from enum import IntEnum

# Mostly we care about EV_KEY. These events have a value of 1 for keydown and 0 for
# keyup, and 2 for autorepeat (key held down).
# LEDs are controlled with EV_LED, autorepeat is controlled with EV_REP (depending on
# keyboard driver), and raw scancodes can be gotten off EV_MSC.MSC_SCAN.
# EV_SYN is synchronization, but we can ignore that for now, I think.

# These are just the codes reported by my Varmilo VA87M.
# TODO: test some other keyboards to see if we need to expand the list.


class EventType(IntEnum):
    # Used as markers to separate events. Events may be separated in time or in
    # space, such as with the multitouch protocol.
    EV_SYN = 0
    # Used to describe state changes of keyboards, buttons, or other key-like
    # devices.
    EV_KEY = 1
    # Used to describe miscellaneous input data that do not fit into other types.
    EV_MSC = 4
    # Used to turn LEDs on devices on and off.
    EV_LED = 17
    # Used for autorepeating devices.
    EV_REP = 20


class SyncEvent(IntEnum):
    # Used to synchronize and separate events into packets of input data changes
    # occurring at the same moment in time. For example, motion of a mouse may set
    # the REL_X and REL_Y values for one motion, then emit a SYN_REPORT. The next
    # motion will emit more REL_X and REL_Y values and send another SYN_REPORT.
    SYN_REPORT = 0
    SYN_CONFIG = 1
    # Used to synchronize and separate touch events. See the
    # multi-touch-protocol.txt document for more information.
    SYN_MT_REPORT = 2
    # Used to indicate buffer overrun in the evdev client's event queue.
    # Client should ignore all events up to and including next SYN_REPORT
    # event and query the device (using EVIOCG* ioctls) to obtain its
    # current state.
    # libevdev will automatically discard events until SYN_REPORT
    SYN_DROPPED = 3


# EV_KEY events take the form KEY_<name> or BTN_<name>. For example, KEY_A is used
# to represent the 'A' key on a keyboard. When a key is depressed, an event with
# the key's code is emitted with value 1. When the key is released, an event is
# emitted with value 0. Some hardware send events when a key is repeated. These
# events have a value of 2. In general, KEY_<name> is used for keyboard keys, and
# BTN_<name> is used for other types of momentary switch events.
class Key(IntEnum):
    KEY_ESC = 1
    KEY_1 = 2
    KEY_2 = 3
    KEY_3 = 4
    KEY_4 = 5
    KEY_5 = 6
    KEY_6 = 7
    KEY_7 = 8
    KEY_8 = 9
    KEY_9 = 10
    KEY_0 = 11
    KEY_MINUS = 12
    KEY_EQUAL = 13
    KEY_BACKSPACE = 14
    KEY_TAB = 15
    KEY_Q = 16
    KEY_W = 17
    KEY_E = 18
    KEY_R = 19
    KEY_T = 20
    KEY_Y = 21
    KEY_U = 22
    KEY_I = 23
    KEY_O = 24
    KEY_P = 25
    KEY_LEFTBRACE = 26
    KEY_RIGHTBRACE = 27
    KEY_ENTER = 28
    KEY_LEFTCTRL = 29
    KEY_A = 30
    KEY_S = 31
    KEY_D = 32
    KEY_F = 33
    KEY_G = 34
    KEY_H = 35
    KEY_J = 36
    KEY_K = 37
    KEY_L = 38
    KEY_SEMICOLON = 39
    KEY_APOSTROPHE = 40
    KEY_GRAVE = 41
    KEY_LEFTSHIFT = 42
    KEY_BACKSLASH = 43
    KEY_Z = 44
    KEY_X = 45
    KEY_C = 46
    KEY_V = 47
    KEY_B = 48
    KEY_N = 49
    KEY_M = 50
    KEY_COMMA = 51
    KEY_DOT = 52
    KEY_SLASH = 53
    KEY_RIGHTSHIFT = 54
    KEY_KPASTERISK = 55
    KEY_LEFTALT = 56
    KEY_SPACE = 57
    KEY_CAPSLOCK = 58
    KEY_F1 = 59
    KEY_F2 = 60
    KEY_F3 = 61
    KEY_F4 = 62
    KEY_F5 = 63
    KEY_F6 = 64
    KEY_F7 = 65
    KEY_F8 = 66
    KEY_F9 = 67
    KEY_F10 = 68
    KEY_NUMLOCK = 69
    KEY_SCROLLLOCK = 70
    KEY_KP7 = 71
    KEY_KP8 = 72
    KEY_KP9 = 73
    KEY_KPMINUS = 74
    KEY_KP4 = 75
    KEY_KP5 = 76
    KEY_KP6 = 77
    KEY_KPPLUS = 78
    KEY_KP1 = 79
    KEY_KP2 = 80
    KEY_KP3 = 81
    KEY_KP0 = 82
    KEY_KPDOT = 83
    KEY_ZENKAKUHANKAKU = 85
    KEY_102ND = 86
    KEY_F11 = 87
    KEY_F12 = 88
    KEY_RO = 89
    KEY_KATAKANA = 90
    KEY_HIRAGANA = 91
    KEY_HENKAN = 92
    KEY_KATAKANAHIRAGANA = 93
    KEY_MUHENKAN = 94
    KEY_KPJPCOMMA = 95
    KEY_KPENTER = 96
    KEY_RIGHTCTRL = 97
    KEY_KPSLASH = 98
    KEY_SYSRQ = 99
    KEY_RIGHTALT = 100
    KEY_HOME = 102
    KEY_UP = 103
    KEY_PAGEUP = 104
    KEY_LEFT = 105
    KEY_RIGHT = 106
    KEY_END = 107
    KEY_DOWN = 108
    KEY_PAGEDOWN = 109
    KEY_INSERT = 110
    KEY_DELETE = 111
    KEY_MUTE = 113
    KEY_VOLUMEDOWN = 114
    KEY_VOLUMEUP = 115
    KEY_POWER = 116
    KEY_KPEQUAL = 117
    KEY_PAUSE = 119
    KEY_KPCOMMA = 121
    KEY_HANGEUL = 122
    KEY_HANJA = 123
    KEY_YEN = 124
    KEY_LEFTMETA = 125
    KEY_RIGHTMETA = 126
    KEY_COMPOSE = 127
    KEY_STOP = 128
    KEY_AGAIN = 129
    KEY_PROPS = 130
    KEY_UNDO = 131
    KEY_FRONT = 132
    KEY_COPY = 133
    KEY_OPEN = 134
    KEY_PASTE = 135
    KEY_FIND = 136
    KEY_CUT = 137
    KEY_HELP = 138
    KEY_CALC = 140
    KEY_SLEEP = 142
    KEY_WWW = 150
    # Terminal Lock/Screensaver (thus, "coffee break")
    KEY_COFFEE = 152
    KEY_BACK = 158
    KEY_FORWARD = 159
    KEY_EJECTCD = 161
    KEY_NEXTSONG = 163
    KEY_PLAYPAUSE = 164
    KEY_PREVIOUSSONG = 165
    KEY_STOPCD = 166
    KEY_REFRESH = 173
    KEY_EDIT = 176
    KEY_SCROLLUP = 177
    KEY_SCROLLDOWN = 178
    KEY_KPLEFTPAREN = 179
    KEY_KPRIGHTPAREN = 180
    KEY_F13 = 183
    KEY_F14 = 184
    KEY_F15 = 185
    KEY_F16 = 186
    KEY_F17 = 187
    KEY_F18 = 188
    KEY_F19 = 189
    KEY_F20 = 190
    KEY_F21 = 191
    KEY_F22 = 192
    KEY_F23 = 193
    KEY_F24 = 194
    KEY_UNKNOWN = 240

    # Synthetic keycodes emitted by the keystream logic
    SYNTHETIC_COMPOSE_DOUBLETAP = 300


class KeyPress(IntEnum):
    RELEASED = 0
    PRESSED = 1
    REPEATED = 2


class Led(IntEnum):
    LED_NUML = 0
    LED_CAPSL = 1
    LED_SCROLLL = 2
    LED_COMPOSE = 3
    LED_KANA = 4


class RepeatConfig(IntEnum):
    REP_DELAY = 0
    REP_PERIOD = 1
