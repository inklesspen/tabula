# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import abc
import datetime
import typing
import unicodedata

import timeflake
import trio

from stilus.types import Size

from .config import Settings
from .db import TabulaDb, now
from .document import DocumentModel
from .help import HELP, COMPOSES_TEMPLATE
from .stub import Stub
from .types import DeviceInfo, Renderable
from .rendering import Screen, ModalDialog


async def _checkpoint():
    await trio.sleep(0)


class Loop(abc.ABC):
    def __init__(
        self,
        device_info: DeviceInfo,
        settings: Settings,
        db: TabulaDb,
        document: DocumentModel,
    ):
        self.device_info = device_info
        self.settings = settings
        self.db = db
        self.document = document
        self.setup()

    @classmethod
    def loops(cls):
        return cls.__subclasses__()

    def setup(self):
        raise NotImplementedError()

    async def activate(self, client: Stub):
        raise NotImplementedError()

    async def deactivate(self, client: Stub):
        raise NotImplementedError()

    async def handle_keystroke(self, keystroke: str):
        raise NotImplementedError()


# https://en.wikipedia.org/wiki/Enclosed_Alphanumerics
# U+24EA is zero; it's out of order from the rest
# U+2460 is 1, U+2468 is 9
# U+24CE is Y; U+24C3 is N
# these are all in Noto Sans Symbols.
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


def _parse_single_digit(keystroke):
    if len(keystroke) == 1 and keystroke >= "0" and keystroke <= "9":
        choice = ord(keystroke) - ord("0")
        return choice
    return None


def screen_size(device_info: DeviceInfo):
    return Size(width=device_info.width, height=device_info.height)


class SystemMenu(Loop):
    FONT = "Noto Serif 8"

    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )
        self.keymappings = {
            "1": "new_session",
            "2": "resume_session",
            "3": "set_font",
        }
        self.menulines = [
            {"code": CIRCLED_ALPHANUMERICS["1"], "text": "New Session"},
            {"code": CIRCLED_ALPHANUMERICS["2"], "text": "Resume Session"},
            None,
            {"code": CIRCLED_ALPHANUMERICS["3"], "text": "Set Font"},
            None,
        ]

        if self.settings.allow_markdown_export_to_device:
            self.menulines.extend(
                [
                    {
                        "code": CIRCLED_ALPHANUMERICS["4"],
                        "text": "Export Markdown to Host",
                    },
                    {
                        "code": CIRCLED_ALPHANUMERICS["5"],
                        "text": "Export Markdown to Device",
                    },
                ]
            )
            self.keymappings["4"] = "export_to_host"
            self.keymappings["5"] = "export_to_device"
            next_num = 6
        else:
            self.menulines.append(
                {"code": CIRCLED_ALPHANUMERICS["4"], "text": "Export Markdown"},
            )
            self.keymappings["4"] = "export_to_host"
            next_num = 5

        if self.settings.allow_setting_time:
            self.menulines.extend(
                [
                    None,
                    {
                        "code": CIRCLED_ALPHANUMERICS[str(next_num)],
                        "text": "Set System Time",
                    },
                ]
            )
            self.keymappings[f"{next_num}"] = "system_time"
            next_num += 1

        self.menulines.extend(
            [None, {"code": CIRCLED_ALPHANUMERICS["0"], "text": "Shutdown"}]
        )
        self.keymappings["0"] = "shutdown"

    def make_menu_markup(self):
        template = (
            '<span font="Noto Sans Symbols">{code}</span> \u00B7 \u00B7 \u00B7 {text}'
        )
        menu = []
        for line in self.menulines:
            if line is None:
                menu.append("")
            else:
                menu.append(template.format(**line))
        return "\n".join(menu)

    async def activate(self, client: Stub):
        await _checkpoint()
        framelets = self.modal.render_dialog(self.make_menu_markup(), self.FONT)
        await client.update_screen(framelets)

    async def deactivate(self, client):
        await _checkpoint()

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if keystroke in self.keymappings:
            return await getattr(self, f"handle_{self.keymappings[keystroke]}")()
        if keystroke == "esc":
            return ["switch_loop", Drafting]
        if keystroke == "f1":
            return ["switch_loop", Help]
        return ["nothing"]

    async def handle_new_session(self):
        await _checkpoint()
        session_id = self.db.new_session()
        await self.document.load_session(session_id)
        return ["switch_loop", Drafting]

    async def handle_resume_session(self):
        await _checkpoint()
        return ["switch_loop", SessionList]

    async def handle_set_font(self):
        await _checkpoint()
        return ["switch_loop", Fonts]

    async def handle_export_to_host(self):
        await _checkpoint()
        # return ["switch_loop", SessionList]
        return ["nothing"]

    async def handle_export_to_device(self):
        await _checkpoint()
        # return ["switch_loop", SessionList]
        return ["nothing"]

    async def handle_system_time(self):
        await _checkpoint()
        return ["switch_loop", Clocks]

    async def handle_shutdown(self):
        await _checkpoint()
        return ["shutdown"]


