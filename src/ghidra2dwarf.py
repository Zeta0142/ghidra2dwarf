# Ghidra2Dwarf
# @author sen, meowmeowxw
# @category PWN
# @runtime PyGhidra
# @keybinding
# @menupath
# @toolbar

import os

from ghidra.app.decompiler import DecompInterface, DecompileOptions
from ghidra.app.decompiler.component import DecompilerUtils
from ghidra.app.util.bin.format.dwarf import DWARFRegisterMappingsManager
from ghidra.app.util.opinion import ElfLoader
from ghidra.framework import OperatingSystem
from ghidra.program.model.data import (
    AbstractComplexDataType,
    AbstractFloatDataType,
    AbstractIntegerDataType,
    Array,
    BooleanDataType,
    BuiltInDataType,
    CharDataType,
    DefaultDataType,
    Enum,
    Pointer,
    Structure,
)
from ghidra.program.model.symbol import SymbolType

import libdwarfp as dw
from elf import add_sections_to_elf
from libdwarfp import DwarfProducer


curr = currentProgram
if curr is None:
    raise RuntimeError("No current program")

if curr.getExecutableFormat() != ElfLoader.ELF_NAME:
    print("Only ELF binaries are supported")
    raise SystemExit(1)

image_base = curr.getImageBase().getOffset()
orig_base = ElfLoader.getElfOriginalImageBase(curr)
orig_base = int(orig_base) if orig_base is not None else 0


def get_real_address(addr):
    """Convert a Ghidra address to the address in the original ELF."""
    return addr.getOffset() - image_base + orig_base


record = {}
decomp_lines = []
register_mappings = {}
decompiler = None


def iter_java(iterator):
    """Iterate a Java Iterator from Python."""
    while iterator.hasNext():
        yield iterator.next()


def get_output_paths():
    exe_path = curr.getExecutablePath()

    # Ghidra on Windows may prepend a slash to the path.
    if (
        OperatingSystem.CURRENT_OPERATING_SYSTEM == OperatingSystem.WINDOWS
        and exe_path
        and exe_path.startswith("/")
    ):
        exe_path = exe_path[1:]

    while not exe_path or not os.path.isfile(exe_path):
        print(
            "I couldn't find the original file at path %s. "
            "Please specify its path:" % exe_path
        )
        chosen = askFile("Original binary path", "Open")
        exe_path = chosen.getAbsolutePath()
        curr.setExecutablePath(exe_path)
        print("Changed binary path to %s." % exe_path)

    return exe_path, exe_path + "_dbg", exe_path + "_dbg.c"


def add_debug_info(producer):
    producer.set_default_string_form()

    cu = producer.new_die(dw.DW_TAG_compile_unit)

    c_file_name = os.path.basename(decompiled_c_path)
    producer.add_name(cu, c_file_name)
    dir_index = producer.add_directory_decl(".")
    file_index = producer.add_file_decl(c_file_name, dir_index, 0, 0)
    producer.add_comp_dir(cu, ".")

    funcs = list(get_functions())
    addr_to_line = {}
    max_addr = 0

    for i, func in enumerate(funcs):
        print("Decompiling function %d: %s" % (i, func.getName()))
        _die, func_addrs = add_function(producer, cu, func, file_index)
        addr_to_line.update(func_addrs)
        max_addr = max(max_addr, get_function_range(func)[1] + 1)

    for addr in sorted(addr_to_line):
        producer.add_line_entry(file_index, addr, addr_to_line[addr])
        max_addr = max(max_addr, addr + 1)

    producer.end_sequence(max_addr)

    producer.add_die_to_debug(cu)
    add_global_variables(producer, cu)
    add_structures(producer, cu)


def get_isa_name(pointer64):
    processor = str(curr.getLanguage().getProcessor()).lower()
    if "aarch64" in processor or "arm64" in processor:
        return "arm64"
    if "arm" in processor:
        return "arm"
    if "x86" in processor or "i386" in processor:
        return "x86_64" if pointer64 else "x86"
    if "mips" in processor:
        return "mips"
    if "ppc" in processor or "powerpc" in processor:
        return "ppc64" if pointer64 else "ppc"
    if "sparc" in processor:
        return "sparc"
    return "x86_64" if pointer64 else "x86"


