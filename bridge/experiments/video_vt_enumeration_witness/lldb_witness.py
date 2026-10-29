# SPDX-License-Identifier: MIT
"""Observe returned values with hardware breakpoints; no expression execution."""
import hashlib
import os
import lldb

POINTS={}
LIST={}
def arm(frame,bp_loc,internal_dict):
    del bp_loc,internal_dict
    process=frame.GetThread().GetProcess(); target=process.GetTarget(); mode=os.environ.get('KM_TRACE_MODE')
    if frame.FindRegister('rdi').GetValueAsUnsigned()!=0xabc0 or mode not in ('cpu','video'):
        print('KM_TRACE_ARM_FAIL marker',flush=True);return False
    if mode=='cpu':
        addresses=[]
        for name in ('KMAfterList','KMAfterBatch'):
            contexts=target.FindSymbols(name,lldb.eSymbolTypeAny)
            if contexts.GetSize()!=1:
                print('KM_TRACE_ARM_FAIL symbol',flush=True);return False
            addresses.append(contexts.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(target))
    else:
        modules=[m for m in target.module_iter() if m.GetFileSpec().GetFilename()=='VideoToolbox']
        if len(modules)!=1 or (modules[0].GetUUIDString() or '').replace('-','').lower()!='e7231bea63883d0a95c0a93ce970b96b':
            print('KM_TRACE_ARM_FAIL image',flush=True);return False
        base=modules[0].GetObjectFileHeaderAddress().GetLoadAddress(target);err=lldb.SBError()
        data=process.ReadMemory(base+0x5fd95f,3420,err)
        if not err.Success() or hashlib.sha256(data).hexdigest()!='f38fc93a01c9f5c715b94b5a2fe6a45c7ebccba26cdd0cedcadb06b7ffe9478b':
            print('KM_TRACE_ARM_FAIL code',flush=True);return False
        sel=process.ReadPointerFromMemory(base+0x2bfaae00,err)
        if not err.Success() or not sel:
            print('KM_TRACE_ARM_FAIL selector_pointer',flush=True);return False
        name=process.ReadCStringFromMemory(sel,128,err)
        if not err.Success() or name!='countByEnumeratingWithState:objects:count:':
            print('KM_TRACE_ARM_FAIL selector',flush=True);return False
        addresses=[base+0x5fd9fb,base+0x5fda32]
    for name,address in zip(('list','batch'),addresses):
        err=lldb.SBError(); original=process.ReadMemory(address,8,err)
        if not err.Success() or len(original)!=8:
            print('KM_TRACE_ARM_FAIL bytes',flush=True);return False
        response=lldb.SBCommandReturnObject()
        target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint set -H -G true -a 0x%x -N km_%s'%(address,name),response)
        if not response.Succeeded():print('KM_TRACE_ARM_FAIL breakpoint',flush=True);return False
        bp=target.GetBreakpointAtIndex(target.GetNumBreakpoints()-1);response=lldb.SBCommandReturnObject()
        target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint command add -F lldb_witness.hit %d'%bp.GetID(),response)
        if not response.Succeeded():print('KM_TRACE_ARM_FAIL callback',flush=True);return False
        POINTS[bp.GetID()]=(name,address,original)
    print('KM_TRACE_ARM_PASS mode='+mode,flush=True);return False

def hit(frame,bp_loc,internal_dict):
    del internal_dict
    item=POINTS.get(bp_loc.GetBreakpoint().GetID())
    if not item:print('KM_TRACE_HIT_FAIL unknown',flush=True);return False
    name,address,original=item;thread=frame.GetThread();error=lldb.SBError();current=thread.GetProcess().ReadMemory(address,8,error)
    reg=frame.FindRegister('rax');tid=thread.GetThreadID()
    if not reg.IsValid() or not error.Success() or current!=original:
        print('KM_TRACE_HIT_FAIL bytes_or_register',flush=True);return False
    value=reg.GetValueAsUnsigned()
    if name=='list':
        LIST[tid]=value;print('KM_TRACE_LIST thread=%d nonnull=%d bytes_match=1'%(tid,int(value!=0)),flush=True)
    else:
        reg12=frame.FindRegister('r12');same=reg12.IsValid() and tid in LIST and reg12.GetValueAsUnsigned()==LIST[tid]
        print('KM_TRACE_BATCH thread=%d count=%d same_list=%d bytes_match=1'%(tid,value,int(same)),flush=True)
    return False
