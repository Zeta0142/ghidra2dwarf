#!/usr/bin/env bash
# Run the ctypes/libdwarfp check inside PyGhidra (headless).
#
# Required:
#   GHIDRA_INSTALL_DIR  Ghidra installation directory
#   PYGHIDRA_PYTHON     Python interpreter with pyghidra installed
#
# Example:
#   GHIDRA_INSTALL_DIR=/home/z142/ghidra_12.1.3_PUBLIC \
#   PYGHIDRA_PYTHON=/home/z142/.config/ghidra/ghidra_12.1.3_PUBLIC/venv/bin/python3 \
#   ./tools/check_pyghidra.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR to the Ghidra installation}"
: "${PYGHIDRA_PYTHON:?set PYGHIDRA_PYTHON to a Python with pyghidra installed}"

BINARY="${1:-${ROOT}/test/binaries/test_ghidra}"
PROJECT_PATH="${PROJECT_PATH:-/tmp/g2d-pyghidra-project}"
PROJECT_NAME="${PROJECT_NAME:-g2d_check}"

"${PYGHIDRA_PYTHON}" -m pyghidra \
    --install-dir "${GHIDRA_INSTALL_DIR}" \
    --skip-analysis \
    --project-name "${PROJECT_NAME}" \
    --project-path "${PROJECT_PATH}" \
    "${BINARY}" \
    "${ROOT}/tools/ghidra_scripts/check_pyghidra.py"
