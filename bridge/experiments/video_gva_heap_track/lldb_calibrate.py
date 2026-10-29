# SPDX-License-Identifier: MIT
import lldb
import lldb_target


def hit(frame,bp_loc,internal_dict):
    del bp_loc,internal_dict
    process=frame.GetThread().GetProcess();target=process.GetTarget()
    addr=lldb_target.symbol(target,'KPHeapTarget')
    pointer=frame.FindRegister('rdi').GetValueAsUnsigned(0)
    ok=addr is not None and lldb_target.set_target(process,addr,pointer)
    print('KP_HEAP_TARGET_WRITE success=%d' % int(ok),flush=True)
    return False
