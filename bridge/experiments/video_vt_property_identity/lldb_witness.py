# SPDX-License-Identifier: MIT
"""Observe natural device/list identity with bounded reads and hardware breakpoints."""
import hashlib,os,struct,lldb
POINTS={};LIST={};DEVICE={};FILTER={};DICT={};REGISTRY={};NAME={};SET={};DEST={};CALLBACK={};APPLY_CONTEXT={};APPLY_FRAME={};CALLBACK_SP={};CONTEXT={};AVAIL={};APPEND={};OUTPUT_SLOT={};CALLER_FRAME={};COUNT={};ITEM={};FILTER_CALL={};REQUEST={};REASON_FRAME={};CMP={};RESULT={};EXTRAS={};EXTRA_IDS={};RID=0;IVAR=0;IVAR_REF=0;COMPARE_KEY=0;FIRST_KEY=0
def arm(frame,bp_loc,internal_dict):
    global RID,IVAR,IVAR_REF,COMPARE_KEY,FIRST_KEY
    del bp_loc,internal_dict
    process=frame.GetThread().GetProcess();target=process.GetTarget();mode=os.environ.get('KM_TRACE_MODE')
    RID=frame.FindRegister('rsi').GetValueAsUnsigned(0)
    if frame.FindRegister('rdi').GetValueAsUnsigned()!=0xabc0 or not RID or mode not in ('cpu','video'):
        print('KM_TRACE_ARM_FAIL marker',flush=True);return False
    if mode=='cpu':
        addresses=[];IVAR=0
        for name in ('KMAfterRegistry','KMAfterList','KMAfterBatch','KMBeforeFilter','KMAfterFilter','KMAfterDict','KMAfterReg','KMAfterName','KMBeforeCompare','KMAfterCompare','KMAfterNext','KMBranchTest','KMPathZero','KMPathNonzero','KMBeforeSet','KMAfterSet','KMBeforeApply','KMCallbackEntry','KMAfterAvailable','KMBeforeAppend','KMAfterAppend','KMBeforeOutStore','KMAfterOutStore','KMBeforeCount','KMAfterCount','KMBeforeItem','KMAfterItem','KMBeforeRequestFilter','KMAfterRequestFilter','KMFirstInput','KMFirstResult','KMSecondResult','KMAbsentResult','KMContainsResult','KMServiceResult','KMPropertyResult','KMPropertyInput'):
            contexts=target.FindSymbols(name,lldb.eSymbolTypeAny)
            if contexts.GetSize()!=1:print('KM_TRACE_ARM_FAIL symbol',flush=True);return False
            addresses.append(contexts.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(target))
        symbols=target.FindSymbols('KMIGPU',lldb.eSymbolTypeAny)
        if symbols.GetSize()!=1:print('KM_TRACE_ARM_FAIL cpu_key',flush=True);return False
        COMPARE_KEY=symbols.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(target)
        symbols=target.FindSymbols('KMFirstKey',lldb.eSymbolTypeAny)
        if symbols.GetSize()!=1:print('KM_TRACE_ARM_FAIL first_key',flush=True);return False
        FIRST_KEY=symbols.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(target)
    else:
        def module(name,uuid):
            matches=[m for m in target.module_iter() if m.GetFileSpec().GetFilename()==name]
            return matches[0] if len(matches)==1 and (matches[0].GetUUIDString() or '').replace('-','').lower()==uuid else None
        vt=module('VideoToolbox','e7231bea63883d0a95c0a93ce970b96b');metal=module('MetalOld.dylib','6581cd53858338d1b4b9773f1dc3f551')
        if not vt or not metal:print('KM_TRACE_ARM_FAIL image',flush=True);return False
        vb=vt.GetObjectFileHeaderAddress().GetLoadAddress(target);mb=metal.GetObjectFileHeaderAddress().GetLoadAddress(target);err=lldb.SBError()
        for address,size,digest in ((vb+0x5fe6bb,520,'c4386b358bb7cfbf8eb38bb9817d194d249368f942a629792fc14386ff6643e4'),(vb+0x3f83,332,'ae2dd856fb1ca2bb409ab0e69f8c563f6e62cde57dc575e05b4d95347a29d929'),(vb+0x5fd95f,3420,'f38fc93a01c9f5c715b94b5a2fe6a45c7ebccba26cdd0cedcadb06b7ffe9478b'),(mb+0x1cbe,132,'f2df1f2af9af40e440eb1b78a4010bdbf6f4eaa4618a2d19322c5e4026f7a7fe'),(vb+0x5fea84,867,'b2b4a259e7b62af742beec8c6b6acbf8351443fc7edc0defe9ecd8ef6d2c1dad'),(vb+0x40cf,154,'bef27ed109c537af88849bbedf170d42048feba3bc6c0a4b750dec5e20733ce5'),(vb+0x228067,70,'ca8343199d316f1656a627acfc35197159982343bcf4bf3a2e416094fc4d0b79')):
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
        for offset,expected in ((0x2bfa3df8,b'RegistryID'),(0x2bfa3f58,b'IORegistryName'),(0x2bfa3f98,b'IGPU'),(0x2bfa3ef8,b'Available'),(0x2bfa3f18,b'PresentIORegKeysAndValues'),(0x2bfa3f38,b'AbsentIORegKeys'),(0x2bfa3dd8,b'Service')):
            raw=process.ReadMemory(vb+offset,32,err)
            if not err.Success() or len(raw)!=32:print('KM_TRACE_ARM_FAIL key_object',flush=True);return False
            isa,flags,chars,length=struct.unpack('<QQQQ',raw)
            if not isa or flags!=0x7c8 or length!=len(expected):print('KM_TRACE_ARM_FAIL key_shape',flush=True);return False
            text=process.ReadMemory(chars,length,err)
            if not err.Success() or text!=expected:print('KM_TRACE_ARM_FAIL key_value',flush=True);return False
        COMPARE_KEY=vb+0x2bfa3f98;FIRST_KEY=vb+0x2bfa3f18
        for offset,image,name in ((0x2a681970,'CoreFoundation','CFDictionaryGetValue'),(0x2a689330,'CoreMedia','FigCFEqual'),(0x2a6819a8,'CoreFoundation','CFDictionarySetValue'),(0x2a6818f8,'CoreFoundation','CFDictionaryApplyFunction'),(0x2a6891b0,'CoreMedia','FigCFDictionaryGetBooleanIfPresent'),(0x2a6811b8,'CoreFoundation','CFArrayAppendValue'),(0x2a689238,'CoreMedia','FigCFDictionaryGetInt64IfPresent'),(0x2a696648,'IOKit','IORegistryEntrySearchCFProperty')):
            pointer=process.ReadPointerFromMemory(vb+offset,err);resolved=target.ResolveLoadAddress(pointer);symbol=resolved.GetSymbol();mod=resolved.GetModule()
            if not err.Success() or not resolved.IsValid() or not symbol.IsValid() or not mod.IsValid() or mod.GetFileSpec().GetFilename()!=image or symbol.GetName() not in (name,'_'+name) or symbol.GetStartAddress().GetLoadAddress(target)!=pointer:
                print('KM_TRACE_ARM_FAIL lookup_target',flush=True);return False
        IVAR_REF=mb+0x238180
        addresses=[mb+0x1d37,vb+0x5fd9fb,vb+0x5fda32,vb+0x5fda85,vb+0x5fda8a,vb+0x5feade,vb+0x5fdaa1,vb+0x5fdab3,vb+0x5fdad7,vb+0x5fdadc,vb+0x5fdb1b,vb+0x5fdb27,vb+0x5fdb4e,vb+0x5fdb35,vb+0x5fdac8,vb+0x5fdacd,vb+0x4133,vb+0x228067,vb+0x228091,vb+0x22809d,vb+0x2280a2,vb+0x4152,vb+0x4155,vb+0x4022,vb+0x4027,vb+0x4038,vb+0x403d,vb+0x4049,vb+0x404e,vb+0x5fe6eb,vb+0x5fe6f0,vb+0x5fe703,vb+0x5fe725,vb+0x5fe74d,vb+0x5fe775,vb+0x5fe7a1,vb+0x5fe79c]
    EXTRAS['filter_input']=addresses[3];EXTRAS['filter_output']=addresses[4];EXTRAS['dict_alloc']=addresses[5];EXTRAS['key_registry']=addresses[6];EXTRAS['key_name']=addresses[7];EXTRAS['compare_input']=addresses[8];EXTRAS['compare_output']=addresses[9];EXTRAS['next_batch']=addresses[10];EXTRAS['branch_test']=addresses[11];EXTRAS['path_zero']=addresses[12];EXTRAS['path_nonzero']=addresses[13];EXTRAS['set_input']=addresses[14];EXTRAS['set_return']=addresses[15];EXTRAS['apply_input']=addresses[16];EXTRAS['callback_entry']=addresses[17];EXTRAS['available_return']=addresses[18];EXTRAS['append_input']=addresses[19];EXTRAS['append_return']=addresses[20];EXTRAS['out_store']=addresses[21];EXTRAS['out_after']=addresses[22];EXTRAS['count_input']=addresses[23];EXTRAS['count_output']=addresses[24];EXTRAS['item_input']=addresses[25];EXTRAS['item_output']=addresses[26];EXTRAS['request_input']=addresses[27];EXTRAS['request_output']=addresses[28];EXTRAS['reason_input']=addresses[29];EXTRAS['reason_first']=addresses[30];EXTRAS['reason_second']=addresses[31];EXTRAS['reason_absent']=addresses[32];EXTRAS['reason_contains']=addresses[33];EXTRAS['reason_service']=addresses[34];EXTRAS['reason_property']=addresses[35];EXTRAS['property_input']=addresses[36]
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
    POINTS[bp.GetID()]=(name,address,original);EXTRA_IDS[name]=bp.GetID()

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
            REGISTRY[tid]=value;print('KM_TRACE_KEY_REG thread=%d nonnull=%d same_dict=%d bytes_match=1'%(tid,int(value!=0),same),flush=True)
            bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'set_input')
        else:
            NAME[tid]=value;print('KM_TRACE_KEY_NAME thread=%d nonnull=%d same_dict=%d bytes_match=1'%(tid,int(value!=0),same),flush=True)
            bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'set_return')
    elif name=='set_input':
        dest=frame.FindRegister('rdi').GetValueAsUnsigned(0);key=frame.FindRegister('rsi').GetValueAsUnsigned(0);data=frame.FindRegister('rdx').GetValueAsUnsigned(0)
        dest_ok=int(dest!=0 and tid in DICT and dest!=DICT[tid]);key_ok=int(tid in REGISTRY and key==REGISTRY[tid] and key!=0);value_ok=int(tid in DICT and data==DICT[tid] and data!=0)
        SET[tid]=bool(dest_ok and key_ok and value_ok);DEST[tid]=dest
        print('KM_TRACE_SET_INPUT thread=%d distinct_destination=%d key_match=%d value_match=%d bytes_match=1'%(tid,dest_ok,key_ok,value_ok),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'compare_input')
    elif name=='set_return':
        print('KM_TRACE_SET_RETURN thread=%d input_match=%d bytes_match=1'%(tid,int(SET.get(tid,False))),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'compare_output');add_extra(process,'apply_input')
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
        bp_loc.GetBreakpoint().SetEnabled(False);other='path_nonzero' if name=='path_zero' else 'path_zero';other_bp=process.GetTarget().FindBreakpointByID(EXTRA_IDS.get(other,0))
        if other_bp.IsValid():other_bp.SetEnabled(False)
        add_extra(process,'callback_entry')
    elif name=='apply_input':
        dest=frame.FindRegister('rdi').GetValueAsUnsigned(0);callback=frame.FindRegister('rsi').GetValueAsUnsigned(0);context=frame.FindRegister('rdx').GetValueAsUnsigned(0)
        ok=int(tid in DEST and dest==DEST[tid] and callback==EXTRAS['callback_entry'] and context!=0)
        if ok:APPLY_CONTEXT[tid]=context;APPLY_FRAME[tid]=frame.FindRegister('rbp').GetValueAsUnsigned(0)
        print('KM_TRACE_APPLY thread=%d dest_callback_context_match=%d bytes_match=1'%(tid,ok),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'available_return')
    elif name=='callback_entry':
        key=frame.FindRegister('rdi').GetValueAsUnsigned(0);data=frame.FindRegister('rsi').GetValueAsUnsigned(0);context=frame.FindRegister('rdx').GetValueAsUnsigned(0)
        km=int(tid in REGISTRY and key==REGISTRY[tid] and key!=0);vm=int(tid in DICT and data==DICT[tid] and data!=0)
        cm=int(tid in APPLY_CONTEXT and context==APPLY_CONTEXT[tid]);print('KM_TRACE_CALLBACK thread=%d key_match=%d value_match=%d context_match=%d bytes_match=1'%(tid,km,vm,cm),flush=True)
        CALLBACK[tid]=bool(km and vm and cm)
        if CALLBACK[tid]:
            CONTEXT[tid]=context;CALLBACK_SP[tid]=frame.GetSP();bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'append_input')
    elif name=='available_return':
        if CALLBACK.get(tid,False) and tid in CALLBACK_SP and frame.FindRegister('rbp').GetValueAsUnsigned(0)==CALLBACK_SP[tid]-8:
            p=frame.FindRegister('r15').GetValueAsUnsigned(0);raw=process.ReadMemory(p,1,error) if p else b''
            if not error.Success() or len(raw)!=1 or raw[0] not in (0,1):print('KM_TRACE_HIT_FAIL available',flush=True);return False
            AVAIL[tid]=raw[0];print('KM_TRACE_AVAILABLE thread=%d value=%d bytes_match=1'%(tid,raw[0]),flush=True)
            bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'append_return')
    elif name=='append_input':
        dest=frame.FindRegister('rdi').GetValueAsUnsigned(0);data=frame.FindRegister('rsi').GetValueAsUnsigned(0)
        ok=int(tid in CONTEXT and dest==CONTEXT[tid] and tid in DICT and data==DICT[tid] and tid in CALLBACK_SP and frame.FindRegister('rbp').GetValueAsUnsigned(0)==CALLBACK_SP[tid]-8)
        if ok:
            APPEND[tid]=True;print('KM_TRACE_APPEND_INPUT thread=%d context_value_match=1 bytes_match=1'%tid,flush=True);bp_loc.GetBreakpoint().SetEnabled(False)
        else:print('KM_TRACE_APPEND_OTHER_INPUT thread=%d bytes_match=1'%tid,flush=True)
    elif name=='append_return':
        if APPEND.pop(tid,False) and tid in CALLBACK_SP and frame.FindRegister('rbp').GetValueAsUnsigned(0)==CALLBACK_SP[tid]-8:
            print('KM_TRACE_APPEND_RETURN thread=%d available=%d bytes_match=1'%(tid,AVAIL.get(tid,-1)),flush=True);bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'out_store')
        else:print('KM_TRACE_APPEND_OTHER_RETURN thread=%d bytes_match=1'%tid,flush=True)
    elif name=='out_store':
        array=frame.FindRegister('r12').GetValueAsUnsigned(0);slot=frame.FindRegister('rbx').GetValueAsUnsigned(0);fp=frame.FindRegister('rbp').GetValueAsUnsigned(0)
        same_frame=int(tid in APPLY_FRAME and fp==APPLY_FRAME[tid]);same_array=int(tid in APPLY_CONTEXT and array==APPLY_CONTEXT[tid]);OUTPUT_SLOT[tid]=slot
        print('KM_TRACE_OUT_STORE thread=%d same_frame=%d same_array=%d slot_nonnull=%d bytes_match=1'%(tid,same_frame,same_array,int(slot!=0)),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'out_after')
    elif name=='out_after':
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);slot=OUTPUT_SLOT.get(tid,0);stored=process.ReadPointerFromMemory(slot,error) if slot else 0
        if not error.Success() or not slot:print('KM_TRACE_HIT_FAIL out_slot',flush=True);return False
        same_frame=int(tid in APPLY_FRAME and fp==APPLY_FRAME[tid]);same_array=int(tid in APPLY_CONTEXT and stored==APPLY_CONTEXT[tid]);status=frame.FindRegister('r15d').GetValueAsUnsigned(0)&0xffffffff
        if status>=0x80000000:status-=0x100000000
        parent=thread.GetFrameAtIndex(1);addr=parent.GetPCAddress() if parent.IsValid() else lldb.SBAddress();mod=addr.GetModule() if addr.IsValid() else lldb.SBModule()
        image=mod.GetFileSpec().GetFilename() if mod.IsValid() else 'unknown';base=mod.GetObjectFileHeaderAddress().GetLoadAddress(process.GetTarget()) if mod.IsValid() else 0
        pc=parent.GetPC() if parent.IsValid() else 0;offset=pc-base if base and pc>=base else 0
        print('KM_TRACE_OUT_AFTER thread=%d same_frame=%d stored_array_match=%d status=%d parent_image=%s parent_offset=%d bytes_match=1'%(tid,same_frame,same_array,status,image,offset),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False)
        if same_frame and same_array and status==0:
            CALLER_FRAME[tid]=fp if os.environ.get('KM_TRACE_MODE')=='cpu' else parent.FindRegister('rbp').GetValueAsUnsigned(0)
            add_extra(process,'count_input')
    elif name=='count_input':
        array=frame.FindRegister('rdi').GetValueAsUnsigned(0);fp=frame.FindRegister('rbp').GetValueAsUnsigned(0)
        same=int(tid in APPLY_CONTEXT and array==APPLY_CONTEXT[tid]);same_frame=int(tid in CALLER_FRAME and fp==CALLER_FRAME[tid])
        print('KM_TRACE_COUNT_INPUT thread=%d same_array=%d same_caller_frame=%d bytes_match=1'%(tid,same,same_frame),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'count_output')
    elif name=='count_output':
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);same_frame=int(tid in CALLER_FRAME and fp==CALLER_FRAME[tid]);COUNT[tid]=value
        print('KM_TRACE_COUNT_OUTPUT thread=%d count=%d same_caller_frame=%d bytes_match=1'%(tid,value,same_frame),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False)
        if value>0 and value<=16:add_extra(process,'item_input')
    elif name=='item_input':
        array=frame.FindRegister('rdi').GetValueAsUnsigned(0);index=frame.FindRegister('rsi').GetValueAsUnsigned(0);fp=frame.FindRegister('rbp').GetValueAsUnsigned(0)
        same=int(tid in APPLY_CONTEXT and array==APPLY_CONTEXT[tid]);same_frame=int(tid in CALLER_FRAME and fp==CALLER_FRAME[tid])
        print('KM_TRACE_ITEM_INPUT thread=%d same_array=%d index=%d same_caller_frame=%d bytes_match=1'%(tid,same,index,same_frame),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'item_output')
    elif name=='item_output':
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);same_frame=int(tid in CALLER_FRAME and fp==CALLER_FRAME[tid]);match=int(tid in DICT and value==DICT[tid] and value!=0);ITEM[tid]=value
        print('KM_TRACE_ITEM_OUTPUT thread=%d gtx_entry_match=%d same_caller_frame=%d bytes_match=1'%(tid,match,same_frame),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'request_input')
    elif name=='request_input':
        item=frame.FindRegister('rdi').GetValueAsUnsigned(0);request=frame.FindRegister('rsi').GetValueAsUnsigned(0);third=frame.FindRegister('rdx').GetValueAsUnsigned(1);fp=frame.FindRegister('rbp').GetValueAsUnsigned(0)
        item_match=int(tid in ITEM and item==ITEM[tid] and item!=0);gtx_match=int(tid in DICT and item==DICT[tid] and item!=0);same_frame=int(tid in CALLER_FRAME and fp==CALLER_FRAME[tid]);FILTER_CALL[tid]=bool(item_match and same_frame)
        print('KM_TRACE_REQUEST_INPUT thread=%d item_match=%d gtx_entry_match=%d request_nonnull=%d third_zero=%d same_caller_frame=%d bytes_match=1'%(tid,item_match,gtx_match,int(request!=0),int(third==0),same_frame),flush=True)
        REQUEST[tid]=request
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'request_output')
        if item_match and gtx_match and same_frame and request and third==0:add_extra(process,'reason_input')
    elif name=='reason_input':
        parent=thread.GetFrameAtIndex(1);parentfp=parent.FindRegister('rbp').GetValueAsUnsigned(0) if parent.IsValid() else 0
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);item=frame.FindRegister('rdi').GetValueAsUnsigned(0);key=frame.FindRegister('rsi').GetValueAsUnsigned(0);req=frame.FindRegister('r15').GetValueAsUnsigned(0)
        parent_match=int(tid in CALLER_FRAME and parentfp==CALLER_FRAME[tid]);entry_match=int(tid in DICT and item==DICT[tid]);key_match=int(key==FIRST_KEY and key!=0);request_match=int(tid in REQUEST and req==REQUEST[tid]);REASON_FRAME[tid]=fp
        print('KM_TRACE_REASON_INPUT thread=%d parent_match=%d entry_match=%d key_match=%d request_match=%d bytes_match=1'%(tid,parent_match,entry_match,key_match,request_match),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'reason_first')
    elif name in ('reason_first','reason_second','reason_absent','reason_contains','reason_service','reason_property'):
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);same_frame=int(tid in REASON_FRAME and fp==REASON_FRAME[tid]);nonzero=int((value&255)!=0) if name in ('reason_contains','reason_service') else int(value!=0)
        print('KM_TRACE_REASON_RESULT thread=%d kind=%s nonzero=%d same_filter_frame=%d bytes_match=1'%(tid,name[7:],nonzero,same_frame),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False)
        next_name={'reason_first':('reason_second' if nonzero else 'reason_absent'),'reason_second':('' if nonzero else 'reason_absent'),'reason_absent':('reason_contains' if nonzero else 'reason_service'),'reason_contains':('' if nonzero else 'reason_service'),'reason_service':('property_input' if nonzero else ''),'reason_property':''}[name]
        if next_name:add_extra(process,next_name)
    elif name=='property_input':
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);service=frame.FindRegister('rdi').GetValueAsUnsigned(0)&0xffffffff;plane=frame.FindRegister('rsi').GetValueAsUnsigned(0);key=frame.FindRegister('rdx').GetValueAsUnsigned(0);options=frame.FindRegister('r8').GetValueAsUnsigned(0)
        same_frame=int(tid in REASON_FRAME and fp==REASON_FRAME[tid]);request_match=int(tid in REQUEST and key==REQUEST[tid]);err=lldb.SBError();plane_text=process.ReadCStringFromMemory(plane,32,err) if plane else '';plane_ok=int(err.Success() and plane_text=='IOService')
        err=lldb.SBError();obj=process.ReadMemory(key,32,err) if key else b'';identity='unknown';shape=0
        if err.Success() and len(obj)==32:
            isa,flags,chars,length=struct.unpack('<QQQQ',obj)
            if isa and flags==0x7c8 and chars and 0<length<=96:
                err=lldb.SBError();raw=process.ReadMemory(chars,length,err)
                if err.Success() and len(raw)==length and all(32<=c<127 for c in raw):
                    shape=1;known=(b'IOGVACodec',b'IOAVDHEVCDecodeCapabilities',b'IOVARendererID',b'IODVDBundleName')
                    identity=raw.decode('ascii') if raw in known else 'other'
        print('KM_TRACE_PROPERTY_INPUT thread=%d same_filter_frame=%d request_match=%d service_nonzero=%d plane_ioservice=%d options=%d constant_shape=%d key=%s bytes_match=1'%(tid,same_frame,request_match,int(service!=0),plane_ok,options,shape,identity),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False);add_extra(process,'reason_property')
    elif name=='request_output':
        fp=frame.FindRegister('rbp').GetValueAsUnsigned(0);same_frame=int(tid in CALLER_FRAME and fp==CALLER_FRAME[tid])
        print('KM_TRACE_REQUEST_OUTPUT thread=%d input_matched=%d return_byte=%d same_caller_frame=%d bytes_match=1'%(tid,int(FILTER_CALL.get(tid,False)),value&255,same_frame),flush=True)
        bp_loc.GetBreakpoint().SetEnabled(False)
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
