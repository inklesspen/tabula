#!/usr/bin/env python3
# This should be made a utility package that can be added to build-system.requires.
# And also should probably handle errors better.
import argparse
import pathlib

from cffi.api import FFI
from cffi.recompiler import Recompiler

parser = argparse.ArgumentParser()
parser.add_argument("--ffivar", default="ffibuilder")
parser.add_argument("infile", type=pathlib.Path)
parser.add_argument("outfile", type=pathlib.Path)


def execfile(srcfile: pathlib.Path, globs: dict):
    compiled = compile(source=srcfile.read_text(), filename=srcfile, mode="exec")
    exec(compiled, globs, globs)


def get_ffi(srcfile: pathlib.Path, ffivar: str):
    globs = {}
    execfile(srcfile, globs)
    if ffivar not in globs:
        raise NameError()
    ffi = globs[ffivar]
    if not isinstance(ffi, FFI) and callable(ffi):
        # Maybe it's a callable that returns a FFI
        ffi = ffi()
    if not isinstance(ffi, FFI):
        raise TypeError()
    return ffi


def main():
    args = parser.parse_args()
    ffi = get_ffi(args.infile, args.ffivar)
    # TODO: improve this; https://github.com/python-cffi/cffi/issues/47
    module_name, source, source_extension, kwds = ffi._assigned_source
    recompiler = Recompiler(ffi, module_name)
    recompiler.collect_type_table()
    recompiler.collect_step_tables()
    with args.outfile.open("w") as f:
        recompiler.write_source_to_f(f, source)


if __name__ == "__main__":
    main()
