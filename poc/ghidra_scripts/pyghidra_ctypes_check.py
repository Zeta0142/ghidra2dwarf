# @runtime PyGhidra
# @category ghidra2dwarf.PoC
"""Check that PyGhidra can load the ctypes libdwarfp binding."""

import os
import sys
import traceback

print("=== pyghidra ctypes/libdwarfp check ===")
print("python:", sys.version.replace("\n", " "))

try:
    import ctypes

    print("ctypes:", ctypes.__file__)
    print("currentProgram:", currentProgram)
    print("program name:", currentProgram.getName())
    print("executable:", currentProgram.getExecutablePath())

    repo = "/home/z142/Dev/ghidra2dwarf"
    poc = os.path.join(repo, "poc")
    if poc not in sys.path:
        sys.path.insert(0, poc)

    import libdwarfp
    from make_dwarf import build_sections

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
