# Vendored dependencies

## libdwarf

- Version: **2.3.3**
- Source: https://github.com/davea42/libdwarf-code/releases/tag/v2.3.3
- Archive: `libdwarf-2.3.3.tar.xz`
- License: LGPL-2.1-or-later; see `vendor/libdwarf/COPYING`

The full release source tree is vendored so builds do not depend on a network
download or a system `libdwarf` package.

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
- The vendored source is unmodified.  Local build configuration lives in
  `tools/build_libdwarf.sh`.
