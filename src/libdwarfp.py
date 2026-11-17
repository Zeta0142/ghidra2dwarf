"""Minimal ctypes binding for the libdwarf producer library (libdwarfp).

This is a proof-of-concept.  It intentionally implements only the producer
functions needed by ghidra2dwarf.  The goal is to show that CPython (and thus
PyGhidra) can drive the modern libdwarfp API without JNA or a Java wrapper.

The binding targets libdwarf 2.3.x.  The producer API in that release uses the
newer ``_a``/``_c`` function variants.
"""

from __future__ import annotations

import ctypes as C
import ctypes.util
import os
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# C types
# ---------------------------------------------------------------------------

U64 = C.c_ulonglong
S64 = C.c_longlong
U16 = C.c_ushort
U8 = C.c_ubyte
Bool = C.c_int

Dwarf_Ptr = C.c_void_p
Dwarf_P_Debug = C.c_void_p
Dwarf_P_Die = C.c_void_p
Dwarf_P_Expr = C.c_void_p
Dwarf_P_Attribute = C.c_void_p
Dwarf_Error = C.c_void_p

# Dwarf_Callback_Func from libdwarfp.h:
#   const char *name, int size, Dwarf_Unsigned type, flags, link, info,
#   Dwarf_Unsigned *sect_name_index, void *user_data, int *error
Dwarf_Callback_Func = C.CFUNCTYPE(
    C.c_int,
    C.c_char_p,
    C.c_int,
    U64,
    U64,
    U64,
    U64,
    C.POINTER(U64),
    C.c_void_p,
    C.POINTER(C.c_int),
)

# ---------------------------------------------------------------------------
# Constants used by the PoC
# ---------------------------------------------------------------------------

DW_DLV_OK = 0
DW_DLV_ERROR = 1
DW_DLV_NO_ENTRY = -1

DW_DLC_POINTER32 = 0x20000000
DW_DLC_POINTER64 = 0x40000000
DW_DLC_OFFSET32 = 0x00010000
DW_DLC_SYMBOLIC_RELOCATIONS = 0x04000000
DW_DLC_TARGET_LITTLEENDIAN = 0x00100000
DW_DLC_TARGET_BIGENDIAN = 0x08000000

DW_FORM_string = 0x08

DW_TAG_array_type = 0x01
DW_TAG_enumeration_type = 0x04
DW_TAG_formal_parameter = 0x05
DW_TAG_member = 0x0D
DW_TAG_pointer_type = 0x0F
DW_TAG_compile_unit = 0x11
DW_TAG_structure_type = 0x13
DW_TAG_subrange_type = 0x21
DW_TAG_base_type = 0x24
DW_TAG_enumerator = 0x28
DW_TAG_subprogram = 0x2E
DW_TAG_variable = 0x34

DW_AT_location = 0x02
DW_AT_name = 0x03
DW_AT_byte_size = 0x0B
DW_AT_low_pc = 0x11
DW_AT_high_pc = 0x12
DW_AT_comp_dir = 0x1B
DW_AT_const_value = 0x1C
DW_AT_count = 0x37
DW_AT_data_member_location = 0x38
DW_AT_decl_file = 0x3A
DW_AT_decl_line = 0x3B
DW_AT_encoding = 0x3E
DW_AT_frame_base = 0x40
DW_AT_type = 0x49
DW_AT_linkage_name = 0x6E

DW_ATE_address = 0x01
DW_ATE_boolean = 0x02
DW_ATE_complex_float = 0x03
DW_ATE_float = 0x04
DW_ATE_signed = 0x05
DW_ATE_signed_char = 0x06
DW_ATE_unsigned = 0x07
DW_ATE_unsigned_char = 0x08

DW_OP_plus_uconst = 0x23
DW_OP_regx = 0x90
DW_OP_fbreg = 0x91
DW_OP_call_frame_cfa = 0x9C

# Large enough for the register mappings used by the target architectures.
# Mirrors DW_FRAME_LAST_REG_NUM from libdwarf.
DW_FRAME_LAST_REG_NUM = 189


class DwarfError(RuntimeError):
    """Raised when a libdwarfp call fails."""


# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDORED_BUILD_ROOTS = (
    _REPO_ROOT / "build" / "libdwarf",
    _REPO_ROOT / "vendor" / "libdwarf" / "build",
)


def _vendored_library(name: str) -> Optional[str]:
    """Find a library produced by poc/build_libdwarf.sh."""

    patterns = [
        f"lib{name}.so*",
        f"{name}.so*",
        f"lib{name}.dylib",
        f"{name}.dylib",
        f"lib{name}.dll",
        f"{name}.dll",
    ]
    for root in _VENDORED_BUILD_ROOTS:
        if not root.is_dir():
            continue
        for pattern in patterns:
            for candidate in sorted(root.rglob(pattern)):
                if candidate.is_file():
                    return str(candidate)
    return None


def _resolve_library(name: str, env_var: str) -> Optional[str]:
    """Env override, then vendored build, then system lookup."""

    path = os.environ.get(env_var)
    if path:
        return path
    path = _vendored_library(name)
    if path:
        return path
    return ctypes.util.find_library(name)


def _load_library() -> C.CDLL:
    """Load libdwarfp and, when possible, its libdwarf dependency."""

    dwarf_path = _resolve_library("dwarf", "LIBDWARF_PATH")
    if dwarf_path:
        try:
            C.CDLL(dwarf_path, mode=getattr(C, "RTLD_GLOBAL", 0))
        except OSError:
            # libdwarfp's own RUNPATH may still find libdwarf.
            pass

    dwarfp_path = _resolve_library("dwarfp", "LIBDWARFP_PATH")
    if not dwarfp_path:
        raise DwarfError(
            "libdwarfp not found. Run poc/build_libdwarf.sh or set "
            "LIBDWARFP_PATH to libdwarfp.so/.dylib/.dll."
        )

    try:
        return C.CDLL(dwarfp_path, mode=getattr(C, "RTLD_GLOBAL", 0))
    except OSError as exc:
        raise DwarfError(f"failed to load {dwarfp_path!r}: {exc}") from exc


_LIB = _load_library()


def _load_errmsg():
    dwarf_path = _resolve_library("dwarf", "LIBDWARF_PATH")
    if not dwarf_path:
        return None
    try:
        lib = C.CDLL(dwarf_path, mode=getattr(C, "RTLD_GLOBAL", 0))
        lib.dwarf_errmsg.argtypes = [Dwarf_Error]
        lib.dwarf_errmsg.restype = C.c_char_p
        return lib.dwarf_errmsg
    except (OSError, TypeError, AttributeError):
        return None


_ERRMSG = _load_errmsg()