def generate_register_mappings():
    d2g_mapping = DWARFRegisterMappingsManager.getMappingForLang(curr.getLanguage())
    g2d_mapping = {}

    for i in range(dw.DW_FRAME_LAST_REG_NUM):
        reg = d2g_mapping.getGhidraReg(i)
        if reg:
            g2d_mapping[reg.getOffset()] = i

    return g2d_mapping


def generate_decomp_interface():
    decompiler = DecompInterface()
    opts = DecompileOptions()
    opts.grabFromProgram(curr)
    decompiler.setOptions(opts)
    decompiler.toggleCCode(True)
    decompiler.toggleSyntaxTree(True)

    # decompile, normalize, jumptable, paramid, register, firstpass
    decompiler.setSimplificationStyle("decompile")
    decompiler.openProgram(curr)
    return decompiler


def get_decompiled_function(func):
    return decompiler.decompileFunction(func, 0, monitor)


def get_decompiled_variables(decomp):
    hf = decomp.getHighFunction()
    symbol_map = hf.getLocalSymbolMap()

    params = []
    for i in range(symbol_map.getNumParams()):
        param = symbol_map.getParam(i)
        if param:
            params.append(param.getSymbol())

    for symbol in iter_java(symbol_map.getSymbols()):
        yield (
            symbol.getName(),
            symbol.getDataType(),
            symbol.getPCAddress(),
            symbol.getStorage(),
            symbol in params,
        )


def add_decompiler_func_info(
    producer, cu, func_die, func, decomp, file_index, func_line
):
    for name, datatype, addr, storage, is_param in get_decompiled_variables(decomp):
        add_variable(
            producer,
            cu,
            func_die,
            name,
            datatype,
            addr,
            storage,
            is_parameter=is_param,
        )

    cmarkup = decomp.getCCodeMarkup()
    lines = DecompilerUtils.toLines(cmarkup)
    addr_to_line = {}

    for line in lines:
        for token in line.getAllTokens():
            min_address = token.getMinAddress()
            if min_address:
                addr_to_line[get_real_address(min_address)] = (
                    line.getLineNumber() + func_line - 1
                )

    return addr_to_line


def get_functions():
    return iter_java(curr.getFunctionManager().getFunctions(True))


def get_function_range(func):
    return (
        get_real_address(func.getEntryPoint()),
        get_real_address(func.getBody().getMaxAddress()),
    )


def add_global_variables(producer, cu):
    for symbol in iter_java(curr.getSymbolTable().getAllSymbols(True)):
        if symbol.getSymbolType() not in (
            SymbolType.LABEL,
            SymbolType.GLOBAL,
            SymbolType.GLOBAL_VAR,
        ):
            continue

        data = curr.getListing().getDataAt(symbol.getAddress())
        if not data:
            continue

        die = producer.new_die(dw.DW_TAG_variable, parent=cu)
        var_type_die = add_type(producer, cu, data.getDataType())

        producer.add_name(die, symbol.getName())
        producer.add_reference(die, dw.DW_AT_type, var_type_die)

        expr = producer.new_expr()
        producer.add_expr_addr(expr, get_real_address(data.getAddress()))
        producer.add_location_expr(die, dw.DW_AT_location, expr)


def add_structures(producer, cu):
    for structure in iter_java(curr.getDataTypeManager().getAllStructures()):
        add_type(producer, cu, structure)


def add_variable(
    producer,
    cu,
    func_die,
    name,
    datatype,
    addr,
    storage,
    is_parameter=False,
):
    # There may be more than one varnode; use the first one as the original
    # implementation does.
    varnode = storage.getFirstVarnode()
    if varnode is None:
        return None

    varnode_addr = varnode.getAddress()

    tag = dw.DW_TAG_formal_parameter if is_parameter else dw.DW_TAG_variable
    var_die = producer.new_die(tag, parent=func_die)
    type_die = add_type(producer, cu, datatype)

    producer.add_reference(var_die, dw.DW_AT_type, type_die)
    producer.add_name(var_die, name)

    expr = producer.new_expr()
    has_location = False

    try:
        if varnode_addr.isRegisterAddress():
            reg = curr.getRegister(varnode_addr, varnode.getSize())
            if reg is None:
                raise RuntimeError("no Ghidra register for %s" % varnode_addr)

            reg_dwarf = register_mappings.get(reg.getOffset())
            if reg_dwarf is None:
                raise RuntimeError("no DWARF mapping for register %s" % reg)

            producer.add_expr_gen(expr, dw.DW_OP_regx, reg_dwarf)
            has_location = True

        elif varnode_addr.isStackAddress():
            producer.add_expr_gen(
                expr,
                dw.DW_OP_fbreg,
                varnode_addr.getOffset() - varnode_addr.getPointerSize(),
            )
            has_location = True

        elif varnode_addr.isMemoryAddress():
            print("warning: memory variable has no location: %s %s" % (name, varnode))
            return var_die

        elif varnode_addr.isHashAddress():
            # Ghidra synthetic variable; the original implementation skips it.
            return var_die

        else:
            print("warning: unsupported variable location: %s %s" % (name, varnode))
            return var_die

    except Exception as exc:
        print("warning: could not emit location for %s: %s" % (name, exc))
        return var_die

    if has_location:
        producer.add_location_expr(var_die, dw.DW_AT_location, expr)

    return var_die


