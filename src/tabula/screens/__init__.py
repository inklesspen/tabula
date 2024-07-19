from .base import Screen, TargetDialog, TargetScreen
from .dialogs import Dialog, OkDialog, YesNoDialog
from .drafting import Drafting
from .fonts import Fonts
from .help import ComposeHelp, Help
from .keyboard_detect import KeyboardDetectDialog
from .menus import SessionActions, SessionList, SystemMenu
from .sprint_control import SprintControl

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
