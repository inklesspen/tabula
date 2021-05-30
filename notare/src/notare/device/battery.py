# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import pathlib

import trio
from tricycle import BackgroundObject

from ..protocol import BatteryState, ChargingState

BATTERY_DIR = pathlib.Path(
    "/sys/devices/platform/pmic_battery.1/power_supply/mc13892_bat/"
)
CAPACITY = BATTERY_DIR / "capacity"
STATUS = BATTERY_DIR / "status"


def has_kobo_battery_state():
    return BATTERY_DIR.is_dir() and CAPACITY.is_file() and STATUS.is_file()


def get_kobo_battery_state() -> BatteryState:
    return BatteryState(
        state=STATUS.read_text().strip(), current_charge=CAPACITY.read_text().strip()
    )


def get_fake_battery_state() -> BatteryState:
    return BatteryState.construct(state=ChargingState.NOT_CHARGING, current_charge=42)


class Battery(BackgroundObject, daemon=True):
    current_state: BatteryState

    def __init__(self):
        self.is_kobo = has_kobo_battery_state()
        self._update()

    def _update(self):
        self.current_state = (
            get_kobo_battery_state() if self.is_kobo else get_fake_battery_state()
        )

    async def __open__(self) -> None:
        self.nursery.start_soon(self._update_periodically)

    async def _update_periodically(self) -> None:
        while True:
            self._update()
            await trio.sleep(5)

    def get(self) -> BatteryState:
        return self.current_state
