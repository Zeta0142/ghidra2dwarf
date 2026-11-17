#!/usr/bin/env python3

from pathlib import Path

from util import Gdb


def find_line(filename: str, needle: str) -> int:
    for number, line in enumerate(Path(filename).read_text().splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found in {filename}")


def test_function():
    gdb = Gdb("binaries", "rsa_dbg")

    info = gdb.execute_gdb("info line RSA_private_encrypt")
    assert "RSA_private_encrypt" in info

    line = find_line("binaries/rsa_dbg.c", "int RSA_private_encrypt")
    assert "RSA_private_encrypt" in gdb.get_line(line)
