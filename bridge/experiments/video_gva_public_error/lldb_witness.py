# SPDX-License-Identifier: MIT
"""Install bounded hardware breakpoints after a controlled process marker."""
import hashlib
import os
import struct
import lldb

EXPECTED = {}
IMAGE_BASE = 0
VT_BASE = 0
GVA_REGIONS = (
    (115359, 719, 'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c'),
    (117024, 176, 'c4ef1c90c52e607a307e995c036890376ebf959ba9ade05725ff02c5cc1b7273'),
    (232918, 136, '80adc25382ccad971d4388af6ab616ae65200ab934d6819a7cbd54c9efdba68f'),
    (146236, 112, '38281d047ee261127550cff96495d8aa7a911fe889fb6f7a6ac2992f3bbb274c'),
    (262270, 2452, '2ce45fe6c3ffc591e794e46655393ba2848540f55c891bfbf1f189e6d0e4c9e0'),
)


def arm(frame, bp_loc, internal_dict):
    global IMAGE_BASE, VT_BASE
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
        for name in ('kp_failure_path', 'kp_gva_exit', 'kp_vt_return'):
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
        modules = [m for m in target.module_iter() if m.GetFileSpec().GetFilename() == 'VideoToolbox']
        if len(modules) != 1 or (modules[0].GetUUIDString() or '').replace('-', '').lower() != 'e7231bea63883d0a95c0a93ce970b96b':
            print('KP_HW_ARM_FAIL vt_identity', flush=True); return False
        vt_base = modules[0].GetObjectFileHeaderAddress().GetLoadAddress(target)
        error = lldb.SBError()
        vt_code = process.ReadMemory(vt_base + 4298704, 2061, error)
        if not error.Success() or len(vt_code) != 2061 or hashlib.sha256(vt_code).hexdigest() != 'f3cb75d0d4d4c97e2ca66ed815bd0fa636d96f6c955ba98d0fe8be39860a7a60':
            print('KP_HW_ARM_FAIL vt_live_region', flush=True); return False
        addresses = [base + 264187, base + 262333, vt_base + 4300698]
        IMAGE_BASE = base
        VT_BASE = vt_base
    for name, address in zip(('failure_path', 'gva_exit', 'vt_return'), addresses):
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
    result = frame.FindRegister('eax')
    result_valid = int(result.IsValid() and name in ('gva_exit', 'vt_return'))
    result_value = result.GetValueAsUnsigned(0) & 0xffffffff if result_valid else 0
    if result_value >= 0x80000000:
        result_value -= 0x100000000
    caller_matches_vt = int(name == 'gva_exit' and VT_BASE and pc == VT_BASE + 4300698)
    print('KP_HW_HIT name=%s bytes_match=%d thread=%d result_valid=%d result=%d caller_vt_match=%d' %
          (name, int(error.Success() and current == original), thread.GetThreadID(), result_valid, result_value, caller_matches_vt), flush=True)
    return False
