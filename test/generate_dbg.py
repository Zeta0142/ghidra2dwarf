#!/usr/bin/env python3
"""Generate _dbg files for the integration tests using headless PyGhidra."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "test"
BINS_DIR = TEST_DIR / "binaries"
BINARIES = ("test_ghidra", "passcode", "rsa")


def main() -> int:
    ghidra_dir = os.environ.get("GHIDRA_INSTALL_DIR")
    if not ghidra_dir:
        print("GHIDRA_INSTALL_DIR is required", file=sys.stderr)
        return 1

    pyghidra_python = os.environ.get("PYGHIDRA_PYTHON", sys.executable)
    skip_analysis = os.environ.get("G2D_SKIP_ANALYSIS") == "1"

    with tempfile.TemporaryDirectory(prefix="ghidra2dwarf_test_") as temp:
        temp_path = Path(temp)
        project_path = temp_path / "project"
        project_path.mkdir()

        for name in BINARIES:
            source = BINS_DIR / name
            if not source.is_file():
                print(f"missing test binary: {source}", file=sys.stderr)
                return 1

            work_binary = temp_path / name
            shutil.copy2(source, work_binary)

            cmd = [
                pyghidra_python,
                "-m",
                "pyghidra",
                "--install-dir",
                ghidra_dir,
                "--project-name",
                f"g2d_{name}",
                "--project-path",
                str(project_path),
            ]
            if skip_analysis:
                cmd.append("--skip-analysis")
            cmd.extend([str(work_binary), str(ROOT / "src" / "ghidra2dwarf.py")])

            print(" ".join(cmd))
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if result.returncode != 0 or "Traceback" in result.stdout:
                print(result.stdout, file=sys.stderr)
                return 1

            for suffix in ("_dbg", "_dbg.c"):
                generated = temp_path / (name + suffix)
                if not generated.is_file():
                    print(f"missing generated file: {generated}", file=sys.stderr)
                    return 1
                shutil.copy2(generated, BINS_DIR / (name + suffix))

            print(result.stdout[-2000:])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
