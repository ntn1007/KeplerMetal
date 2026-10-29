# SPDX-License-Identifier: MIT
"""Install bounded hardware breakpoints after a controlled process marker."""
import hashlib
import os
import struct
import lldb

EXPECTED = {}
IMAGE_BASE = 0
PROPERTY_NODE = None
REQUEST_ADDRESS = 0
GVA_REGIONS = (
    (115359, 719, 'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c'),
    (117024, 176, 'c4ef1c90c52e607a307e995c036890376ebf959ba9ade05725ff02c5cc1b7273'),
    (232918, 136, '80adc25382ccad971d4388af6ab616ae65200ab934d6819a7cbd54c9efdba68f'),
    (146236, 112, '38281d047ee261127550cff96495d8aa7a911fe889fb6f7a6ac2992f3bbb274c'),
    (146348, 1136, '4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564'),
    (148746, 2669, 'f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19'),
)


def arm(frame, bp_loc, internal_dict):
    global IMAGE_BASE, REQUEST_ADDRESS
    del bp_loc, internal_dict
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    base = frame.FindRegister('rdi').GetValueAsUnsigned(0)
    mode = os.environ.get('KP_HW_WITNESS_MODE')
    if not base or mode not in ('cpu', 'gva'):
        print('KP_HW_ARM_FAIL mode_or_base', flush=True)
        return False
    if mode == 'cpu':
        addresses = []
        for name in ('kp_property_return', 'kp_list_entry', 'kp_after_enumeration'):
            contexts = target.FindFunctions(name)
            if contexts.GetSize() != 1:
                print('KP_HW_ARM_FAIL cpu_symbol', flush=True)
                return False
            address = contexts.GetContextAtIndex(0).GetFunction().GetStartAddress().GetLoadAddress(target)
            addresses.append(address)
        contexts = target.FindFunctions('kp_after_base')
        if contexts.GetSize() != 1 or base != contexts.GetContextAtIndex(0).GetFunction().GetStartAddress().GetLoadAddress(target):
            print('KP_HW_ARM_FAIL cpu_base', flush=True)
            return False
    else:
        for offset, size, expected in GVA_REGIONS:
            error = lldb.SBError()
            data = process.ReadMemory(base + offset, size, error)
            if not error.Success() or len(data) != size or hashlib.sha256(data).hexdigest() != expected:
                print('KP_HW_ARM_FAIL live_region', flush=True)
                return False
        addresses = [base + 150812, base + 146410, base + 150964]
        IMAGE_BASE = base
    symbols = target.FindSymbols("kp_request_index")
    if symbols.GetSize() != 1:
        print('KP_HW_ARM_FAIL request_symbol', flush=True); return False
    symbol = symbols.GetContextAtIndex(0).GetSymbol()
    if not symbol.IsValid():
        print('KP_HW_ARM_FAIL request_symbol_invalid', flush=True); return False
    REQUEST_ADDRESS = symbol.GetStartAddress().GetLoadAddress(target)
    request_error = lldb.SBError()
    initial = process.ReadMemory(REQUEST_ADDRESS, 4, request_error)
    if not request_error.Success() or len(initial) != 4 or struct.unpack('<I', initial)[0] > 3:
        print('KP_HW_ARM_FAIL request_initial', flush=True); return False
    print('KP_REQUEST_ARM window=%d' % struct.unpack('<I', initial)[0], flush=True)
    for name, address in zip(('property_return', 'list_entry', 'after_enumeration'), addresses):
        error = lldb.SBError()
        original = process.ReadMemory(address, 8, error)
        if not error.Success() or len(original) != 8:
            print('KP_HW_ARM_FAIL target_bytes', flush=True)
            return False
        response = lldb.SBCommandReturnObject()
        target.GetDebugger().GetCommandInterpreter().HandleCommand(
            'breakpoint set -H -G true -a 0x%x -N kp_%s' % (address, name), response)
        if not response.Succeeded():
            print('KP_HW_ARM_FAIL breakpoint ' + response.GetError(), flush=True)
            return False
        bp = target.GetBreakpointAtIndex(target.GetNumBreakpoints() - 1)
        if not bp.IsValid():
            print('KP_HW_ARM_FAIL callback', flush=True)
            return False
        response = lldb.SBCommandReturnObject()
        target.GetDebugger().GetCommandInterpreter().HandleCommand(
            'breakpoint command add -F lldb_witness.hit %d' % bp.GetID(), response)
        if not response.Succeeded():
            print('KP_HW_ARM_FAIL callback ' + response.GetError(), flush=True)
            return False
        EXPECTED[bp.GetID()] = (name, address, original)
    print('KP_HW_ARM_PASS mode=' + mode, flush=True)
    return False


