#!/usr/bin/env python

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# -*- encoding: utf-8 -*-

from glob import glob
from os.path import basename
from os.path import splitext
import platform

from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError
from setuptools import find_packages
from setuptools import setup
from setuptools.command.build_ext import build_ext

EXPECTED_TO_BUILD_ON = {"stilus._cffi": ("Linux", "Darwin")}


class optional_build_ext(build_ext):
    """Allow the building of C extensions to fail."""

    def build_extension(self, ext):
        extname = ext.name.split(".", 1)[1]
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError) as e:
            if platform.system() in EXPECTED_TO_BUILD_ON.get(extname, tuple()):
                raise
            if extname not in EXPECTED_TO_BUILD_ON:
                self._unavailable(extname, e)

            self.extensions.remove(ext)

    def _unavailable(self, extname, e):
        print("*" * 80)
        print(
            f"WARNING: {extname} failed to compile and we couldn't tell if that's okay!"
        )

        print("CAUSE:")
        print("")
        print("    " + repr(e))
        print("*" * 80)


setup(
    name="stilus",
    version="0.0.0",
    license="GPL-3.0-or-later",
    description="pango wrapper",
    long_description="TODO",
    author="Rose Davidson",
    author_email="rose@metaclassical.com",
    url="https://github.com/inklesspen/tabula",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)"
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Artistic Software",
        "Topic :: Text Editors :: Word Processors",
        "Topic :: Text Processing :: Fonts",
        "Topic :: Text Processing :: Markup :: Markdown",
    ],
    project_urls={
        "Changelog": "https://github.com/inklesspen/tabula/blob/master/CHANGELOG.md",
        "Issue Tracker": "https://github.com/inklesspen/tabula/issues",
    },
    keywords=[
        # eg: 'keyword1', 'keyword2', 'keyword3',
    ],
    python_requires=">=3.8",
    install_requires=[
        "cffi>=1.0.0",
        "attrs",
        "numpy>=1.20.3",
        "markdown-it-py",
        # eg: 'aspectlib==1.1.1', 'six>=1.7',
    ],
    tests_require=["pytest>=6.2.4", "Pillow>=8.2.0"],
    extras_require={
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
    },
    setup_requires=[
        "setuptools>=30.3.0",
        "wheel",
        "cffi>=1.0.0",
    ],
    cmdclass={"build_ext": optional_build_ext},
    cffi_modules=[
        i + ":ffibuilder" for i in glob("src/**/_*_build.py", recursive=True)
    ],
)
