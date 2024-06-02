from .base import TargetScreen, TargetDialog, Screen
from .menus import SystemMenu, SessionList, SessionActions
from .fonts import Fonts
from .drafting import Drafting
from .help import Help, ComposeHelp
from .keyboard_detect import KeyboardDetectDialog
from .sprint_control import SprintControl
from .dialogs import Dialog, OkDialog, YesNoDialog

SCREENS: dict[TargetScreen, type[Screen]] = {
    TargetScreen.SystemMenu: SystemMenu,
    TargetScreen.Drafting: Drafting,
    TargetScreen.SessionList: SessionList,
    TargetScreen.SessionActions: SessionActions,
    TargetScreen.Fonts: Fonts,
}

DIALOGS: dict[TargetDialog, type[Dialog]] = {
    TargetDialog.Ok: OkDialog,
    TargetDialog.YesNo: YesNoDialog,
    TargetDialog.Help: Help,
    TargetDialog.ComposeHelp: ComposeHelp,
    TargetDialog.KeyboardDetect: KeyboardDetectDialog,
    TargetDialog.SprintControl: SprintControl,
}
