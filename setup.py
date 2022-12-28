#!/usr/bin/env python

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# -*- encoding: utf-8 -*-

from glob import glob
from os.path import basename
from os.path import splitext
import platform

from setuptools import find_packages
from setuptools import setup

EXTENSIONBUILDERS_BY_PLATFORM = {
    "Linux": {
        "src/tabula/device/_fbink_build.py",
        "src/tabula/rendering/_cairopango_build.py",
    },
    # fbink can't build on Mac OS, so don't even bother.
    "Darwin": {"src/tabula/rendering/_cairopango_build.py"},
}


setup(
    name="tabula",
    version="0.0.0",
    license="GPL-3.0-or-later",
    description="cool as hecc",
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
        "markdown-it-py",
        "cardinality>=0.1.1",
        "numpy>=1.20.3",
        "Pillow>=8.3.1",
        "pygtrie>=2.4.2",
        "python-dateutil>=2.8.1",
        "timeflake>=0.4.0",
        "tomli>=1.1.0",
        "trio>=0.20.0",
        "trio-util>=0.7.0",
        "tricycle>=0.2.1",
        "sqlalchemy>=1.4.18",
        "msgspec",
        # eg: 'aspectlib==1.1.1', 'six>=1.7',
    ],
    tests_require=["pytest>=6.2.4", "Pillow>=8.2.0"],
    extras_require={
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
    },
    # We only require CFFI when compiling.
    # pyproject.toml does not support requirements only for some build actions,
    # but we can do it in setup.py.
    setup_requires=[
        "setuptools>=30.3.0",
        "wheel",
        "cffi>=1.0.0",
    ],
    # cmdclass={"build_ext": optional_build_ext},
    cffi_modules=[
        i + ":ffibuilder"
        for i in glob("src/**/_*_build.py", recursive=True)
        if i in EXTENSIONBUILDERS_BY_PLATFORM[platform.system()]
    ],
)