def _proto(name, restype, argtypes):
    fn = getattr(_LIB, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


# ---------------------------------------------------------------------------
# Function prototypes
# ---------------------------------------------------------------------------

dwarf_producer_init = _proto(
    "dwarf_producer_init",
    C.c_int,
    [
        U64,  # flags
        Dwarf_Callback_Func,
        C.c_void_p,  # errhand
        C.c_void_p,  # errarg
        C.c_void_p,  # user_data
        C.c_char_p,  # isa_name
        C.c_char_p,  # dwarf_version
        C.c_char_p,  # extra
        C.POINTER(Dwarf_P_Debug),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_pro_set_default_string_form = _proto(
    "dwarf_pro_set_default_string_form",
    C.c_int,
    [Dwarf_P_Debug, C.c_int, C.POINTER(Dwarf_Error)],
)

dwarf_new_die_a = _proto(
    "dwarf_new_die_a",
    C.c_int,
    [
        Dwarf_P_Debug,
        U64,  # tag
        Dwarf_P_Die,  # parent
        Dwarf_P_Die,  # child
        Dwarf_P_Die,  # left
        Dwarf_P_Die,  # right
        C.POINTER(Dwarf_P_Die),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_AT_name_a = _proto(
    "dwarf_add_AT_name_a",
    C.c_int,
    [Dwarf_P_Die, C.c_char_p, C.POINTER(Dwarf_P_Attribute), C.POINTER(Dwarf_Error)],
)

dwarf_add_AT_comp_dir_a = _proto(
    "dwarf_add_AT_comp_dir_a",
    C.c_int,
    [Dwarf_P_Die, C.c_char_p, C.POINTER(Dwarf_P_Attribute), C.POINTER(Dwarf_Error)],
)

dwarf_add_AT_string_a = _proto(
    "dwarf_add_AT_string_a",
    C.c_int,
    [
        Dwarf_P_Debug,
        Dwarf_P_Die,
        U16,
        C.c_char_p,
        C.POINTER(Dwarf_P_Attribute),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_AT_unsigned_const_a = _proto(
    "dwarf_add_AT_unsigned_const_a",
    C.c_int,
    [
        Dwarf_P_Debug,
        Dwarf_P_Die,
        U16,
        U64,
        C.POINTER(Dwarf_P_Attribute),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_AT_reference_c = _proto(
    "dwarf_add_AT_reference_c",
    C.c_int,
    [
        Dwarf_P_Debug,
        Dwarf_P_Die,
        U16,
        Dwarf_P_Die,
        C.POINTER(Dwarf_P_Attribute),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_AT_targ_address_c = _proto(
    "dwarf_add_AT_targ_address_c",
    C.c_int,
    [
        Dwarf_P_Debug,
        Dwarf_P_Die,
        U16,
        U64,  # pc_value
        U64,  # sym_index
        C.POINTER(Dwarf_P_Attribute),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_AT_location_expr_a = _proto(
    "dwarf_add_AT_location_expr_a",
    C.c_int,
    [
        Dwarf_P_Debug,
        Dwarf_P_Die,
        U16,
        Dwarf_P_Expr,
        C.POINTER(Dwarf_P_Attribute),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_die_to_debug_a = _proto(
    "dwarf_add_die_to_debug_a",
    C.c_int,
    [Dwarf_P_Debug, Dwarf_P_Die, C.POINTER(Dwarf_Error)],
)

dwarf_add_directory_decl_a = _proto(
    "dwarf_add_directory_decl_a",
    C.c_int,
    [Dwarf_P_Debug, C.c_char_p, C.POINTER(U64), C.POINTER(Dwarf_Error)],
)

dwarf_add_file_decl_a = _proto(
    "dwarf_add_file_decl_a",
    C.c_int,
    [
        Dwarf_P_Debug,
        C.c_char_p,
        U64,
        U64,
        U64,
        C.POINTER(U64),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_line_entry_c = _proto(
    "dwarf_add_line_entry_c",
    C.c_int,
    [
        Dwarf_P_Debug,
        U64,  # file_index
        U64,  # code_address
        U64,  # lineno
        S64,  # column_number
        Bool,  # is_source_stmt_begin
        Bool,  # is_basic_block_begin
        Bool,  # is_epilogue_begin
        Bool,  # is_prologue_end
        U64,  # isa
        U64,  # discriminator
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_lne_end_sequence_a = _proto(
    "dwarf_lne_end_sequence_a",
    C.c_int,
    [Dwarf_P_Debug, U64, C.POINTER(Dwarf_Error)],
)

dwarf_new_expr_a = _proto(
    "dwarf_new_expr_a",
    C.c_int,
    [Dwarf_P_Debug, C.POINTER(Dwarf_P_Expr), C.POINTER(Dwarf_Error)],
)

dwarf_add_expr_gen_a = _proto(
    "dwarf_add_expr_gen_a",
    C.c_int,
    [
        Dwarf_P_Expr,
        U8,  # opcode
        U64,  # val1
        U64,  # val2
        C.POINTER(U64),
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_add_expr_addr_c = _proto(
    "dwarf_add_expr_addr_c",
    C.c_int,
    [Dwarf_P_Expr, U64, U64, C.POINTER(U64), C.POINTER(Dwarf_Error)],
)

dwarf_transform_to_disk_form_a = _proto(
    "dwarf_transform_to_disk_form_a",
    C.c_int,
    [Dwarf_P_Debug, C.POINTER(U64), C.POINTER(Dwarf_Error)],
)

dwarf_get_section_bytes_a = _proto(
    "dwarf_get_section_bytes_a",
    C.c_int,
    [
        Dwarf_P_Debug,
        U64,  # dwarf_section
        C.POINTER(U64),  # elf_section_index
        C.POINTER(U64),  # length
        C.POINTER(C.c_void_p),  # section_bytes
        C.POINTER(Dwarf_Error),
    ],
)

dwarf_producer_finish_a = _proto(
    "dwarf_producer_finish_a",
    C.c_int,
    [Dwarf_P_Debug, C.POINTER(Dwarf_Error)],
)


# ---------------------------------------------------------------------------
# Thin object-oriented wrapper
# ---------------------------------------------------------------------------


class DwarfProducer:
    """Small wrapper around the libdwarfp producer API."""

    def __init__(
        self,
        *,
        isa_name: str = "x86_64",
        dwarf_version: str = "V4",
        pointer64: bool = True,
        little_endian: bool = True,
    ):
        self._section_names: list[str] = []
        self._callback = Dwarf_Callback_Func(self._on_section)
        self._dbg = Dwarf_P_Debug()
        self._closed = False

        flags = DW_DLC_OFFSET32 | DW_DLC_SYMBOLIC_RELOCATIONS
        flags |= DW_DLC_POINTER64 if pointer64 else DW_DLC_POINTER32
        flags |= (
            DW_DLC_TARGET_LITTLEENDIAN if little_endian else DW_DLC_TARGET_BIGENDIAN
        )

        err = Dwarf_Error()
        rc = dwarf_producer_init(
            flags,
            self._callback,
            None,
            None,
            None,
            isa_name.encode(),
            dwarf_version.encode(),
            None,
            C.byref(self._dbg),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_producer_init")

    def _on_section(
        self,
        name,
        size,
        section_type,
        flags,
        link,
        info,
        name_index,
        user_data,
        error,
    ):
        try:
            self._section_names.append(
                name.decode("utf-8", "replace") if name else ""
            )
            if name_index:
                name_index[0] = 0
            return len(self._section_names) - 1
        except Exception:
            if error:
                error[0] = 1
            return -1

    def _check(self, rc: int, err: Dwarf_Error, operation: str) -> None:
        if rc == DW_DLV_OK:
            return

        message = None
        if err and _ERRMSG:
            raw = _ERRMSG(err)
            if raw:
                message = raw.decode("utf-8", "replace")
        if not message:
            message = "no libdwarf error message"
        raise DwarfError(f"{operation} failed: {message} (rc={rc})")

    def set_default_string_form(self, form: int = DW_FORM_string) -> None:
        err = Dwarf_Error()
        rc = dwarf_pro_set_default_string_form(self._dbg, form, C.byref(err))
        self._check(rc, err, "dwarf_pro_set_default_string_form")

    def new_die(self, tag: int, parent=None, child=None, left=None, right=None):
        die = Dwarf_P_Die()
        err = Dwarf_Error()
        rc = dwarf_new_die_a(
            self._dbg,
            tag,
            parent,
            child,
            left,
            right,
            C.byref(die),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_new_die_a")
        return die

    def add_name(self, die, name: str):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_name_a(
            die, name.encode(), C.byref(attr), C.byref(err)
        )
        self._check(rc, err, "dwarf_add_AT_name_a")
        return attr

    def add_comp_dir(self, die, directory: str):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_comp_dir_a(
            die, directory.encode(), C.byref(attr), C.byref(err)
        )
        self._check(rc, err, "dwarf_add_AT_comp_dir_a")
        return attr

    def add_string(self, die, attribute: int, value: str):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_string_a(
            self._dbg,
            die,
            attribute,
            value.encode(),
            C.byref(attr),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_AT_string_a")
        return attr

    def add_unsigned_const(self, die, attribute: int, value: int):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_unsigned_const_a(
            self._dbg,
            die,
            attribute,
            value,
            C.byref(attr),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_AT_unsigned_const_a")
        return attr

    def add_reference(self, die, attribute: int, target_die):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_reference_c(
            self._dbg,
            die,
            attribute,
            target_die,
            C.byref(attr),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_AT_reference_c")
        return attr

    def add_targ_address(self, die, attribute: int, address: int, symbol_index: int = 0):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_targ_address_c(
            self._dbg,
            die,
            attribute,
            address,
            symbol_index,
            C.byref(attr),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_AT_targ_address_c")
        return attr

    def add_location_expr(self, die, attribute: int, expr):
        attr = Dwarf_P_Attribute()
        err = Dwarf_Error()
        rc = dwarf_add_AT_location_expr_a(
            self._dbg,
            die,
            attribute,
            expr,
            C.byref(attr),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_AT_location_expr_a")
        return attr

    def add_die_to_debug(self, die):
        err = Dwarf_Error()
        rc = dwarf_add_die_to_debug_a(self._dbg, die, C.byref(err))
        self._check(rc, err, "dwarf_add_die_to_debug_a")

    def add_directory_decl(self, directory: str) -> int:
        index = U64()
        err = Dwarf_Error()
        rc = dwarf_add_directory_decl_a(
            self._dbg, directory.encode(), C.byref(index), C.byref(err)
        )
        self._check(rc, err, "dwarf_add_directory_decl_a")
        return index.value

    def add_file_decl(
        self,
        filename: str,
        directory_index: int,
        mtime: int = 0,
        length: int = 0,
    ) -> int:
        file_count = U64()
        err = Dwarf_Error()
        rc = dwarf_add_file_decl_a(
            self._dbg,
            filename.encode(),
            directory_index,
            mtime,
            length,
            C.byref(file_count),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_file_decl_a")
        return file_count.value

    def add_line_entry(
        self,
        file_index: int,
        address: int,
        line: int,
        column: int = 0,
        is_stmt: bool = True,
        basic_block: bool = False,
        isa: int = 0,
        discriminator: int = 0,
    ) -> None:
        err = Dwarf_Error()
        rc = dwarf_add_line_entry_c(
            self._dbg,
            file_index,
            address,
            line,
            column,
            int(is_stmt),
            int(basic_block),
            0,
            0,
            isa,
            discriminator,
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_line_entry_c")

    def end_sequence(self, address: int) -> None:
        err = Dwarf_Error()
        rc = dwarf_lne_end_sequence_a(self._dbg, address, C.byref(err))
        self._check(rc, err, "dwarf_lne_end_sequence_a")

    def new_expr(self):
        expr = Dwarf_P_Expr()
        err = Dwarf_Error()
        rc = dwarf_new_expr_a(self._dbg, C.byref(expr), C.byref(err))
        self._check(rc, err, "dwarf_new_expr_a")
        return expr

    def add_expr_gen(self, expr, opcode: int, value1: int = 0, value2: int = 0) -> int:
        next_offset = U64()
        err = Dwarf_Error()
        rc = dwarf_add_expr_gen_a(
            expr,
            opcode,
            value1,
            value2,
            C.byref(next_offset),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_expr_gen_a")
        return next_offset.value

    def add_expr_addr(self, expr, address: int, symbol_index: int = 0) -> int:
        next_offset = U64()
        err = Dwarf_Error()
        rc = dwarf_add_expr_addr_c(
            expr,
            address,
            symbol_index,
            C.byref(next_offset),
            C.byref(err),
        )
        self._check(rc, err, "dwarf_add_expr_addr_c")
        return next_offset.value

    def transform(self) -> Dict[str, bytes]:
        count = U64()
        err = Dwarf_Error()
        rc = dwarf_transform_to_disk_form_a(self._dbg, C.byref(count), C.byref(err))
        self._check(rc, err, "dwarf_transform_to_disk_form_a")

        sections: Dict[str, bytearray] = {}
        for i in range(count.value):
            elf_index = U64()
            length = U64()
            buf = C.c_void_p()
            err = Dwarf_Error()
            rc = dwarf_get_section_bytes_a(
                self._dbg,
                i,
                C.byref(elf_index),
                C.byref(length),
                C.byref(buf),
                C.byref(err),
            )
            self._check(rc, err, "dwarf_get_section_bytes_a")

            name = self._section_names[elf_index.value]
            data = C.string_at(buf, length.value)
            sections.setdefault(name, bytearray()).extend(data)

        return {name: bytes(data) for name, data in sections.items()}

    def finish(self) -> None:
        if self._closed:
            return
        self._closed = True
        err = Dwarf_Error()
        rc = dwarf_producer_finish_a(self._dbg, C.byref(err))
        self._dbg = Dwarf_P_Debug()
        self._check(rc, err, "dwarf_producer_finish_a")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finish()
        return False
