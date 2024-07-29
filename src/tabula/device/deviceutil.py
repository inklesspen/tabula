import collections.abc
import contextlib
import fcntl
import os
import pathlib
from contextlib import contextmanager

import libevdev

from .eventsource import Event


class EventDevice(contextlib.AbstractContextManager):
    def __init__(self, device_path: str | pathlib.Path, allow_auto_sync=False):
        self.allow_auto_sync = allow_auto_sync
        if not isinstance(device_path, pathlib.Path):
            device_path = pathlib.Path(device_path)
        if not device_path.is_absolute():
            raise ValueError("Device path must be absolute")
        self.device_path = device_path
        self._f = None
        self._d = None

    def __enter__(self):
        self._f = self.device_path.open("r+b", buffering=0)
        fcntl.fcntl(self._f, fcntl.F_SETFL, os.O_NONBLOCK)
        self._d = libevdev.Device(self._f)
        self._d.grab()
        return self

    def events(self) -> collections.abc.Iterator[Event]:
        if self._d is None:
            raise Exception("Must be within a context expression")

        resyncing = False
        events = self._d.events()
        while True:
            if resyncing:
                if self.allow_auto_sync:
                    for evt in self._d.sync():
                        yield Event.from_libevdev_event(evt)
                else:
                    # If we don't trust the auto-sync feature, then
                    # we just have to discard all events until the next
                    # SYN_REPORT (including that one).
                    synced = False
                    while not synced:
                        evt = next(events)
                        if evt.code == libevdev.EV_SYN.SYN_REPORT:
                            synced = True
                resyncing = False
            else:
                try:
                    evt = next(events)
                except StopIteration:
                    return
                except libevdev.EventsDroppedException:
                    resyncing = True
                else:
                    yield Event.from_libevdev_event(evt)

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self._f.close()
        self._d = None
        self._f = None
        return False  # to reraise exceptions if needed


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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("device", type=pathlib.Path)
    parser.add_argument("output", type=argparse.FileType(mode="w"))
    args = parser.parse_args()

    with EventDevice(args.device, allow_auto_sync=True) as device:
        args.output.write(f"# {args.device}\n")
        while True:
            try:
                for evt in device.events():
                    args.output.write(evt.to_log() + ",\n")
            except libevdev.EventsDroppedException as exc:
                args.output.write(f"# {exc!r}\n")
