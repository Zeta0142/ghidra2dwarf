#!/bin/bash
# Headless PyGhidra launcher for ghidra2dwarf.
#
# Usage:
#   GHIDRA_INSTALL_DIR=/path/to/ghidra ./src/ghidra2dwarf.sh /path/to/binary
#
# The Python interpreter must have pyghidra installed.  Set PYGHIDRA_PYTHON
# when it is not the default python3.
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <binary> [script args...]" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GHIDRA_INSTALL_DIR="${GHIDRA_INSTALL_DIR:-/opt/ghidra}"
PYGHIDRA_PYTHON="${PYGHIDRA_PYTHON:-python3}"

"${PYGHIDRA_PYTHON}" -m pyghidra \
    --install-dir "${GHIDRA_INSTALL_DIR}" \
    "$1" \
    "${SCRIPT_DIR}/ghidra2dwarf.py" \
    "${@:2}"
