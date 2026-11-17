# Vendored dependencies

## libdwarf

- Version: **2.3.3**
- Repository: https://github.com/davea42/libdwarf-code
- Tag: `v2.3.3`
- Commit: `1c267616a4c8dc46b3380f0be4296ff8767bdfbb`
- License: LGPL-2.1-or-later; see `vendor/libdwarf/COPYING`

libdwarf is tracked as a git submodule, not as a copy of the source tree.

Initialize it after cloning:

```bash
git submodule update --init --recursive
```

Build only the producer library:

```bash
tools/build_libdwarf.sh
```

Outputs go to `build/libdwarf/` (ignored by git):

```text
build/libdwarf/src/lib/libdwarf/libdwarf.so.2.3.3
build/libdwarf/src/lib/libdwarfp/libdwarfp.so.2.3.3
```

Notes:

- `libdwarfp` is the producer library; `libdwarf` is the consumer library.
- libdwarf 2.3.3's CMake build only adds `src/lib/libdwarfp` when
  `BUILD_DWARFGEN=ON`; the build script sets that option.
- The producer API uses the `_a`/`_c` variants.
- Local build configuration lives in `tools/build_libdwarf.sh`.
