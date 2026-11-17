#!/usr/bin/env python3
"""Proof-of-concept: generate DWARF with libdwarfp through ctypes.

This does not talk to Ghidra yet.  It builds a tiny, valid DWARF compilation
unit and a line table, then optionally injects the resulting .debug_* sections
into a copy of an ELF using objcopy.

The point is to validate the native bridge:

    CPython 3 -> ctypes -> libdwarfp 2.3.x -> .debug_* bytes -> ELF

Ghidra is deliberately not required for this native-binding smoke test.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from libdwarfp import (
    DW_ATE_signed,
    DW_AT_byte_size,
    DW_AT_comp_dir,
    DW_AT_decl_file,
    DW_AT_decl_line,
    DW_AT_encoding,
    DW_AT_frame_base,
    DW_AT_high_pc,
    DW_AT_linkage_name,
    DW_AT_location,
    DW_AT_low_pc,
    DW_AT_name,
    DW_AT_type,
    DW_OP_call_frame_cfa,
    DW_OP_fbreg,
    DW_TAG_base_type,
    DW_TAG_compile_unit,
    DW_TAG_subprogram,
    DW_TAG_variable,
    DwarfProducer,
)

SOURCE = """\
int main(void) {
  int x = 1;
  return x;
}
"""


def build_sections() -> dict[str, bytes]:
    with DwarfProducer(isa_name="x86_64", dwarf_version="V4") as producer:
        producer.set_default_string_form()

        cu = producer.new_die(DW_TAG_compile_unit)
        producer.add_name(cu, "sample.c")
        producer.add_comp_dir(cu, ".")

        dir_index = producer.add_directory_decl(".")
        file_index = producer.add_file_decl("sample.c", dir_index)

        int_type = producer.new_die(DW_TAG_base_type, parent=cu)
        producer.add_name(int_type, "int")
        producer.add_unsigned_const(int_type, DW_AT_byte_size, 4)
        producer.add_unsigned_const(int_type, DW_AT_encoding, DW_ATE_signed)

        func = producer.new_die(DW_TAG_subprogram, parent=cu)
        producer.add_name(func, "main")
        producer.add_string(func, DW_AT_linkage_name, "main")
        producer.add_reference(func, DW_AT_type, int_type)
        producer.add_targ_address(func, DW_AT_low_pc, 0x1000)
        producer.add_targ_address(func, DW_AT_high_pc, 0x1014)
        producer.add_unsigned_const(func, DW_AT_decl_file, file_index)
        producer.add_unsigned_const(func, DW_AT_decl_line, 1)

        frame_base = producer.new_expr()
        producer.add_expr_gen(frame_base, DW_OP_call_frame_cfa)
        producer.add_location_expr(func, DW_AT_frame_base, frame_base)

        variable = producer.new_die(DW_TAG_variable, parent=func)
        producer.add_name(variable, "x")
        producer.add_reference(variable, DW_AT_type, int_type)

        var_expr = producer.new_expr()
        producer.add_expr_gen(var_expr, DW_OP_fbreg, 0)
        producer.add_location_expr(variable, DW_AT_location, var_expr)

        producer.add_die_to_debug(cu)

        producer.add_line_entry(file_index, 0x1000, 1, is_stmt=True)
        producer.add_line_entry(file_index, 0x1004, 2, is_stmt=True)
        producer.add_line_entry(file_index, 0x1008, 3, is_stmt=True)
        producer.end_sequence(0x1014)

        return producer.transform()


def add_sections_with_objcopy(
    base_elf: Path, out_elf: Path, sections: dict[str, bytes], workdir: Path
) -> None:
    shutil.copy2(base_elf, out_elf)
    cmd = ["objcopy"]
    for name, data in sections.items():
        path = workdir / name.lstrip(".")
        path.write_bytes(data)
        cmd += ["--add-section", f"{name}={path}"]
    cmd += [str(out_elf)]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/tmp/ghidra2dwarf-smoke"),
        help="output directory",
    )
    parser.add_argument(
        "--base-elf",
        type=Path,
        default=Path("test/binaries/test_ghidra"),
        help="ELF to copy and inject the generated sections into",
    )
    parser.add_argument(
        "--no-objcopy",
        action="store_true",
        help="only write section files, do not create an ELF",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    source_path = args.out / "sample.c"
    source_path.write_text(SOURCE, encoding="utf-8")

    sections = build_sections()
    if not sections:
        print("error: libdwarfp returned no sections", file=sys.stderr)
        return 1

    print("generated sections:")
    for name, data in sorted(sections.items()):
        path = args.out / name.lstrip(".")
        path.write_bytes(data)
        print(f"  {name:16s} {len(data):6d} bytes -> {path}")

    if args.no_objcopy:
        print(f"\nsource: {source_path}")
        return 0

    base_elf = args.base_elf
    if not base_elf.is_file():
        print(f"error: base ELF not found: {base_elf}", file=sys.stderr)
        print("use --base-elf PATH or --no-objcopy", file=sys.stderr)
        return 1

    out_elf = args.out / (base_elf.name + "_dbg")
    try:
        add_sections_with_objcopy(base_elf, out_elf, sections, args.out)
    except FileNotFoundError:
        print("error: objcopy not found; rerun with --no-objcopy", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"error: objcopy failed: {exc}", file=sys.stderr)
        return 1

    print(f"\nsource: {source_path}")
    print(f"ELF:    {out_elf}")
    print("\nverify with:")
    print(f"  readelf --debug-dump=info,line {out_elf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
