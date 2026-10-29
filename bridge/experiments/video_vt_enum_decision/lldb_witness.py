# SPDX-License-Identifier: MIT
"""Observe natural device/list identity with bounded reads and hardware breakpoints."""
import hashlib,os,struct,lldb
POINTS={};LIST={};DEVICE={};FILTER={};DICT={};NAME={};CMP={};RESULT={};EXTRAS={};RID=0;IVAR=0;IVAR_REF=0;COMPARE_KEY=0
def arm(frame,bp_loc,internal_dict):
    global RID,IVAR,IVAR_REF,COMPARE_KEY
    del bp_loc,internal_dict
    process=frame.GetThread().GetProcess();target=process.GetTarget();mode=os.environ.get('KM_TRACE_MODE')
    RID=frame.FindRegister('rsi').GetValueAsUnsigned(0)
    if frame.FindRegister('rdi').GetValueAsUnsigned()!=0xabc0 or not RID or mode not in ('cpu','video'):
        print('KM_TRACE_ARM_FAIL marker',flush=True);return False
    if mode=='cpu':
        addresses=[];IVAR=0
        for name in ('KMAfterRegistry','KMAfterList','KMAfterBatch','KMBeforeFilter','KMAfterFilter','KMAfterDict','KMAfterReg','KMAfterName','KMBeforeCompare','KMAfterCompare','KMAfterNext','KMBranchTest','KMPathZero','KMPathNonzero'):
            contexts=target.FindSymbols(name,lldb.eSymbolTypeAny)
            if contexts.GetSize()!=1:print('KM_TRACE_ARM_FAIL symbol',flush=True);return False
            addresses.append(contexts.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(target))
        symbols=target.FindSymbols('KMIGPU',lldb.eSymbolTypeAny)
        if symbols.GetSize()!=1:print('KM_TRACE_ARM_FAIL cpu_key',flush=True);return False
        COMPARE_KEY=symbols.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(target)
    else:
        def module(name,uuid):
            matches=[m for m in target.module_iter() if m.GetFileSpec().GetFilename()==name]
            return matches[0] if len(matches)==1 and (matches[0].GetUUIDString() or '').replace('-','').lower()==uuid else None
        vt=module('VideoToolbox','e7231bea63883d0a95c0a93ce970b96b');metal=module('MetalOld.dylib','6581cd53858338d1b4b9773f1dc3f551')
        if not vt or not metal:print('KM_TRACE_ARM_FAIL image',flush=True);return False
        vb=vt.GetObjectFileHeaderAddress().GetLoadAddress(target);mb=metal.GetObjectFileHeaderAddress().GetLoadAddress(target);err=lldb.SBError()
        for address,size,digest in ((vb+0x5fd95f,3420,'f38fc93a01c9f5c715b94b5a2fe6a45c7ebccba26cdd0cedcadb06b7ffe9478b'),(mb+0x1cbe,132,'f2df1f2af9af40e440eb1b78a4010bdbf6f4eaa4618a2d19322c5e4026f7a7fe'),(vb+0x5fea84,867,'b2b4a259e7b62af742beec8c6b6acbf8351443fc7edc0defe9ecd8ef6d2c1dad')):
            data=process.ReadMemory(address,size,err)
            if not err.Success() or hashlib.sha256(data).hexdigest()!=digest:print('KM_TRACE_ARM_FAIL code',flush=True);return False
        sel=process.ReadPointerFromMemory(vb+0x2bfaae00,err)
        if not err.Success() or not sel:print('KM_TRACE_ARM_FAIL selector_pointer',flush=True);return False
        name=process.ReadCStringFromMemory(sel,128,err)
        if not err.Success() or name!='countByEnumeratingWithState:objects:count:':print('KM_TRACE_ARM_FAIL selector',flush=True);return False
        dispatch=process.ReadPointerFromMemory(vb+0x2a6c2080,err);resolved=target.ResolveLoadAddress(dispatch)
        symbol=resolved.GetSymbol();mod=resolved.GetModule()
        if not err.Success() or not resolved.IsValid() or not symbol.IsValid() or not mod.IsValid() or mod.GetFileSpec().GetFilename()!='libobjc.A.dylib' or symbol.GetName() not in ('objc_msgSend','_objc_msgSend') or symbol.GetStartAddress().GetLoadAddress(target)!=dispatch:
            print('KM_TRACE_ARM_FAIL dispatch',flush=True);return False
        creator=process.ReadPointerFromMemory(vb+0x2a681930,err);addr=target.ResolveLoadAddress(creator);symbol=addr.GetSymbol();mod=addr.GetModule()
        if not err.Success() or not addr.IsValid() or not symbol.IsValid() or not mod.IsValid() or mod.GetFileSpec().GetFilename()!='CoreFoundation' or symbol.GetName() not in ('CFDictionaryCreateMutable','_CFDictionaryCreateMutable') or symbol.GetStartAddress().GetLoadAddress(target)!=creator:
            print('KM_TRACE_ARM_FAIL dictionary_creator',flush=True);return False
        for offset,expected in ((0x2bfa3df8,b'RegistryID'),(0x2bfa3f58,b'IORegistryName'),(0x2bfa3f98,b'IGPU')):
            raw=process.ReadMemory(vb+offset,32,err)
            if not err.Success() or len(raw)!=32:print('KM_TRACE_ARM_FAIL key_object',flush=True);return False
            isa,flags,chars,length=struct.unpack('<QQQQ',raw)
            if not isa or flags!=0x7c8 or length!=len(expected):print('KM_TRACE_ARM_FAIL key_shape',flush=True);return False
            text=process.ReadMemory(chars,length,err)
            if not err.Success() or text!=expected:print('KM_TRACE_ARM_FAIL key_value',flush=True);return False
        COMPARE_KEY=vb+0x2bfa3f98
        for offset,image,name in ((0x2a681970,'CoreFoundation','CFDictionaryGetValue'),(0x2a689330,'CoreMedia','FigCFEqual')):
            pointer=process.ReadPointerFromMemory(vb+offset,err);resolved=target.ResolveLoadAddress(pointer);symbol=resolved.GetSymbol();mod=resolved.GetModule()
            if not err.Success() or not resolved.IsValid() or not symbol.IsValid() or not mod.IsValid() or mod.GetFileSpec().GetFilename()!=image or symbol.GetName() not in (name,'_'+name) or symbol.GetStartAddress().GetLoadAddress(target)!=pointer:
                print('KM_TRACE_ARM_FAIL lookup_target',flush=True);return False
        IVAR_REF=mb+0x238180
        addresses=[mb+0x1d37,vb+0x5fd9fb,vb+0x5fda32,vb+0x5fda85,vb+0x5fda8a,vb+0x5feade,vb+0x5fdaa1,vb+0x5fdab3,vb+0x5fdad7,vb+0x5fdadc,vb+0x5fdb1b,vb+0x5fdb27,vb+0x5fdb4e,vb+0x5fdb35]
    EXTRAS['filter_input']=addresses[3];EXTRAS['filter_output']=addresses[4];EXTRAS['dict_alloc']=addresses[5];EXTRAS['key_registry']=addresses[6];EXTRAS['key_name']=addresses[7];EXTRAS['compare_input']=addresses[8];EXTRAS['compare_output']=addresses[9];EXTRAS['next_batch']=addresses[10];EXTRAS['branch_test']=addresses[11];EXTRAS['path_zero']=addresses[12];EXTRAS['path_nonzero']=addresses[13]
    for name,address in zip(('device','list','batch'),addresses[:3]):
        err=lldb.SBError();original=process.ReadMemory(address,8,err)
        if not err.Success() or len(original)!=8:print('KM_TRACE_ARM_FAIL bytes',flush=True);return False
        response=lldb.SBCommandReturnObject();target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint set -H -G true -a 0x%x -N km_%s'%(address,name),response)
        if not response.Succeeded():print('KM_TRACE_ARM_FAIL breakpoint',flush=True);return False
        bp=target.GetBreakpointAtIndex(target.GetNumBreakpoints()-1);response=lldb.SBCommandReturnObject()
        target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint command add -F lldb_witness.hit %d'%bp.GetID(),response)
        if not response.Succeeded():print('KM_TRACE_ARM_FAIL callback',flush=True);return False
        POINTS[bp.GetID()]=(name,address,original)
    print('KM_TRACE_ARM_PASS mode='+mode,flush=True);return False