def add_function(producer, cu, func, file_index):
    die = producer.new_die(dw.DW_TAG_subprogram, parent=cu)

    frame_base = producer.new_expr()
    producer.add_expr_gen(frame_base, dw.DW_OP_call_frame_cfa)
    producer.add_location_expr(die, dw.DW_AT_frame_base, frame_base)

    f_name = func.getName()
    producer.add_name(die, f_name)
    producer.add_string(die, dw.DW_AT_linkage_name, f_name)

    return_type = func.getReturnType()
    if return_type:
        ret_type_die = add_type(producer, cu, return_type)
        producer.add_reference(die, dw.DW_AT_type, ret_type_die)

    f_start, f_end = get_function_range(func)
    producer.add_targ_address(die, dw.DW_AT_low_pc, f_start)
    producer.add_targ_address(die, dw.DW_AT_high_pc, f_end + 1)

    func_line = len(decomp_lines) + 1
    res = get_decompiled_function(func)
    decompiled_function = res.getDecompiledFunction()

    if decompiled_function is None:
        error = res.getErrorMessage() or "unknown decompiler error"
        d = "/* Error decompiling %s: %s */" % (func.getName(), error)
    else:
        d = decompiled_function.getC()

    decomp_lines.extend(d.split("\n"))

    producer.add_unsigned_const(die, dw.DW_AT_decl_file, file_index)
    producer.add_unsigned_const(die, dw.DW_AT_decl_line, func_line + 1)

    addr_to_line = {f_start: func_line + 1}
    if decompiled_function is not None:
        addr_to_line.update(
            add_decompiler_func_info(
                producer, cu, die, func, res, file_index, func_line
            )
        )

    return die, addr_to_line


def write_source():
    with open(decompiled_c_path, "wb") as src:
        src.write("\n".join(decomp_lines).encode("utf8"))


def _type_key(datatype):
    name = datatype.getName()
    return name if name else "<anonymous:%s>" % id(datatype)


def add_type(producer, cu, datatype):
    if datatype is None:
        raise RuntimeError("cannot add a null datatype")

    key = _type_key(datatype)
    if key in record:
        return record[key]

    if isinstance(datatype, Pointer):
        return add_ptr_type(producer, cu, datatype, key)
    if isinstance(datatype, Enum):
        return add_enum_type(producer, cu, datatype, key)
    if isinstance(datatype, Array):
        return add_array_type(producer, cu, datatype, key)
    if isinstance(datatype, Structure):
        return add_struct_type(producer, cu, datatype, key)
    if isinstance(datatype, (BuiltInDataType, DefaultDataType)):
        return add_default_type(producer, cu, datatype, key)

    return add_default_type(producer, cu, datatype, key)


def add_default_type(producer, cu, datatype, key):
    die = producer.new_die(dw.DW_TAG_base_type, parent=cu)
    record[key] = die

    producer.add_name(die, datatype.getName() or "<anonymous>")
    producer.add_unsigned_const(die, dw.DW_AT_byte_size, datatype.getLength())

    if isinstance(datatype, BooleanDataType):
        encoding = dw.DW_ATE_boolean
    elif isinstance(datatype, CharDataType):
        is_signed = (
            datatype.getDataTypeManager()
            .getDataOrganization()
            .isSignedChar()
        )
        encoding = dw.DW_ATE_signed_char if is_signed else dw.DW_ATE_unsigned_char
    elif isinstance(datatype, AbstractIntegerDataType):
        encoding = dw.DW_ATE_signed if datatype.isSigned() else dw.DW_ATE_unsigned
    elif isinstance(datatype, AbstractFloatDataType):
        encoding = dw.DW_ATE_float
    elif isinstance(datatype, AbstractComplexDataType):
        encoding = dw.DW_ATE_complex_float
    else:
        encoding = dw.DW_ATE_unsigned

    producer.add_unsigned_const(die, dw.DW_AT_encoding, encoding)
    return die


