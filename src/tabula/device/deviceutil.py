import fcntl
import os
from contextlib import contextmanager

import libevdev


@contextmanager
def open_device(devpath):
    f = open(devpath, "r+b", buffering=0)
    fcntl.fcntl(f, fcntl.F_SETFL, os.O_NONBLOCK)
    d = libevdev.Device(f)
    d.grab()
    try:
        yield d
    finally:
        f.close()
