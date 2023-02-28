from .base import TargetScreen
from .keyboard_detect import KeyboardDetect
from .menus import SystemMenu, SessionList
from .fonts import Fonts
from .drafting import Drafting
from .help import Help, ComposeHelp

SCREENS = {
    TargetScreen.KeyboardDetect: KeyboardDetect,
    TargetScreen.SystemMenu: SystemMenu,
    TargetScreen.Drafting: Drafting,
    TargetScreen.SessionList: SessionList,
    TargetScreen.Fonts: Fonts,
    TargetScreen.Help: Help,
    TargetScreen.ComposeHelp: ComposeHelp,
}
