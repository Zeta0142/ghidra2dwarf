# libdwarfp ctypes PoC

This directory is a proof-of-concept for the proposed migration:

```text
PyGhidra / CPython 3
        -> ctypes
        -> libdwarfp 2.3.x
        -> .debug_* sections
        -> ELF
```

It intentionally does **not** depend on Ghidra, Jython, JNA, or `libdwarf.jar`.
The goal is to validate the native bridge before changing the real script.

## What is verified

`make_dwarf.py` builds a tiny DWARF v4 compile unit with:

- one `DW_TAG_compile_unit`
- one `int` base type
- one `main` subprogram
- one stack variable
- a `.debug_line` line table for `sample.c`

Then it writes `.debug_abbrev`, `.debug_info`, and `.debug_line`, and optionally
uses `objcopy` to inject them into a copy of `test/binaries/test_ghidra`.

The generated sections were verified with `readelf`:

```text
DW_TAG_compile_unit
  DW_AT_name        : sample.c
  ...
  DW_TAG_subprogram
    DW_AT_name      : main
    DW_AT_low_pc    : 0x1000
    DW_AT_high_pc   : 0x1014
    DW_TAG_variable
      DW_AT_name    : x
```

Line table:

```text
0x1000  line 1
0x1004  line 2
0x1008  line 3
```

## Build the vendored libdwarf / libdwarfp

libdwarf 2.3.3 is vendored under `vendor/libdwarf/`.  Build it with:

```bash
poc/build_libdwarf.sh
```

The script writes to `build/libdwarf/` and uses `BUILD_DWARFGEN=ON` because, as
of libdwarf 2.3.3, CMake only adds `src/lib/libdwarfp` when dwarfgen is enabled.
We only need the library, not the `dwarfgen` executable.

Result:

```text
build/libdwarf/src/lib/libdwarf/libdwarf.so.2.3.3
build/libdwarf/src/lib/libdwarfp/libdwarfp.so.2.3.3
```

On macOS/Windows the names will be `libdwarf.dylib` / `libdwarfp.dylib` and
`libdwarf.dll` / `libdwarfp.dll`.

`poc/libdwarfp.py` automatically looks in `build/libdwarf/`, so no environment
variables are needed after this.  `LIBDWARFP_PATH` and `LIBDWARF_PATH` still
override the search when needed.

## Run the PoC

```bash
python3 poc/make_dwarf.py --out /tmp/ghidra2dwarf-libdwarfp-poc
```

Expected output:

```text
generated sections:
  .debug_abbrev        55 bytes
  .debug_info          81 bytes
  .debug_line          53 bytes

source: /tmp/ghidra2dwarf-libdwarfp-poc/sample.c
ELF:    /tmp/ghidra2dwarf-libdwarfp-poc/test_ghidra_dbg
```

Verify:

```bash
readelf --debug-dump=info,line /tmp/ghidra2dwarf-libdwarfp-poc/test_ghidra_dbg
```

If `objcopy` is unavailable:

```bash
python3 poc/make_dwarf.py --out /tmp/ghidra2dwarf-libdwarfp-poc --no-objcopy
```

## PyGhidra check

The same binding has been verified inside **PyGhidra 3.1.0 + Ghidra 12.1.3**,
headless, with Python 3.14.8:

```text
python: 3.14.8
ctypes: /usr/lib64/python3.14/ctypes/__init__.py
currentProgram: test_ghidra - .ProgramDB
libdwarfp module: .../poc/libdwarfp.py
sections: {'.debug_abbrev': 55, '.debug_info': 81, '.debug_line': 53}
RESULT: OK
```

Run it with a Python that has `pyghidra` installed:

```bash
GHIDRA_INSTALL_DIR=/path/to/ghidra \
PYGHIDRA_PYTHON=/path/to/venv/bin/python3 \
./poc/run_pyghidra_check.sh
```

The script is `poc/ghidra_scripts/pyghidra_ctypes_check.py`.

### Ghidra MCP note

If you want to run the check through Ghidra MCP's `run_ghidra_script`, the MCP
bridge must be started with:

```bash
export GHIDRA_MCP_ALLOW_SCRIPTS=1
```

Script execution is disabled by default in current ghidra-mcp versions.  The
headless PyGhidra command above does not need MCP script execution.

## Files

| Path | Purpose |
|---|---|
| `poc/libdwarfp.py` | ctypes prototypes + `DwarfProducer` wrapper |
| `poc/make_dwarf.py` | minimal DWARF producer and `objcopy` injection |
| `poc/build_libdwarf.sh` | builds the vendored libdwarf/libdwarfp |
| `poc/ghidra_scripts/pyghidra_ctypes_check.py` | PyGhidra smoke test |
| `poc/run_pyghidra_check.sh` | headless PyGhidra runner |
| `vendor/libdwarf/` | vendored libdwarf 2.3.3 source (LGPL-2.1) |
| `poc/README.md` | this file |

## Important notes

- `libdwarfp` is a **separate library** from `libdwarf`.
  Loading `libdwarf.so` alone will not give you `dwarf_producer_init`.
- The binding targets the modern `_a`/`_c` producer API:
  - `dwarf_new_die_a`
  - `dwarf_add_AT_*_a`
  - `dwarf_add_line_entry_c`
  - `dwarf_transform_to_disk_form_a`
  - `dwarf_get_section_bytes_a`
- The old JNA wrapper in `lib/` matches the 2021 fork, not current libdwarf.
  Do not point current `libdwarfp` at the old JNA binding.
- The callback object is kept alive on `DwarfProducer`; without that, Python
  may garbage-collect it and the native call can crash.
- `dwarf_get_section_bytes_a()` returns native memory owned by libdwarf.
  The PoC copies it with `ctypes.string_at()` before `finish()`.

## Next steps

This PoC only proves the native bridge. The next phase would:

1. Run the same binding from PyGhidra instead of plain CPython.
2. Replace the script's JNA calls with `DwarfProducer` calls.
3. Keep using the existing `elf.py` (after Python 3 port) or replace it.
4. Add a Ghidra/ELF end-to-end test with `gdb`.