class SessionList(Loop):
    FONT = "Noto Serif 8"

    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )

    def make_menu_markup(self, sessions):
        template = (
            '<span font="Noto Sans Symbols">{code}</span> \u00B7 \u00B7 \u00B7 {text}'
        )
        menu = []
        for i, session in enumerate(sessions, start=1):
            deets = f"Started {session.started_on} — {session.wordcount} words"
            menu.append(template.format(code=CIRCLED_ALPHANUMERICS[str(i)], text=deets))
        # TODO: give an explanation if there aren't any sessions
        menu.append(template.format(code=CIRCLED_ALPHANUMERICS["0"], text="Back"))
        return "\n".join(menu)

    async def activate(self, client: Stub):
        await _checkpoint()
        # TODO: maybe need to filter for exportable
        self.sessions = self.db.list_sessions(limit=9)
        framelets = self.modal.render_dialog(
            self.make_menu_markup(self.sessions), self.FONT
        )
        await client.update_screen(framelets)

    async def deactivate(self, client: Stub):
        await _checkpoint()
        self.sessions = []

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if keystroke == "0" or keystroke == "f12":
            return ["switch_loop", SystemMenu]
        if (parsed := _parse_single_digit(keystroke)) is not None:
            index = parsed - 1
            if index < len(self.sessions):
                # TODO: maybe need to export instead of load
                await self.document.load_session(self.sessions[index].id)
                return ["switch_loop", Drafting]
        return ["nothing"]


class Fonts(Loop):
    FONT = "Noto Serif 8"

    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )

    def make_menu_markup(self):
        fontoptions = self.settings.drafting_fonts[:9]
        template = (
            '<span font="Noto Sans Symbols">{code}</span> \u00B7 \u00B7 \u00B7 {text}'
        )
        menu = []
        for i, font in enumerate(fontoptions, start=1):
            fontmarkup = f'<span font="{font}">{font}</span>'
            menu.append(
                template.format(code=CIRCLED_ALPHANUMERICS[str(i)], text=fontmarkup)
            )
        menu.append(template.format(code=CIRCLED_ALPHANUMERICS["0"], text="Back"))
        return "\n".join(menu)

    async def activate(self, client: Stub):
        await _checkpoint()
        framelets = self.modal.render_dialog(self.make_menu_markup(), self.FONT)
        await client.update_screen(framelets)

    async def deactivate(self, client: Stub):
        await _checkpoint()

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if keystroke == "0" or keystroke == "f12":
            return ["switch_loop", SystemMenu]
        if (parsed := _parse_single_digit(keystroke)) is not None:
            index = parsed - 1
            new_font = self.settings.drafting_fonts[index]
            await self.document.set_font(new_font)
            return [
                "switch_loop",
                Drafting if self.document.has_session else SystemMenu,
            ]

        return ["nothing"]


