# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import socket


def notify_ready():
    sock = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_DGRAM)
    addr = os.getenv("NOTIFY_SOCKET")
    msg = b"READY=1\n"
    sock.sendto(msg, addr)
