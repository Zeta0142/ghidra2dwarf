#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path

import pytest

BINARIES = ("test_ghidra", "passcode", "rsa")
ENV = dict(os.environ, LC_ALL="C")


@pytest.mark.parametrize("name", BINARIES)
def test_sections(name: str) -> None:
    binary = Path("binaries") / (name + "_dbg")
    assert binary.is_file(), f"missing {binary}; run generate_dbg.py first"

    sections = subprocess.check_output(
        ["readelf", "-S", str(binary)],
        text=True,
        env=ENV,
    )
    for section in (".debug_info", ".debug_line", ".debug_abbrev"):
        assert section in sections


@pytest.mark.parametrize("name", BINARIES)
def test_debug_info_and_line_table(name: str) -> None:
    binary = Path("binaries") / (name + "_dbg")

    info = subprocess.check_output(
        ["readelf", "--debug-dump=info", str(binary)],
        text=True,
        env=ENV,
    )
    assert "DW_TAG_compile_unit" in info

    lines = subprocess.check_output(
        ["readelf", "--debug-dump=line", str(binary)],
        text=True,
        env=ENV,
    )
    assert "The File Name Table" in lines
    assert "Line Number Statements" in lines
