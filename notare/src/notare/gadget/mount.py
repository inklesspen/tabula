# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import pathlib

from ._mount import lib as mountlib, ffi as mountffi

_ERRNO_NAMES = (
    "EAGAIN",
    "EBUSY",
    "EFAULT",
    "EINVAL",
    "ENAMETOOLONG",
    "ENOENT",
    "ENOMEM",
    "EPERM",
)

ERRNO_MAP = {getattr(mountlib, name): name for name in _ERRNO_NAMES}


def mount_ffs(ffs_name: str, mountpoint: pathlib.Path):
    r = mountlib.mount(
        os.fsencode(ffs_name), bytes(mountpoint), b"functionfs", 0, mountffi.NULL
    )
    if r != 0:
        raise Exception(
            "error {} in mount(), not handled yet".format(
                ERRNO_MAP.get(mountffi.errno, mountffi.errno)
            )
        )


def umount_ffs(mountpoint: pathlib.Path):
    r = mountlib.umount(bytes(mountpoint))
    if r != 0:
        raise Exception(
            "error {} in umount(), not handled yet".format(
                ERRNO_MAP.get(mountffi.errno, mountffi.errno)
            )
        )
