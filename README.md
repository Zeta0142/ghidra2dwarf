# Ghidra2Dwarf

![](./img/ghidra2dwarf.png)

Inspired by: [dwarfexport](https://github.com/ALSchwalm/dwarfexport)

Ghidra2Dwarf exports information from Ghidra (functions, decompiled code,
types and variables) into DWARF sections inside ELF binaries.

More specifically it writes all decompiled functions to `${program}_dbg.c` and
creates `${program}_dbg`, an ELF binary that can be used for source-level
debugging.

Example:

![](./img/gdb.png)

Inside gdb you can now use:

1. `list <function>` to display the function's source code.
2. `n` to step one source code line.
3. `ni` to step one assembly instruction.
4. `p variable` to print the variable's value.

## Current branch: PyGhidra + libdwarfp

This branch is the migration from the original Jython/JNA implementation to:

- Ghidra 12.x with **PyGhidra**
- **ctypes** instead of JNA
- the modern **libdwarfp** producer API
- a vendored libdwarf 2.3.3 under `vendor/libdwarf`

The original JNA implementation is still visible in git history.

## Requirements

- Ghidra 12.x with PyGhidra
- Python 3.9+
- CMake, a C/C++ compiler and Ninja (or Make) for the vendored libdwarf
- Linux/macOS/Windows.  The current branch has been tested on Linux x86-64 and
  x86-32.

## Build the vendored libdwarf

```bash
./poc/build_libdwarf.sh
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
./poc/run_full_check.sh /path/to/binary
```

Or directly:

```bash
python3 -m pyghidra \
  --install-dir /path/to/ghidra \
  /path/to/binary \
  src/ghidra2dwarf.py
```

## Verification

The current branch was verified with:

- Ghidra 12.1.3
- PyGhidra 3.1.0
- Python 3.14
- libdwarf 2.3.3

Tested fixtures:

- `test/binaries/test_ghidra` (x86-64)
- `test/binaries/passcode` (x86-32)
- `test/binaries/rsa` (x86-64)

All produced `.debug_info`, `.debug_line` and `.debug_abbrev`; gdb can resolve
source lines for the recovered functions.

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
- MCP's `run_ghidra_script` copies only the script file; for GUI testing add the
  full `src` directory to the Script Manager instead.

## Legacy Jython version

The original Jython/JNA version is available in the `master` branch history.
It requires the Jython extension on Ghidra 12.x and is no longer the primary
implementation on this branch.
