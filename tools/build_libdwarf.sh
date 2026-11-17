#!/usr/bin/env bash
# Build the vendored libdwarf 2.3.x and its producer library, libdwarfp.
#
# The vendored source is pinned under vendor/libdwarf/.  Build artifacts go to
# build/libdwarf/ (ignored by git) unless a custom directory is passed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/vendor/libdwarf"
BUILD="${1:-${ROOT}/build/libdwarf}"

if [ ! -f "${SRC}/CMakeLists.txt" ]; then
    echo "error: libdwarf submodule not found at ${SRC}" >&2
    echo "run: git submodule update --init --recursive" >&2
    exit 1
fi

CMAKE_ARGS=(
    -S "${SRC}"
    -B "${BUILD}"
    -DCMAKE_BUILD_TYPE=Release
    -DBUILD_DWARFDUMP=OFF
    -DBUILD_DWARFEXAMPLE=OFF
    # libdwarf 2.3.3 only adds the libdwarfp subdirectory when dwarfgen is
    # enabled.  We do not need the dwarfgen executable, only the library.
    -DBUILD_DWARFGEN=ON
)

if command -v ninja >/dev/null 2>&1; then
    cmake "${CMAKE_ARGS[@]}" -G Ninja
else
    cmake "${CMAKE_ARGS[@]}"
fi

cmake --build "${BUILD}" --target dwarfp-shared -j"$(nproc 2>/dev/null || echo 2)"

echo
echo "built:"
find "${BUILD}/src/lib" -maxdepth 2 \( \
    -name 'libdwarfp.so*' -o -name 'libdwarfp.dylib' -o -name 'libdwarfp.dll' -o \
    -name 'libdwarf.so*' -o -name 'libdwarf.dylib' -o -name 'libdwarf.dll' \
    \) -print | sort

echo
echo "run the smoke test with:"
echo "  python3 ${ROOT}/tools/smoke_producer.py --out /tmp/ghidra2dwarf-smoke"