def add_ptr_type(producer, cu, datatype, key):
    die = producer.new_die(dw.DW_TAG_pointer_type, parent=cu)
    record[key] = die

    child = datatype.getDataType()
    if child is not None:
        child_die = add_type(producer, cu, child)
        producer.add_reference(die, dw.DW_AT_type, child_die)

    producer.add_unsigned_const(die, dw.DW_AT_byte_size, datatype.getLength())
    producer.add_unsigned_const(die, dw.DW_AT_encoding, dw.DW_ATE_address)
    return die


def add_enum_type(producer, cu, datatype, key):
    die = producer.new_die(dw.DW_TAG_enumeration_type, parent=cu)
    record[key] = die

    producer.add_name(die, datatype.getName() or "<anonymous>")
    producer.add_unsigned_const(die, dw.DW_AT_byte_size, datatype.getLength())

    int_type = AbstractIntegerDataType.getUnsignedDataType(
        datatype.getLength(), curr.getDataTypeManager()
    )
    child_type_die = add_type(producer, cu, int_type)
    producer.add_reference(die, dw.DW_AT_type, child_type_die)

    values = datatype.getValues()
    for i in range(len(values)):
        value = values[i]
        name = datatype.getName(value)
        child_die = producer.new_die(dw.DW_TAG_enumerator, parent=die)
        producer.add_name(child_die, name)
        producer.add_unsigned_const(child_die, dw.DW_AT_const_value, value)

    return die


def add_struct_type(producer, cu, struct, key):
    die = producer.new_die(dw.DW_TAG_structure_type, parent=cu)
    record[key] = die

    struct_name = struct.getName() or "<anonymous>"
    producer.add_name(die, struct_name.replace("struct", ""))
    producer.add_unsigned_const(die, dw.DW_AT_byte_size, struct.getLength())

    for component in struct.getComponents():
        member_die = producer.new_die(dw.DW_TAG_member, parent=die)
        member_type_die = add_type(producer, cu, component.getDataType())

        producer.add_reference(member_die, dw.DW_AT_type, member_type_die)
        producer.add_name(
            member_die,
            component.getFieldName() or component.getDefaultFieldName(),
        )

        loc_expr = producer.new_expr()
        producer.add_expr_gen(loc_expr, dw.DW_OP_plus_uconst, component.getOffset())
        producer.add_location_expr(
            member_die, dw.DW_AT_data_member_location, loc_expr
        )

    return die


def add_array_type(producer, cu, array, key):
    die = producer.new_die(dw.DW_TAG_array_type, parent=cu)
    record[key] = die

    element_type = array.getDataType()
    element_die = add_type(producer, cu, element_type)
    producer.add_reference(die, dw.DW_AT_type, element_die)

    subrange = producer.new_die(dw.DW_TAG_subrange_type, parent=die)
    element_length = element_type.getLength()
    count = array.getLength() // element_length if element_length else 0
    producer.add_unsigned_const(subrange, dw.DW_AT_count, count)

    return die


def main():
    global decompiler
    global register_mappings
    global exe_path
    global out_path
    global decompiled_c_path

    exe_path, out_path, decompiled_c_path = get_output_paths()

    decompiler = generate_decomp_interface()
    register_mappings = generate_register_mappings()

    pointer64 = curr.getDefaultPointerSize() == 8
    little_endian = not curr.getMemory().isBigEndian()
    isa_name = get_isa_name(pointer64)

    print("libdwarfp target:", isa_name, "DWARF v4")

    with DwarfProducer(
        isa_name=isa_name,
        dwarf_version="V4",
        pointer64=pointer64,
        little_endian=little_endian,
    ) as producer:
        add_debug_info(producer)
        write_source()
        sections = producer.transform()

    add_sections_to_elf(exe_path, out_path, list(sections.items()))

    print("Done.")
    print("ELF saved to", out_path)
    print("C source saved to", decompiled_c_path)


if __name__ == "__main__":
    main()
