# SPDX-License-Identifier: MIT
"""Arm an own-process heap watcher from the pinned property breakpoint."""
import struct
import lldb
import lldb_binding
import lldb_target
import lldb_witness

ORIGINAL_HIT=lldb_witness.hit
TARGET_SLOT=None
FREE_SLOT=None
ZONE_SLOT=None
TRACK_NODE=0
BASE=0
FREE_IMPL=0


def library_symbol(target,name):
    found=target.FindSymbols(name)
    if found.GetSize()!=1:return None
    context=found.GetContextAtIndex(0);module=context.GetModule();symbol=context.GetSymbol()
    if not module.IsValid() or module.GetFileSpec().GetFilename()!='heap-watch.dylib' or not symbol.IsValid():return None
    address=symbol.GetStartAddress().GetLoadAddress(target)
    return address if address and address!=lldb.LLDB_INVALID_ADDRESS else None


def u64(process,address):
    data=lldb_target.read(process,address,8)
    return struct.unpack('<Q',data)[0] if data is not None else None


def u32(process,address):
    data=lldb_target.read(process,address,4)
    return struct.unpack('<I',data)[0] if data is not None else None


def hit(frame,bp_loc,internal_dict):
    global TRACK_NODE
    saved=lldb_witness.EXPECTED.get(bp_loc.GetBreakpoint().GetID())
    if saved is None:
        print('KP_HW_HIT_FAIL tracking_breakpoint',flush=True);return False
    name=saved[0];process=frame.GetThread().GetProcess()
    if name=='property_return':
        pointer=frame.FindRegister('r14').GetValueAsUnsigned(0)
        binding=lldb_binding.inspect(process,BASE+lldb_binding.GOT_OFFSET,FREE_IMPL)
        if TRACK_NODE or not pointer or binding is not True or not lldb_target.set_target(process,TARGET_SLOT,pointer):
            print('KP_HW_HIT_FAIL tracking_arm',flush=True);return False
        TRACK_NODE=pointer
        print('KP_HEAP_TRACK_ARM bound=1 target_written=1',flush=True)
    if name=='list_entry':
        free_count=u32(process,FREE_SLOT);zone_count=u32(process,ZONE_SLOT);target=u64(process,TARGET_SLOT)
        binding=lldb_binding.inspect(process,BASE+lldb_binding.GOT_OFFSET,FREE_IMPL)
        if not TRACK_NODE or free_count is None or zone_count is None or target!=TRACK_NODE or binding is not True:
            print('KP_HW_HIT_FAIL tracking_read',flush=True);return False
        req=u32(process,lldb_witness.REQUEST_ADDRESS)
        if req is None or req>3:
            print('KP_HW_HIT_FAIL tracking_window',flush=True);return False
        print('KP_HEAP_TRACK_LIST window=%d free_hits=%d zone_hits=%d bound=1 target_ok=1' %
              (req,free_count,zone_count),flush=True)
    return ORIGINAL_HIT(frame,bp_loc,internal_dict)


def arm(frame,bp_loc,internal_dict):
    global TARGET_SLOT,FREE_SLOT,ZONE_SLOT,BASE,FREE_IMPL
    process=frame.GetThread().GetProcess();target=process.GetTarget()
    TARGET_SLOT=library_symbol(target,'KPHeapTarget');FREE_SLOT=library_symbol(target,'KPHeapFreeCount')
    ZONE_SLOT=library_symbol(target,'KPHeapZoneCount');FREE_IMPL=library_symbol(target,'observed_free')
    BASE=frame.FindRegister('rdi').GetValueAsUnsigned(0)
    if not all((TARGET_SLOT,FREE_SLOT,ZONE_SLOT,FREE_IMPL,BASE)) or u64(process,TARGET_SLOT)!=1 or u32(process,FREE_SLOT)!=0 or u32(process,ZONE_SLOT)!=0:
        print('KP_HW_ARM_FAIL tracker_initial',flush=True);return False
    lldb_witness.hit=hit
    return lldb_binding.arm(frame,bp_loc,internal_dict)
