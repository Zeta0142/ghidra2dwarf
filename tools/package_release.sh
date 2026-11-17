#!/usr/bin/env bash
# Assemble a script-directory release zip.
#
# Usage:
#   tools/package_release.sh [platform-dir]
#
# platform-dir defaults to the current host (e.g. linux-x86-64).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${ROOT}/build/libdwarf"
PLATFORM_DIR="${1:-}"

if [ -z "${PLATFORM_DIR}" ]; then
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64) PLATFORM_DIR=linux-x86-64 ;;
        Linux-aarch64|Linux-arm64) PLATFORM_DIR=linux-aarch64 ;;
        Darwin-x86_64) PLATFORM_DIR=darwin-x86-64 ;;
        Darwin-arm64) PLATFORM_DIR=darwin-aarch64 ;;
        MINGW*|MSYS*|CYGWIN*) PLATFORM_DIR=win32-x86-64 ;;
        *) PLATFORM_DIR="$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)" ;;
    esac
fi

if [ ! -d "${BUILD}/src/lib/libdwarfp" ]; then
    "${ROOT}/tools/build_libdwarf.sh"
fi

STAGE="${ROOT}/build/release/ghidra2dwarf"
rm -rf "${ROOT}/build/release"
mkdir -p "${STAGE}/lib/${PLATFORM_DIR}"

cp "${ROOT}/src/ghidra2dwarf.py" \
   "${ROOT}/src/ghidra2dwarf.sh" \
   "${ROOT}/src/libdwarfp.py" \
   "${ROOT}/src/elf.py" \
   "${STAGE}/"
cp "${ROOT}/README.md" "${ROOT}/LICENSE" "${STAGE}/"

copy_libs() {
    local source_dir="$1"
    find "${source_dir}" -maxdepth 1 \
        \( -name 'libdwarf.so*' -o -name 'libdwarf.dylib' -o -name 'libdwarf.dll' \
           -o -name 'libdwarfp.so*' -o -name 'libdwarfp.dylib' -o -name 'libdwarfp.dll' \) \
        -exec cp -a {} "${STAGE}/lib/${PLATFORM_DIR}/" \;
}

copy_libs "${BUILD}/src/lib/libdwarf"
copy_libs "${BUILD}/src/lib/libdwarfp"

ZIP="${ROOT}/build/ghidra2dwarf.zip"
rm -f "${ZIP}"
(
    cd "${ROOT}/build/release"
    zip -q -r "${ZIP}" ghidra2dwarf
)

echo "packaged: ${ZIP}"
echo "platform: ${PLATFORM_DIR}"
