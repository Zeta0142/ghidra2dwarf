#!/usr/bin/env python3

from pathlib import Path

from util import Gdb


def find_line(filename: str, needle: str) -> int:
    for number, line in enumerate(Path(filename).read_text().splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found in {filename}")


def test_function():
    gdb = Gdb("binaries", "passcode_dbg")

    info = gdb.execute_gdb("info line login")
    assert "login" in info

    line = find_line("binaries/passcode_dbg.c", "void login(void)")
    assert "login" in gdb.get_line(line)
