# SPDX-License-Identifier: MIT
"""Read three pinned classification checkpoints without modifying the target."""
import hashlib
import os
import struct
import lldb

EXPECTED={}
IMAGE_BASE=0
CLASSIFIED={}
REGIONS=((115359,719,'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c'),
 (117024,176,'c4ef1c90c52e607a307e995c036890376ebf959ba9ade05725ff02c5cc1b7273'),
 (232918,136,'80adc25382ccad971d4388af6ab616ae65200ab934d6819a7cbd54c9efdba68f'),
 (146236,112,'38281d047ee261127550cff96495d8aa7a911fe889fb6f7a6ac2992f3bbb274c'),
 (146348,1136,'4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564'),
 (148746,2669,'f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19'))


def arm(frame,bp_loc,internal_dict):
    global IMAGE_BASE
    del bp_loc,internal_dict
    process=frame.GetThread().GetProcess();target=process.GetTarget();base=frame.FindRegister('rdi').GetValueAsUnsigned(0)
    mode=os.environ.get('KP_HW_WITNESS_MODE')
    if not base or mode not in ('cpu','gva'):
        print('KP_HW_ARM_FAIL mode_or_base',flush=True);return False
    if mode=='cpu':
        ctx=target.FindFunctions('kp_after_base')
        if ctx.GetSize()!=1 or base!=ctx.GetContextAtIndex(0).GetFunction().GetStartAddress().GetLoadAddress(target):
            print('KP_HW_ARM_FAIL cpu_base',flush=True);return False
        addresses=[]
        for name in ('kp_classify','kp_skip','kp_after_enumeration'):
            ctx=target.FindFunctions(name)
            if ctx.GetSize()!=1:
                print('KP_HW_ARM_FAIL cpu_symbol',flush=True);return False
            addresses.append(ctx.GetContextAtIndex(0).GetFunction().GetStartAddress().GetLoadAddress(target))
    else:
        for off,size,wanted in REGIONS:
            error=lldb.SBError();data=process.ReadMemory(base+off,size,error)
            if not error.Success() or len(data)!=size or hashlib.sha256(data).hexdigest()!=wanted:
                print('KP_HW_ARM_FAIL live_region',flush=True);return False
        addresses=[base+146629,base+146619,base+115796];IMAGE_BASE=base
    for name,address in zip(('classify','skip','after_enumeration'),addresses):
        error=lldb.SBError();original=process.ReadMemory(address,8,error)
        if not error.Success() or len(original)!=8:
            print('KP_HW_ARM_FAIL target_bytes',flush=True);return False
        response=lldb.SBCommandReturnObject();target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint set -H -G true -a 0x%x -N kp_%s'%(address,name),response)
        if not response.Succeeded():
            print('KP_HW_ARM_FAIL breakpoint '+response.GetError(),flush=True);return False
        bp=target.GetBreakpointAtIndex(target.GetNumBreakpoints()-1)
        response=lldb.SBCommandReturnObject();target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint command add -F lldb_witness.hit %d'%bp.GetID(),response)
        if not bp.IsValid() or not response.Succeeded():
            print('KP_HW_ARM_FAIL callback',flush=True);return False
        EXPECTED[bp.GetID()]=(name,address,original)
    print('KP_HW_ARM_PASS mode='+mode,flush=True);return False


def read(process,address,length):
    error=lldb.SBError();data=process.ReadMemory(address,length,error)
    return data if error.Success() and len(data)==length else None


def hit(frame,bp_loc,internal_dict):
    del internal_dict
    saved=EXPECTED.get(bp_loc.GetBreakpoint().GetID())
    if not saved:
        print('KP_HW_HIT_FAIL unknown_breakpoint',flush=True);return False
    name,address,original=saved;thread=frame.GetThread();process=thread.GetProcess();tid=thread.GetThreadID()
    current=read(process,address,len(original));parent=thread.GetFrameAtIndex(1);pc=parent.GetPC() if parent.IsValid() else 0
    caller=pc-IMAGE_BASE if IMAGE_BASE and pc>=IMAGE_BASE else 0
    kind_valid=0;kind=0;flags_valid=0;flags=(0,0,0,0);same=0;node=0;field_valid=0;field=0
    if name in ('classify','skip'):
        reg=frame.FindRegister('rax');node=reg.GetValueAsUnsigned(0) if reg.IsValid() else 0
        data=read(process,node+0x428,4) if node else None
        b=read(process,node+0x460,4) if node else None
        if data is not None:kind_valid=1;kind=struct.unpack('<I',data)[0]
        if b is not None:flags_valid=1;flags=tuple(b)
        if name=='classify': CLASSIFIED[tid]=node if node else None
        else: same=int(node!=0 and CLASSIFIED.get(tid)==node)
    else:
        reg=frame.FindRegister('rbx');ptr=reg.GetValueAsUnsigned(0) if reg.IsValid() else 0
        data=read(process,ptr,4) if ptr else None
        if data is not None:field_valid=1;field=struct.unpack('<I',data)[0]
    print('KP_CLASS_HIT name=%s bytes_match=%d thread=%d caller_offset=%d kind_valid=%d kind=%d flags_valid=%d flags=%d,%d,%d,%d same_prior=%d field_valid=%d field=%d' %
          (name,int(current==original),tid,caller,kind_valid,kind,flags_valid,*flags,same,field_valid,field),flush=True)
    return False
