# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from cffi import FFI

ffibuilder = FFI()

ffibuilder.cdef('''
    int mount(const char *source, const char *target,
                 const char *filesystemtype, unsigned long mountflags,
                 const void *data);
    int umount(const char *target);

    #define EAGAIN ...
    #define EBUSY ...
    #define EFAULT ...
    #define EINVAL ...
    #define ENAMETOOLONG ...
    #define ENOENT ...
    #define ENOMEM ...
    #define EPERM ...
''')

ffibuilder.set_source(
    'notare.gadget._mount',
    '''
    #include <sys/mount.h>
    #include <errno.h>
    '''
)
