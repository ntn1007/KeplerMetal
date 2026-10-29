# SPDX-License-Identifier: MIT
"""Install bounded hardware breakpoints after a controlled process marker."""
import hashlib
import os
import struct
import lldb

EXPECTED = {}
IMAGE_BASE = 0
GVA_REGIONS = (
    (115359, 719, 'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c'),
    (117024, 176, 'c4ef1c90c52e607a307e995c036890376ebf959ba9ade05725ff02c5cc1b7273'),
    (232918, 136, '80adc25382ccad971d4388af6ab616ae65200ab934d6819a7cbd54c9efdba68f'),
    (146236, 112, '38281d047ee261127550cff96495d8aa7a911fe889fb6f7a6ac2992f3bbb274c'),
    (262270, 2452, '2ce45fe6c3ffc591e794e46655393ba2848540f55c891bfbf1f189e6d0e4c9e0'),
)


def arm(frame, bp_loc, internal_dict):
    global IMAGE_BASE
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
        for name in ('kp_after_dispatch', 'kp_failure_path', 'kp_nonempty_path'):
            contexts = target.FindFunctions(name)
            if contexts.GetSize() != 1:
                print('KP_HW_ARM_FAIL cpu_symbol', flush=True)
                return False
            address = contexts.GetContextAtIndex(0).GetFunction().GetStartAddress().GetLoadAddress(target)
            addresses.append(address)
        if base != addresses[0]:
            print('KP_HW_ARM_FAIL cpu_base', flush=True)
            return False
    else:
        for offset, size, expected in GVA_REGIONS:
            error = lldb.SBError()
            data = process.ReadMemory(base + offset, size, error)
            if not error.Success() or len(data) != size or hashlib.sha256(data).hexdigest() != expected:
                print('KP_HW_ARM_FAIL live_region', flush=True)
                return False
        addresses = [base + 264163, base + 264187, base + 264221]
        IMAGE_BASE = base
    for name, address in zip(('after_dispatch', 'failure_path', 'nonempty_path'), addresses):
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
    del internal_dict
    saved = EXPECTED.get(bp_loc.GetBreakpoint().GetID())
    if saved is None:
        print('KP_HW_HIT_FAIL unknown_breakpoint', flush=True)
        return False
    name, address, original = saved
    error = lldb.SBError()
    current = frame.GetThread().GetProcess().ReadMemory(address, len(original), error)
    thread = frame.GetThread()
    register = frame.FindRegister('r14')
    parent = thread.GetFrameAtIndex(1)
    pc = parent.GetPC() if parent.IsValid() else 0
    caller_offset = pc - IMAGE_BASE if IMAGE_BASE and pc >= IMAGE_BASE else 0
    valid, value = 0, 0
    if name == 'after_dispatch':
        pointer = frame.FindRegister('r12')
        if pointer.IsValid():
            field_error = lldb.SBError()
            field = frame.GetThread().GetProcess().ReadMemory(pointer.GetValueAsUnsigned(0), 4, field_error)
            if field_error.Success() and len(field) == 4:
                valid, value = 1, struct.unpack('<I', field)[0]
    result = frame.FindRegister('eax')
    result_valid = int(name == 'after_dispatch' and result.IsValid())
    result_value = result.GetValueAsUnsigned(0) if result_valid else 0
    print('KP_HW_HIT name=%s bytes_match=%d thread=%d r14_valid=%d r14=%d caller_offset=%d field_valid=%d field=%d result_valid=%d result=%d' %
          (name, int(error.Success() and current == original), thread.GetThreadID(),
           int(register.IsValid()), register.GetValueAsUnsigned(0), caller_offset, valid, value, result_valid, result_value), flush=True)
    return False