def add_extra(process,name):
    target=process.GetTarget();address=EXTRAS[name];err=lldb.SBError();original=process.ReadMemory(address,8,err)
    if not err.Success() or len(original)!=8:print('KM_TRACE_HIT_FAIL extra_bytes',flush=True);return
    response=lldb.SBCommandReturnObject();target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint set -H -G true -a 0x%x -N km_%s'%(address,name),response)
    if not response.Succeeded():print('KM_TRACE_HIT_FAIL extra_breakpoint',flush=True);return
    bp=target.GetBreakpointAtIndex(target.GetNumBreakpoints()-1);response=lldb.SBCommandReturnObject()
    target.GetDebugger().GetCommandInterpreter().HandleCommand('breakpoint command add -F lldb_witness.hit %d'%bp.GetID(),response)
    if not response.Succeeded():print('KM_TRACE_HIT_FAIL extra_callback',flush=True);return
    POINTS[bp.GetID()]=(name,address,original)

def hit(frame,bp_loc,internal_dict):
    del internal_dict
    item=POINTS.get(bp_loc.GetBreakpoint().GetID())
    if not item:print('KM_TRACE_HIT_FAIL unknown',flush=True);return False
    name,address,original=item;thread=frame.GetThread();process=thread.GetProcess();error=lldb.SBError();current=process.ReadMemory(address,8,error);reg=frame.FindRegister('rax');tid=thread.GetThreadID()
    if not reg.IsValid() or not error.Success() or current!=original:print('KM_TRACE_HIT_FAIL bytes_or_register',flush=True);return False
    value=reg.GetValueAsUnsigned()
    if name=='device':
        offset=process.ReadUnsignedFromMemory(IVAR_REF,8,error) if IVAR_REF else IVAR
        if not error.Success() or (IVAR_REF and offset!=0xd3d8):print('KM_TRACE_HIT_FAIL ivar',flush=True);return False
        ptr=frame.FindRegister('r14').GetValueAsUnsigned(0);registry=process.ReadUnsignedFromMemory(ptr+offset,8,error) if ptr else 0
        if not ptr or not error.Success() or (value&0xffffffff)!=0:print('KM_TRACE_HIT_FAIL device_read',flush=True);return False
        match=int(registry==RID)
        if match:DEVICE[tid]=ptr
        print('KM_TRACE_DEVICE thread=%d target_match=%d bytes_match=1'%(tid,match),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'filter_input')
    elif name=='list':
        LIST[tid]=value;print('KM_TRACE_LIST thread=%d nonnull=%d bytes_match=1'%(tid,int(value!=0)),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'filter_output')
    elif name=='filter_input':
        arg=frame.FindRegister('rdi').GetValueAsUnsigned(0);match=int(tid in DEVICE and arg==DEVICE[tid]);FILTER[tid]=match
        print('KM_TRACE_FILTER_INPUT thread=%d device_match=%d bytes_match=1'%(tid,match),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'dict_alloc')
    elif name=='dict_alloc':
        DICT[tid]=value;print('KM_TRACE_DICT_ALLOC thread=%d nonnull=%d bytes_match=1'%(tid,int(value!=0)),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'key_registry')
    elif name=='filter_output':
        same_alloc=int(tid in DICT and DICT[tid]==value)
        print('KM_TRACE_FILTER_OUTPUT thread=%d input_match=%d nonnull=%d same_alloc=%d bytes_match=1'%(tid,FILTER.get(tid,-1),int(value!=0),same_alloc),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'key_name')
    elif name in ('key_registry','key_name'):
        current_dict=frame.FindRegister('r15').GetValueAsUnsigned(0);same=int(tid in DICT and DICT[tid]==current_dict)
        if name=='key_registry':
            print('KM_TRACE_KEY_REG thread=%d nonnull=%d same_dict=%d bytes_match=1'%(tid,int(value!=0),same),flush=True)
            bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'compare_input')
        else:
            NAME[tid]=value;print('KM_TRACE_KEY_NAME thread=%d nonnull=%d same_dict=%d bytes_match=1'%(tid,int(value!=0),same),flush=True)
            bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'compare_output')
    elif name=='compare_input':
        arg=frame.FindRegister('rdi').GetValueAsUnsigned(0);key=frame.FindRegister('rsi').GetValueAsUnsigned(0)
        match=int(tid in NAME and NAME[tid]==arg);key_match=int(key==COMPARE_KEY);CMP[tid]=match and key_match
        print('KM_TRACE_COMPARE_INPUT thread=%d name_match=%d key_match=%d bytes_match=1'%(tid,match,key_match),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'next_batch')
    elif name=='compare_output':
        RESULT[tid]=value&0xff
        print('KM_TRACE_COMPARE_RESULT thread=%d same_input=%d equal=%d bytes_match=1'%(tid,int(CMP.get(tid,False)),value&0xff),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'branch_test')
    elif name=='next_batch':
        reg12=frame.FindRegister('r12');same=int(reg12.IsValid() and tid in LIST and reg12.GetValueAsUnsigned()==LIST[tid])
        print('KM_TRACE_NEXT_BATCH thread=%d count=%d same_list=%d bytes_match=1'%(tid,value,same),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'path_zero')
    elif name=='branch_test':
        bl=frame.FindRegister('bl');flag=bl.GetValueAsUnsigned(256) if bl.IsValid() else 256
        print('KM_TRACE_BRANCH thread=%d flag=%d same_compare=%d bytes_match=1'%(tid,flag,int(tid in RESULT and RESULT[tid]==flag)),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'path_nonzero')
    elif name in ('path_zero','path_nonzero'):
        print('KM_TRACE_PATH thread=%d choice=%s bytes_match=1'%(tid,'zero' if name=='path_zero' else 'nonzero'),flush=True)
    else:
        reg12=frame.FindRegister('r12');same=reg12.IsValid() and tid in LIST and reg12.GetValueAsUnsigned()==LIST[tid];item_match=-1
        if value:
            rbp=frame.FindRegister('rbp').GetValueAsUnsigned(0);items=process.ReadPointerFromMemory(rbp-0x198,error) if rbp else 0
            if not error.Success() or not items or value>16:print('KM_TRACE_HIT_FAIL items',flush=True);return False
            first=process.ReadPointerFromMemory(items,error)
            if not error.Success() or not first:print('KM_TRACE_HIT_FAIL first',flush=True);return False
            item_match=int(tid in DEVICE and first==DEVICE[tid])
        print('KM_TRACE_BATCH thread=%d count=%d same_list=%d item_match=%d bytes_match=1'%(tid,value,int(same),item_match),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False)
    return False
