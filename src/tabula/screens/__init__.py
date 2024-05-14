from .base import TargetScreen
from .keyboard_detect import KeyboardDetect
from .menus import SystemMenu, SessionList, SessionChoices
from .fonts import Fonts
from .drafting import Drafting
from .help import Help, ComposeHelp
from .sprint_control import SprintControl

SCREENS = {
    TargetScreen.KeyboardDetect: KeyboardDetect,
    TargetScreen.SystemMenu: SystemMenu,
    TargetScreen.Drafting: Drafting,
    TargetScreen.SessionList: SessionList,
    TargetScreen.SessionChoices: SessionChoices,
    TargetScreen.Fonts: Fonts,
    TargetScreen.Help: Help,
    TargetScreen.ComposeHelp: ComposeHelp,
    TargetScreen.SprintControl: SprintControl,
}