class Clocks(Loop):
    FONT = "Noto Serif 8"

    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )

    async def activate(self, client: Stub):
        await _checkpoint()
        host_time = now()
        device_time = (await client.get_current_time()).now
        letter_y = (
            f"<span font=\"Noto Sans Symbols\">{CIRCLED_ALPHANUMERICS['Y']}</span>"
        )
        letter_n = (
            f"<span font=\"Noto Sans Symbols\">{CIRCLED_ALPHANUMERICS['N']}</span>"
        )
        rows = [f"Host time: {host_time}", f"Device time: {device_time}", ""]
        self.can_change = abs(host_time - device_time) > datetime.timedelta(minutes=5)
        if self.can_change:
            rows.extend(
                [
                    "Change host time to match device time?",
                    f"{letter_y}es",
                    f"{letter_n}o",
                ]
            )
        else:
            rows.append("Press any key to close.")
        markup = "\n".join(rows)
        framelets = self.modal.render_dialog(markup, self.FONT)
        await client.update_screen(framelets)

    async def deactivate(self, client: Stub):
        await _checkpoint()

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if not self.can_change:
            return ["switch_loop", SystemMenu]
        if keystroke not in {"Y", "y", "N", "n"}:
            return ["nothing"]
        if keystroke.lower() == "y":
            return ["set_time"]
        else:
            return ["switch_loop", SystemMenu]


class Help(Loop):
    FONT = "Noto Serif 8"

    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )

    async def activate(self, client: Stub):
        await _checkpoint()
        framelets = self.modal.render_dialog(HELP, self.FONT)
        await client.update_screen(framelets)

    async def deactivate(self, client: Stub):
        await _checkpoint()

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if keystroke == "f2":
            return ["switch_loop", ComposeHelp]
        elif keystroke == "f12":
            return ["switch_loop", SystemMenu]
        return ["switch_loop", Drafting]


class ComposeHelp(Loop):
    FONT = "Noto Serif 6"

    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )

    async def activate(self, client: Stub):
        await _checkpoint()
        markup = COMPOSES_TEMPLATE.format(composekey=self.settings.compose_key)
        framelets = self.modal.render_dialog(markup, self.FONT)
        await client.update_screen(framelets)

    async def deactivate(self, client: Stub):
        await _checkpoint()

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if keystroke == "f1":
            return ["switch_loop", Help]
        elif keystroke == "f12":
            return ["switch_loop", SystemMenu]
        return ["switch_loop", Drafting]


class Sprint(Loop):
    def setup(self):
        self.modal = ModalDialog(
            screen_size=screen_size(self.device_info), dpi=self.device_info.dpi
        )

    async def activate(self, client: Stub):
        await _checkpoint()

    async def deactivate(self, client: Stub):
        await _checkpoint()

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()


def graphical_char(c: typing.Text):
    category = unicodedata.category(c)
    return category == "Zs" or category[0] in ("L", "M", "N", "P", "S")


class Drafting(Loop):
    def setup(self):
        self.screen = Screen(screen_size(self.device_info), self.device_info.dpi)

    async def activate(self, client: Stub):
        await client.restore_screen()
        self.screen.set_font(self.document.font)
        self.client = client

    async def deactivate(self, client: Stub):
        await client.save_screen()
        self.client = None

    async def handle_keystroke(self, keystroke: str):
        await _checkpoint()
        if len(keystroke) == 1 and graphical_char(keystroke):
            await self.document.keystroke(keystroke)
        elif keystroke == "enter":
            await self.document.new_para()
        elif keystroke == "backspace":
            await self.document.backspace()
        elif keystroke == "f1":
            return ["switch_loop", Help]
        elif keystroke == "f2":
            return ["switch_loop", ComposeHelp]
        elif keystroke == "f12":
            return ["switch_loop", SystemMenu]
        return ["nothing"]

    async def handle_dirty_updates(
        self, dirty_paragraph_ids: typing.Iterable[timeflake.Timeflake]
    ):
        paras = [self.document[para_id] for para_id in dirty_paragraph_ids]
        renderables = [
            Renderable(
                index=para.index,
                markup=para.markup,
                has_cursor=(para.id == self.document.cursor_para_id),
            )
            for para in paras
        ]
        framelets = self.screen.render_update(renderables)
        if framelets:
            await self.client.update_screen(framelets)
