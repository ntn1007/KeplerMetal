# SPDX-License-Identifier: MIT
"""Read one pinned AppleGVA free binding in the debugged process."""
import struct
import lldb
import lldb_witness

GOT_OFFSET = 847829912


def inspect(process, slot, expected):
    error=lldb.SBError();data=process.ReadMemory(slot,8,error)
    if not error.Success() or len(data)!=8:return None
    return struct.unpack('<Q',data)[0]==expected


def arm(frame,bp_loc,internal_dict):
    lldb_witness.arm(frame,bp_loc,internal_dict)
    if not lldb_witness.EXPECTED:
        print('KP_HEAP_BINDING_ARM_FAIL witness_not_armed',flush=True);return False
    process=frame.GetThread().GetProcess();target=process.GetTarget()
    symbols=target.FindSymbols('observed_free')
    if symbols.GetSize()!=1:
        print('KP_HEAP_BINDING_ARM_FAIL symbol_count',flush=True);return False
    symbol=symbols.GetContextAtIndex(0).GetSymbol()
    if not symbol.IsValid():
        print('KP_HEAP_BINDING_ARM_FAIL symbol_invalid',flush=True);return False
    expected=symbol.GetStartAddress().GetLoadAddress(target)
    base=frame.FindRegister('rdi').GetValueAsUnsigned(0)
    matched=inspect(process,base+GOT_OFFSET,expected)
    if matched is None:
        print('KP_HEAP_BINDING_ARM_FAIL slot_unreadable',flush=True);return False
    print('KP_HEAP_BINDING matched=%d' % int(matched),flush=True)
    return False
