#!/usr/bin/env python3
# This should be made a utility package that can be added to build-system.requires.
# And also should probably handle errors better.
import argparse
import pathlib

from cffi.api import FFI
from cffi.recompiler import Recompiler

parser = argparse.ArgumentParser()
parser.add_argument("--modulename", required=True)
parser.add_argument("--cdef", type=pathlib.Path, required=True)
parser.add_argument("--csrc", type=pathlib.Path, required=True)
parser.add_argument("--output", type=argparse.FileType("w", encoding="utf-8"), required=True)


def make_ffi(modulename: str, cdef: pathlib.Path, csrc: pathlib.Path):
    ffibuilder = FFI()
    ffibuilder.cdef(cdef.read_text())
    ffibuilder.set_source(modulename, csrc.read_text())
    return ffibuilder


def main():
    args = parser.parse_args()
    ffi = make_ffi(args.modulename, args.cdef, args.csrc)
    # TODO: improve this; https://github.com/python-cffi/cffi/issues/47
    module_name, source, source_extension, kwds = ffi._assigned_source
    recompiler = Recompiler(ffi, module_name)
    recompiler.collect_type_table()
    recompiler.collect_step_tables()
    with args.output as f:
        recompiler.write_source_to_f(f, source)


if __name__ == "__main__":
    main()
