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

## Build libdwarf / libdwarfp manually

The PoC needs a **modern libdwarf 2.3.x** built with the producer library.

As of libdwarf 2.3.3, CMake only adds `src/lib/libdwarfp` when `BUILD_DWARFGEN=ON`,
so use that option even if you do not need `dwarfgen` itself.

```bash
cd /tmp
curl -L -o libdwarf-2.3.3.tar.xz \
  https://github.com/davea42/libdwarf-code/releases/download/v2.3.3/libdwarf-2.3.3.tar.xz
tar xf libdwarf-2.3.3.tar.xz
mv libdwarf-2.3.3 libdwarf-src

cmake -S /tmp/libdwarf-src -B /tmp/libdwarf-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_DWARFDUMP=OFF \
  -DBUILD_DWARFGEN=ON \
  -DBUILD_DWARFEXAMPLE=OFF

cmake --build /tmp/libdwarf-build --target dwarfp-shared -j"$(nproc)"
```

Result:

```text
/tmp/libdwarf-build/src/lib/libdwarf/libdwarf.so.2.3.3
/tmp/libdwarf-build/src/lib/libdwarfp/libdwarfp.so.2.3.3
```

On macOS/Windows the names will be `libdwarf.dylib` / `libdwarfp.dylib` and
`libdwarf.dll` / `libdwarfp.dll`.

## Run the PoC

```bash
LIBDWARFP_PATH=/tmp/libdwarf-build/src/lib/libdwarfp/libdwarfp.so.2.3.3 \
LIBDWARF_PATH=/tmp/libdwarf-build/src/lib/libdwarf/libdwarf.so.2.3.3 \
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

## Files

| File | Purpose |
|---|---|
| `libdwarfp.py` | ctypes prototypes + `DwarfProducer` wrapper |
| `make_dwarf.py` | minimal DWARF producer and `objcopy` injection |
| `README.md` | this file |

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
