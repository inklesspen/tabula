#!/usr/bin/env python

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# -*- encoding: utf-8 -*-

from glob import glob
from os.path import basename
from os.path import splitext

from setuptools import find_packages
from setuptools import setup


setup(
    name="notare",
    version="0.0.0",
    license="GPL-3.0-or-later",
    description="glue",
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
        "attrs",
        "cardinality>=0.1.1",
        "pydantic>=1.8.2",
        "python-dateutil>=2.8.1",
        "timeflake>=0.4.0",
        "toml>=0.10.2",
        "trio>=0.18.0",
        "trio-jsonrpc>=0.4.0",
        "trio-util>=0.5.0",
        "tricycle>=0.2.1",
        # eg: 'aspectlib==1.1.1', 'six>=1.7',
    ],
    extras_require={
        "host": [
            "numpy>=1.20.3",
            "urwid>=2.1.2",
            "xdg>=5.1.0",
            "sqlalchemy>=1.4.18",
            "aiosqlite>=0.17.0",
        ]
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
    },
    tests_require=["pytest>=6.2.4", "Pillow>=8.2.0"],
)
