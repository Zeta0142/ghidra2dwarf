# @runtime PyGhidra
# @category ghidra2dwarf.Tools
"""Check that PyGhidra can load the ctypes libdwarfp binding."""

import os
import sys
import traceback
from pathlib import Path

print("=== pyghidra ctypes/libdwarfp check ===")
print("python:", sys.version.replace("\n", " "))

try:
    import ctypes

    print("ctypes:", ctypes.__file__)
    print("currentProgram:", currentProgram)
    print("program name:", currentProgram.getName())
    print("executable:", currentProgram.getExecutablePath())

    repo = str(Path(__file__).resolve().parents[2])
    for path in (os.path.join(repo, "src"), os.path.join(repo, "tools")):
        if path not in sys.path:
            sys.path.insert(0, path)

    import libdwarfp
    from smoke_producer import build_sections

    print("libdwarfp module:", libdwarfp.__file__)

    sections = build_sections()
    print("sections:", {name: len(data) for name, data in sorted(sections.items())})
    assert ".debug_info" in sections
    assert ".debug_abbrev" in sections
    assert ".debug_line" in sections
    print("RESULT: OK")
except Exception:
    traceback.print_exc()
    print("RESULT: FAILED")
    raise
