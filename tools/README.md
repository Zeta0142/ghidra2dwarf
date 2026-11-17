# Development tools

This directory contains build and smoke-test helpers for the PyGhidra +
ctypes implementation:

```text
PyGhidra / CPython 3
        -> ctypes
        -> libdwarfp 2.3.x
        -> .debug_* sections
        -> ELF
```

It does not depend on Jython, JNA, or `libdwarf.jar`.

## Build the vendored libdwarf / libdwarfp

libdwarf 2.3.3 is vendored under `vendor/libdwarf/`. Build it with:

```bash
tools/build_libdwarf.sh
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

`src/libdwarfp.py` automatically looks in `build/libdwarf/`, so no environment
variables are needed after this. `LIBDWARFP_PATH` and `LIBDWARF_PATH` still
override the search when needed.

## Smoke-test the native binding

`smoke_producer.py` builds a tiny DWARF v4 compile unit with:

- one `DW_TAG_compile_unit`
- one `int` base type
- one `main` subprogram
- one stack variable
- a `.debug_line` line table for `sample.c`

It writes `.debug_abbrev`, `.debug_info`, and `.debug_line`, and optionally uses
`objcopy` to inject them into a copy of `test/binaries/test_ghidra`:

```bash
python3 tools/smoke_producer.py --out /tmp/ghidra2dwarf-smoke
```

Verify:

```bash
readelf --debug-dump=info,line /tmp/ghidra2dwarf-smoke/test_ghidra_dbg
```

If `objcopy` is unavailable:

```bash
python3 tools/smoke_producer.py --out /tmp/ghidra2dwarf-smoke --no-objcopy
```

## PyGhidra smoke test

The binding is verified inside **PyGhidra 3.1.0 + Ghidra 12.1.3**:

```text
python: 3.14.8
ctypes: /usr/lib64/python3.14/ctypes/__init__.py
currentProgram: test_ghidra - .ProgramDB
libdwarfp module: .../src/libdwarfp.py
sections: {'.debug_abbrev': 55, '.debug_info': 81, '.debug_line': 53}
RESULT: OK
```

Run it with a Python that has `pyghidra` installed:

```bash
GHIDRA_INSTALL_DIR=/path/to/ghidra \
PYGHIDRA_PYTHON=/path/to/venv/bin/python3 \
./tools/check_pyghidra.sh
```

The script is `tools/ghidra_scripts/check_pyghidra.py`.

### Ghidra MCP note

If you want to run the check through Ghidra MCP's `run_ghidra_script`, the MCP
bridge must be started with:

```bash
export GHIDRA_MCP_ALLOW_SCRIPTS=1
```

The MCP runner copies only the selected script into `~/ghidra_scripts`; this
project needs the full `src` directory, so MCP is not a substitute for adding
`src` to the Script Manager (or using the headless runner).

## Full integration smoke test

`src/ghidra2dwarf.py` is tested headlessly on the three existing fixtures:

```text
test_ghidra  x86-64  -> test_ghidra_dbg
passcode     x86-32  -> passcode_dbg
rsa          x86-64  -> rsa_dbg
```

Run:

```bash
GHIDRA_INSTALL_DIR=/path/to/ghidra \
PYGHIDRA_PYTHON=/path/to/venv/bin/python3 \
./tools/check_integration.sh test/binaries/test_ghidra
```

All three produce `.debug_info`, `.debug_line`, and `.debug_abbrev`; gdb can
resolve source lines for the recovered functions, for example:

```text
(gdb) list login
(gdb) list FUN_001011e2
(gdb) list RSA_private_encrypt
```

`src/elf.py` is used directly, so the integration does not need `objcopy`.

## Files

| Path | Purpose |
|---|---|
| `src/libdwarfp.py` | ctypes prototypes + `DwarfProducer` wrapper |
| `src/ghidra2dwarf.py` | PyGhidra script using ctypes/libdwarfp |
| `src/elf.py` | Python 3 ELF section injector |
| `tools/smoke_producer.py` | minimal DWARF producer and `objcopy` injection |
| `tools/build_libdwarf.sh` | builds the vendored libdwarf/libdwarfp |
| `tools/ghidra_scripts/check_pyghidra.py` | PyGhidra binding smoke test |
| `tools/check_pyghidra.sh` | headless PyGhidra binding runner |
| `tools/check_integration.sh` | full script integration runner |
| `vendor/libdwarf/` | vendored libdwarf 2.3.3 source (LGPL-2.1) |

## Important notes

- `libdwarfp` is a **separate library** from `libdwarf`.
  Loading `libdwarf.so` alone will not give you `dwarf_producer_init`.
- The binding targets the modern `_a`/`_c` producer API:
  - `dwarf_new_die_a`
  - `dwarf_add_AT_*_a`
  - `dwarf_add_line_entry_c`
  - `dwarf_transform_to_disk_form_a`
  - `dwarf_get_section_bytes_a`
- The callback object is kept alive on `DwarfProducer`; without that, Python
  may garbage-collect it and the native call can crash.
- `dwarf_get_section_bytes_a()` returns native memory owned by libdwarf.
  The binding copies it with `ctypes.string_at()` before `finish()`.
