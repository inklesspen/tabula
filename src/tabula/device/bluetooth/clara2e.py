from __future__ import annotations

import contextlib
import functools
import pty

import tricycle
import trio
import trio.lowlevel

from .bluez import BluezContext


@contextlib.asynccontextmanager
async def kmods():
    lsmod = await trio.run_process(["lsmod"], capture_stdout=True)
    loaded_mods = [line.split()[0] for line in lsmod.stdout.decode().splitlines() if line]
    # print(f"loaded mods at start: {loaded_mods}")
    need_uhid = "uhid" not in loaded_mods
    need_pwr = "sdio_bt_pwr" not in loaded_mods

    if need_uhid:
        await trio.run_process(["insmod", "/opt/modules/uhid.ko"])
    if need_pwr:
        await trio.run_process(["insmod", "/drivers/mx6sll-ntx/wifi/sdio_bt_pwr.ko"])
    yield True
    if need_pwr:
        await trio.run_process(["rmmod", "sdio_bt_pwr"])
    if need_uhid:
        await trio.run_process(["rmmod", "uhid"])


async def hciattach(nursery: trio.Nursery, *, task_status=trio.TASK_STATUS_IGNORED):
    expected = "Device setup complete"
    # hciattach is going to buffer its stdout, no matter whether or not it's buffered on our side.
    # that's just part of libc's behavior: https://www.gnu.org/software/libc/manual/html_node/Buffering-Concepts.html
    # the workarounds are to use stdbuf (part of GNU coreutils, not yet part of busybox) or use a pty
    # so we use a pty (which triggers libc to use line buffering)
    pty_m, pty_s = pty.openpty()
    async with tricycle.TextReceiveStream(trio.lowlevel.FdStream(pty_m)) as stdout:
        hci = await nursery.start(
            functools.partial(trio.run_process, ["/sbin/hciattach", "-n", "ttymxc1", "any", "1500000", "flow", "-t", "20"], stdout=pty_s)
        )
        with trio.move_on_after(10):
            line = (await stdout.receive_line()).strip()
            if line != expected:
                raise Exception(f"hciattach went wrong; expected {expected!r} but got {line!r}")
        task_status.started(hci)
        await hci.wait()


@contextlib.asynccontextmanager
async def bluetooth():
    async with kmods(), BluezContext() as bluezcontext:
        await bluezcontext.nursery.start(hciattach, bluezcontext.nursery)
        await bluezcontext.ensure_adapter_powered_on()
        yield bluezcontext
