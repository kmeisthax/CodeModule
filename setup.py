#!/usr/bin/env python3
from distutils.core import setup

setup(name = "CodeModule",
    version = '0.1',
    description = "Python utility for dealing with low-level programs.",
    author = "David Wendt",
    author_email = "dcrkid@yahoo.com",
    packages = ["CodeModule", "CodeModule.asm", "CodeModule.systems", "CodeModule.fileops", "CodeModule.games"],
    package_dir = {'': "py"},
    scripts = ["scripts/codemodule"])
