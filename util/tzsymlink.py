#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later

import os
import os.path

KOBO_LOCALTIME = "/koboroot/etc/localtime"
ALPINE_LOCALTIME = "/etc/localtime"
ZONEINFOS = "/usr/share/zoneinfo"

kobo_target = os.readlink(KOBO_LOCALTIME)
components = []
currently = kobo_target
while os.path.basename(currently) != "zoneinfo":
    currently, lastpart = os.path.split(currently)
    components.insert(0, lastpart)

components.insert(0, ZONEINFOS)
alpine_target = os.path.join(*components)

if os.path.lexists(ALPINE_LOCALTIME):
    os.unlink(ALPINE_LOCALTIME)

os.symlink(alpine_target, ALPINE_LOCALTIME)
