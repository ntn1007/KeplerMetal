# SPDX-License-Identifier: MIT
"""Arm the original cache callback on an original CPU-only target."""
import lldb
import lldb_witness


def arm(frame, bp_loc, internal_dict):
    del bp_loc, internal_dict
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    base = frame.FindRegister('rdi').GetValueAsUnsigned(0)
    contexts = target.FindFunctions('kp_after_base')
    checks = target.FindFunctions('kp_cache_target')
    if contexts.GetSize() != 1 or checks.GetSize() != 1:
        print('KP_CACHE_CAL_FAIL symbols', flush=True); return False
    expected_base = contexts.GetContextAtIndex(0).GetFunction().GetStartAddress().GetLoadAddress(target)
    cache_context = checks.GetContextAtIndex(0)
    cache_function = cache_context.GetFunction()
    cache_symbol = cache_context.GetSymbol()
    location = cache_function.GetStartAddress() if cache_function.IsValid() else cache_symbol.GetStartAddress()
    address = location.GetLoadAddress(target)
    if not base or base != expected_base:
        print('KP_CACHE_CAL_FAIL base', flush=True); return False
    error = lldb.SBError()
    original = process.ReadMemory(address, 8, error)
    if not error.Success() or len(original) != 8:
        print('KP_CACHE_CAL_FAIL bytes', flush=True); return False
    interp = target.GetDebugger().GetCommandInterpreter()
    response = lldb.SBCommandReturnObject()
    interp.HandleCommand('breakpoint set -H -G true -a 0x%x -N kp_cpu_cache' % address, response)
    if not response.Succeeded():
        print('KP_CACHE_CAL_FAIL breakpoint', flush=True); return False
    bp = target.GetBreakpointAtIndex(target.GetNumBreakpoints()-1)
    response = lldb.SBCommandReturnObject()
    interp.HandleCommand('breakpoint command add -F lldb_witness.hit %d' % bp.GetID(), response)
    if not response.Succeeded():
        print('KP_CACHE_CAL_FAIL callback', flush=True); return False
    lldb_witness.EXPECTED[bp.GetID()] = ('after_enumeration', address, original)
    # Enable the exact cached-reader branch in the unmodified witness callback.
    lldb_witness.IMAGE_BASE = base
    print('KP_CACHE_CAL_ARMED', flush=True)
    return False
