# Ghidra2Dwarf

![](./img/ghidra2dwarf.png)

Inspired by: [dwarfexport](https://github.com/ALSchwalm/dwarfexport)

Ghidra2Dwarf exports information from Ghidra (functions, decompiled code,
types and variables) into DWARF sections inside ELF binaries.

More specifically it writes all decompiled functions to `${program}_dbg.c` and
creates `${program}_dbg`, an ELF binary that can be used for source-level
debugging.

This repository is a fork of
[cesena/ghidra2dwarf](https://github.com/cesena/ghidra2dwarf). The original
project targets older Ghidra releases with Jython/JNA; this fork modernizes it
for Ghidra 12.x using PyGhidra, ctypes, and a vendored libdwarf 2.3.3.

## Implementation

The exporter uses:

- Ghidra 12.x with **PyGhidra**
- **ctypes** to call the native producer API
- the modern **libdwarfp** producer API
- a vendored libdwarf 2.3.3 under `vendor/libdwarf`

## Requirements

For a packaged release, the native libraries are already under
`lib/<platform>/`, so no build step is needed.  For a source checkout, build
them with `tools/build_libdwarf.sh` as described below.

- Ghidra 12.x with PyGhidra
- Python 3.9+
- CMake, a C/C++ compiler and Ninja (or Make) for the vendored libdwarf
- Linux is currently the only tested platform (x86-64 and x86-32).
  Windows and macOS have not been tested yet.

## Build the vendored libdwarf (source checkout only)

```bash
./tools/build_libdwarf.sh
```

This builds:

```text
build/libdwarf/src/lib/libdwarf/libdwarf.so*
build/libdwarf/src/lib/libdwarfp/libdwarfp.so*
```

`src/libdwarfp.py` looks in `build/libdwarf/` automatically, so no environment
variables are required after the build.

## Run with PyGhidra

Start Ghidra using the PyGhidra launcher:

```bash
<GhidraInstallDir>/support/pyghidraRun
```

Then add the `src` directory to the Script Manager script directories and run
`ghidra2dwarf.py`.

The generated `_dbg` and `_dbg.c` files are written next to the original binary.

## Headless mode

Use the PyGhidra command-line runner:

```bash
GHIDRA_INSTALL_DIR=/path/to/ghidra \
PYGHIDRA_PYTHON=/path/to/python-with-pyghidra \
./tools/check_integration.sh /path/to/binary
```

Or directly:

```bash
python3 -m pyghidra \
  --install-dir /path/to/ghidra \
  /path/to/binary \
  src/ghidra2dwarf.py
```

## Verification

The implementation has been exercised with Ghidra 12.x + PyGhidra and
libdwarf 2.3.3.

Tested fixtures:

- `test/binaries/test_ghidra` (x86-64)
- `test/binaries/passcode` (x86-32)
- `test/binaries/rsa` (x86-64)

All produced `.debug_info`, `.debug_line` and `.debug_abbrev`, including
source line information for the recovered functions.

## How it works

```text
Ghidra Program
  -> traverse functions/types/variables
  -> decompile and build C source + address/line mapping
  -> emit DWARF DIEs and line table through libdwarfp (ctypes)
  -> append .debug_* sections to the original ELF (src/elf.py)
  -> ${program}_dbg + ${program}_dbg.c
```

## Known limitations

- Only ELF is supported.
- Tested mainly on x86/x86-64; ARM/AArch64 need more register and line-table
  validation.
- Stack variable locations use the same approximation as the original project.
- Synthetic/hash variables are skipped.
- The ELF writer is append-only and assumes a normal section-header table.

## AI disclaimer

Parts of this fork, including code changes, tests, documentation, and commit
messages, were produced with AI assistance using:

- **Tool:** OpenCode
- **Model:** DeepSeek V4.1 Flash 1017
