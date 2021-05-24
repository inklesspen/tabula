<!--
SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>

SPDX-License-Identifier: CC0-1.0
-->

Directories asm, asm-generic, linux should be _directly_ next to this file, **not** nested inside an include directory

These directories come from the `make headers_install` target in the Linux kernel source tree.

As of this writing, you will need to download Kobo's provided [kernel source](https://github.com/kobolabs/Kobo-Reader/raw/master/hw/imx6sll-clara/kernel.tar.bz2) and extract it on a case-sensitive filesystem. (Most Mac OS filesystems are case-insensitive; this is a problem because of certain files in the kernel source tree.)

Then you need to download the [mainline kernel source](https://mirrors.edge.kernel.org/pub/linux/kernel/v4.x/linux-4.1.15.tar.gz), unpack that, and replace `include/uapi/linux/netfilter*` in Kobo's tree with the corresponding globfiles from the mainline tree.

Finally, get the kernel config from your Kobo (`/proc/config.gz`), ungzip it, put it in your Kobo kernel tree.

Run `make olddefconfig`, then `make headers_install ARCH=arm INSTALL_HDR_PATH=/your/output/path`.

There will be a whole lot of files in there that you **don't** need, along with all the ones you do need.

These files are all licensed under GPL 2.0 with the Linux-syscall-note, as explained in https://github.com/torvalds/linux/commit/e2be04c7f9958dde770eeb8b30e829ca969b37bb
