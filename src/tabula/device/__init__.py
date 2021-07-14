# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Keyboard event stages
# device level:
# stage 0: OS-specific; watch keyboard device and issue keystream, or issue pre-recorded keystream

# editor level:
# stage 1: track modifier keydown/up and annotate keystream with current modifiers
# stage 2: convert key event + modifier into character or special key code
# stage 3: compose sequences
