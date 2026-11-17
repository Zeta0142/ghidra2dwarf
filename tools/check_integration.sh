#!/usr/bin/env bash
# Run the actual PyGhidra script against one ELF and check the output.
#
# Required:
#   GHIDRA_INSTALL_DIR  Ghidra installation directory
#   PYGHIDRA_PYTHON     Python interpreter with pyghidra installed
#
# Optional:
#   SKIP_ANALYSIS=1     pass --skip-analysis to PyGhidra
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR to the Ghidra installation}"
: "${PYGHIDRA_PYTHON:?set PYGHIDRA_PYTHON to a Python with pyghidra installed}"

SRC="${1:-${ROOT}/test/binaries/test_ghidra}"
OUT="${OUT:-/tmp/ghidra2dwarf-integration}"
BINARY_NAME="$(basename "${SRC}")"
BINARY="${OUT}/${BINARY_NAME}"

rm -rf "${OUT}"
mkdir -p "${OUT}"
cp "${SRC}" "${BINARY}"

ARGS=(
    -m pyghidra
    --install-dir "${GHIDRA_INSTALL_DIR}"
    --project-name g2d_full_check
    --project-path "${OUT}/project"
)
if [ "${SKIP_ANALYSIS:-0}" = "1" ]; then
    ARGS+=(--skip-analysis)
fi

"${PYGHIDRA_PYTHON}" "${ARGS[@]}" \
    "${BINARY}" \
    "${ROOT}/src/ghidra2dwarf.py"

test -s "${BINARY}_dbg"
test -s "${BINARY}_dbg.c"

echo
echo "generated:"
ls -l "${BINARY}_dbg" "${BINARY}_dbg.c"
echo
echo "debug sections:"
readelf -S "${BINARY}_dbg" | grep '\.debug' || true