def hit(frame, bp_loc, internal_dict):
    global PROPERTY_NODE
    del internal_dict
    saved = EXPECTED.get(bp_loc.GetBreakpoint().GetID())
    if saved is None:
        print('KP_HW_HIT_FAIL unknown_breakpoint', flush=True)
        return False
    name, address, original = saved
    req_error = lldb.SBError()
    request_data = frame.GetThread().GetProcess().ReadMemory(REQUEST_ADDRESS, 4, req_error)
    if not req_error.Success() or len(request_data) != 4:
        print('KP_HW_HIT_FAIL request_read', flush=True); return False
    request = struct.unpack('<I', request_data)[0]
    if request > 3:
        print('KP_HW_HIT_FAIL request_range', flush=True); return False
    print('KP_REQUEST_HIT name=%s thread=%d request_window=%d' %
          (name, frame.GetThread().GetThreadID(), request), flush=True)
    error = lldb.SBError()
    current = frame.GetThread().GetProcess().ReadMemory(address, len(original), error)
    thread = frame.GetThread()
    register = frame.FindRegister('r14')
    parent = thread.GetFrameAtIndex(1)
    pc = parent.GetPC() if parent.IsValid() else 0
    caller_offset = pc - IMAGE_BASE if IMAGE_BASE and pc >= IMAGE_BASE else 0
    valid, value = 0, 0
    if name == 'after_enumeration' and not IMAGE_BASE:
        pointer = frame.FindRegister('rbx')
        if pointer.IsValid():
            field_error = lldb.SBError()
            field = frame.GetThread().GetProcess().ReadMemory(pointer.GetValueAsUnsigned(0), 4, field_error)
            if field_error.Success() and len(field) == 4:
                valid, value = 1, struct.unpack('<I', field)[0]
    if name == 'after_enumeration':
        candidate = frame.FindRegister('rdi')
        value_candidate = candidate.GetValueAsUnsigned(0) if candidate.IsValid() else 0
        compared = int(bool(value_candidate) and PROPERTY_NODE is not None)
        matches = int(compared and value_candidate == PROPERTY_NODE)
        print('KP_NODE_FREE_CANDIDATE thread=%d request_window=%d compared=%d matches=%d' %
              (thread.GetThreadID(), request, compared, matches), flush=True)
    head = frame.FindRegister('rax')
    flag = frame.FindRegister('edx')
    selector = frame.FindRegister('edi')
    list_valid = int(name == 'list_entry' and head.IsValid() and flag.IsValid() and selector.IsValid())
    property_valid, property_present, node_flag_valid, node_flag = 0, 0, 0, 0
    if name == 'property_return' and head.IsValid() and register.IsValid():
        property_valid = 1
        property_present = int(head.GetValueAsUnsigned(0) != 0)
        node = register.GetValueAsUnsigned(0)
        PROPERTY_NODE = node if node else None
        if node:
            node_error = lldb.SBError()
            byte = frame.GetThread().GetProcess().ReadMemory(node + 0x463, 1, node_error)
            if node_error.Success() and len(byte) == 1:
                node_flag_valid, node_flag = 1, byte[0]
    link_valid = int(list_valid and PROPERTY_NODE is not None)
    same_node = int(link_valid and head.GetValueAsUnsigned(0) == PROPERTY_NODE)
    print('KP_HW_HIT name=%s bytes_match=%d thread=%d r14_valid=%d r14=%d caller_offset=%d field_valid=%d field=%d list_valid=%d head_present=%d flag=%d selector=%d prop_valid=%d prop_present=%d node_flag_valid=%d node_flag=%d link_valid=%d same_node=%d' %
          (name, int(error.Success() and current == original), thread.GetThreadID(),
           int(register.IsValid()), register.GetValueAsUnsigned(0) if name != 'property_return' else 0, caller_offset, valid, value,
           list_valid, int(list_valid and head.GetValueAsUnsigned(0) != 0),
           flag.GetValueAsUnsigned(0) if list_valid else 0, selector.GetValueAsUnsigned(0) if list_valid else 0,
           property_valid, property_present, node_flag_valid, node_flag, link_valid, same_node), flush=True)
    if name == 'list_entry' and list_valid:
        inspect_nodes(frame.GetThread().GetProcess(), head.GetValueAsUnsigned(0), caller_offset, thread.GetThreadID())
    return False


def inspect_nodes(process, address, caller_offset, thread_id):
    seen = set()
    reason = 'end'
    while address:
        if address in seen:
            reason = 'cycle'
            break
        if len(seen) >= 16:
            reason = 'limit'
            break
        seen.add(address)
        fields = []
        for offset, length in ((0, 8), (0x428, 4), (0x460, 4)):
            error = lldb.SBError()
            data = process.ReadMemory(address + offset, length, error)
            if not error.Success() or len(data) != length:
                reason = 'unreadable'
                break
            fields.append(data)
        if reason != 'end':
            break
        next_address = struct.unpack('<Q', fields[0])[0]
        kind = struct.unpack('<I', fields[1])[0]
        flags = tuple(fields[2])
        print('KP_LIST_NODE caller_offset=%d thread=%d index=%d kind=%d flags=%d,%d,%d,%d next_present=%d' %
              (caller_offset, thread_id, len(seen) - 1, kind, *flags, int(next_address != 0)), flush=True)
        address = next_address
    print('KP_LIST_END caller_offset=%d thread=%d visited=%d reason=%s' %
          (caller_offset, thread_id, len(seen), reason), flush=True)
