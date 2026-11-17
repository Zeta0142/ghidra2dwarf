#!/usr/bin/env python3

from pathlib import Path

from util import Gdb


def find_line(filename: str, needle: str) -> int:
    for number, line in enumerate(Path(filename).read_text().splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found in {filename}")


def test_function():
    gdb = Gdb("binaries", "test_ghidra_dbg")

    line_example_1 = find_line(
        "binaries/test_ghidra_dbg.c", '= "Example 1";'
    )
    line_example_2 = find_line(
        "binaries/test_ghidra_dbg.c", '= "Example 2";'
    )

    gdb.breakpoint(line_example_1)
    gdb.breakpoint(line_example_2)
    gdb.run()

    assert "Example 1" in gdb.get_line(line_example_1)
    gdb.execute_raw("c")
    assert "Example 2" in gdb.get_line(line_example_2)
