#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit CPU calibration and reserved public VideoToolbox witness runs."""
import argparse,datetime,hashlib,json,platform,re,subprocess,sys,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from inspect_video_cache import Cache,image_map,inspect,stub_symbol
from experiment import SOURCE,SYSTEM,REFERENCE,EXPECTED,sha

def need(v,message):
    if not v:raise ValueError(message)
def main():
    p=argparse.ArgumentParser()
    for n in ('build','calibration','cache','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=8,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    b=json.loads((a.build/'build.json').read_text());c=json.loads((a.calibration/'calibration.json').read_text())
    need(c['status']=='PASS_CPU_ENUMERATION_WITNESS' and c['one_and_zero_verified'] and c['wrong_marker_refused'] and c['wrong_target_rejected'] and c['null_result_verified'] and c['allocation_identity_verified'] and c['equal_and_different_verified'] and c['both_branch_paths_verified'] and c['wrong_key_and_value_verified'] and c['available_and_unavailable_verified'] and c['other_entry_not_attributed'] and c['wrong_output_rejected'] and c['wrong_item_and_filter_rejection_verified'] and c['reason_branch_controls_verified'] and c['property_identity_controls_verified'] and c['wrong_service_control_verified'] and c['wrong_retained_service_control_verified'] and c['calibrator_sha256']==sha(HERE/'calibrate.py') and
        all(sha(a.calibration/n)==h for n,h in c['sources'].items()) and sha(a.calibration/'host')==c['host_sha256'] and subprocess.run(['codesign','--verify','--strict',str(a.calibration/'host')],capture_output=True).returncode==0 and
        all(sha(a.calibration/(n+'.log'))==h for n,h in c['logs'].items()),'calibration differs')
    need(b['status']=='PREPARED' and b['calibration_sha256']==sha(a.calibration/'calibration.json') and
         b['builder_sha256']==sha(HERE/'experiment.py') and b['source_sha256']=={n:sha(v) for n,v in SOURCE.items()} and
         b['build_sha256']=={n:sha(a.build/n) for n in ('client','observer.dylib')} and
         b['fixture']==EXPECTED=={n:sha(a.build/'fixture'/n) for n in EXPECTED} and
         sha(a.build/'reference.nv12')==REFERENCE,'build differs')
    need({path:sha(path) for path in SYSTEM}==SYSTEM and platform.machine()=='x86_64','profile differs')
    image='/System/Library/Frameworks/VideoToolbox.framework/Versions/A/VideoToolbox';cache=Cache(a.cache.resolve())
    base=image_map(a.cache.with_name(a.cache.name+'.map'),image)[0]['start'];img,starts=inspect(cache,base,image)
    need(img['UUID']=='e7231bea63883d0a95c0a93ce970b96b' and base+0x5fd95f in starts and base+0x5fe6bb in starts and
         hashlib.sha256(cache.read(base+0x5fd95f,3420)).hexdigest()=='f38fc93a01c9f5c715b94b5a2fe6a45c7ebccba26cdd0cedcadb06b7ffe9478b', 'cache function differs')
    site=base+0x5fda85;call=cache.read(site,5);helper=base+0x5fea84
    need(call[0]==0xe8 and hashlib.sha256(call).hexdigest()=='4b690b4196f759c80e21fc8de5667323f2e440bfbc881e1e67aacf1535a3f2cc' and
         site+5+struct.unpack_from('<i',call,1)[0]==helper and helper in starts and
         hashlib.sha256(cache.read(helper,867)).hexdigest()=='b2b4a259e7b62af742beec8c6b6acbf8351443fc7edc0defe9ecd8ef6d2c1dad','helper static profile differs')
    create_site=base+0x5fead9;create_call=cache.read(create_site,5)
    need(create_call[0]==0xe8 and hashlib.sha256(create_call).hexdigest()=='646dc5ff7e3875f64cc2ec4a65b892c4bace2cf3c0df87a366d51aba8ea07a59','creation call differs')
    create_stub=create_site+5+struct.unpack_from('<i',create_call,1)[0]
    binding=stub_symbol(cache,img,create_stub)
    need(create_stub==base+0x646ae2 and binding and binding.get('static_symbol')=='_CFDictionaryCreateMutable','creation import differs')
    for site,offset,name in ((0x5fda95,0x2bfa3df8,b'RegistryID'),(0x5fdaa7,0x2bfa3f58,b'IORegistryName'),(0x5fdad0,0x2bfa3f98,b'IGPU')):
        lea=cache.read(base+site,7);need(lea[:3]==b'\x48\x8d\x35' and base+site+7+struct.unpack_from('<i',lea,3)[0]==base+offset,'key instruction differs')
        obj=cache.read(base+offset,32);_,flags,_,length=struct.unpack('<QQQQ',obj)
        need(flags==0x7c8 and length==len(name) and cache.read(cache.pointer_v2(base+offset+16),length)==name,'key constant differs')
    for site,expected in ((0x5fda9c,'_CFDictionaryGetValue'),(0x5fdaae,'_CFDictionaryGetValue'),(0x5fdad7,'_FigCFEqual')):
        instruction=cache.read(base+site,5);need(instruction[0]==0xe8,'key call differs')
        dest=base+site+5+struct.unpack_from('<i',instruction,1)[0];binding=stub_symbol(cache,img,dest)
        need(binding and binding.get('static_symbol')==expected,'key import differs')
    site=base+0x5fdac8;call=cache.read(site,5)
    need(call[0]==0xe8 and hashlib.sha256(call).hexdigest()=='85cfc348064db8b7c175862ed94c0afc95e49f8d59ebc7c74b5e67e57ae7b710','registration call differs')
    dest=site+5+struct.unpack_from('<i',call,1)[0];binding=stub_symbol(cache,img,dest)
    need(dest==base+0x646b1e and binding and binding.get('static_symbol')=='_CFDictionarySetValue','registration import differs')
    branch=cache.read(base+0x5fdb27,14)
    need(branch[:2]==b'\x84\xdb' and branch[12:14]==b'\x74\x19' and base+0x5fdb35+struct.unpack('b',branch[13:14])[0]==base+0x5fdb4e,'branch instructions differ')
    for off,size,digest in ((0x40cf,154,'bef27ed109c537af88849bbedf170d42048feba3bc6c0a4b750dec5e20733ce5'),(0x228067,70,'ca8343199d316f1656a627acfc35197159982343bcf4bf3a2e416094fc4d0b79')):
        need(base+off in starts and hashlib.sha256(cache.read(base+off,size)).hexdigest()==digest,'apply or callback static profile differs')
    lea=cache.read(base+0x4129,7);need(lea[:3]==b'\x48\x8d\x35' and base+0x4129+7+struct.unpack_from('<i',lea,3)[0]==base+0x228067,'callback binding differs')
    key=cache.read(base+0x2bfa3ef8,32);_,flags,_,length=struct.unpack('<QQQQ',key)
    need(flags==0x7c8 and length==9 and cache.read(cache.pointer_v2(base+0x2bfa3ef8+16),length)==b'Available','available key differs')
    for site,expected in ((0x4133,'_CFDictionaryApplyFunction'),(0x22808c,'_FigCFDictionaryGetBooleanIfPresent'),(0x22809d,'_CFArrayAppendValue')):
        op=cache.read(base+site,5);need(op[0]==0xe8,'apply path call differs')
        dest=base+site+5+struct.unpack_from('<i',op,1)[0];bound=stub_symbol(cache,img,dest)
        need(bound and bound.get('static_symbol')==expected,'apply path import differs')
    need(base+0x3f83 in starts and hashlib.sha256(cache.read(base+0x3f83,332)).hexdigest()=='ae2dd856fb1ca2bb409ab0e69f8c563f6e62cde57dc575e05b4d95347a29d929','caller region differs')
    need(base+0x5fe6bb in starts and hashlib.sha256(cache.read(base+0x5fe6bb,520)).hexdigest()=='c4386b358bb7cfbf8eb38bb9817d194d249368f942a629792fc14386ff6643e4','filter region differs')
    for offset,name in ((0x2bfa3f18,b'PresentIORegKeysAndValues'),(0x2bfa3f38,b'AbsentIORegKeys'),(0x2bfa3dd8,b'Service')):
        obj=cache.read(base+offset,32);_,flags,_,length=struct.unpack('<QQQQ',obj)
        need(flags==0x7c8 and length==len(name) and cache.read(cache.pointer_v2(base+offset+16),length)==name,'filter key constant differs')
    for site,offset in ((0x5fe6e4,0x2bfa3f18),(0x5fe716,0x2bfa3f38),(0x5fe762,0x2bfa3dd8)):
        lea=cache.read(base+site,7);need(lea[:3]==b'\x48\x8d\x35' and base+site+7+struct.unpack_from('<i',lea,3)[0]==base+offset,'filter key reference differs')
    for site,expected in ((0x4022,'_CFArrayGetCount'),(0x4038,'_CFArrayGetValueAtIndex')):
        op=cache.read(base+site,5);need(op[0]==0xe8,'caller array call differs')
        dest=base+site+5+struct.unpack_from('<i',op,1)[0];bound=stub_symbol(cache,img,dest)
        need(bound and bound.get('static_symbol')==expected,'caller array import differs')
    op=cache.read(base+0x4049,5);need(op[0]==0xe8 and base+0x404e+struct.unpack_from('<i',op,1)[0]==base+0x5fe6bb,'request filter target differs')
    for site,expected in ((0x5fe6eb,'_CFDictionaryGetValue'),(0x5fe6fe,'_CFDictionaryGetValue'),(0x5fe720,'_CFDictionaryGetValue'),(0x5fe748,'_CFArrayContainsValue'),(0x5fe770,'_FigCFDictionaryGetInt64IfPresent'),(0x5fe79c,'_IORegistryEntrySearchCFProperty')):
        op=cache.read(base+site,5);need(op[0]==0xe8,'filter call instruction differs')
        dest=base+site+5+struct.unpack_from('<i',op,1)[0];binding=stub_symbol(cache,img,dest)
        need(binding and binding.get('static_symbol')==expected,'filter call import differs')
    need(cache.read(base+0x64e75e,10)==b'IOService\0','property plane differs')
    metal=Path('/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib')
    need(sha(metal)=='fd1e8e07491819334a1b3e788f01bc0d4fef0229c1022cb2fc29031c5c5dc97e' and
         hashlib.sha256(metal.read_bytes()[0x1cbe:0x1d42]).hexdigest()=='f2df1f2af9af40e440eb1b78a4010bdbf6f4eaa4618a2d19322c5e4026f7a7fe','MetalOld file differs')
    dis=subprocess.check_output(['xcrun','llvm-objdump','-d','--start-address=0x1cbe','--stop-address=0x1d42','--x86-asm-syntax=intel',str(metal)],text=True,timeout=60)
    indirect=subprocess.check_output(['xcrun','llvm-objdump','--macho','--indirect-symbols',str(metal)],text=True,timeout=60)
    need(re.search(r'1cf3:.*mov\s+r14, rax',dis) and re.search(r'1d25:.*0x238180',dis) and
         re.search(r'1d32:.*call\s+0x14cfd0',dis) and re.search(r'1d37:',dis) and
         re.search(r'^0x000000000014cfd0\s+\d+\s+_IORegistryEntryGetRegistryEntryID$',indirect,re.M),
         'MetalOld registry flow differs')
    g=json.loads(subprocess.check_output(['system_profiler','SPDisplaysDataType','-json'],timeout=60))['SPDisplaysDataType']
    need(len(g)==1 and g[0].get('spdisplays_vendor')=='sppci_vendor_Nvidia' and g[0].get('spdisplays_device-id')=='0x1198' and g[0].get('spdisplays_vram')=='8 GB','gpu inventory differs')
    rows=[];intervals=[];pids=set();reservations=set();counts={n:0 for n in ('hardware-debug','software-debug','hardware-plain','software-plain')}
    for path in a.runs:
        m=json.loads((path/'manifest.json').read_text());raw=json.loads((path/'stdout.json').read_text());debug=m['status']=='TERMINAL_DEBUGGER'
        mode=(m['mode']+'-debug') if debug else m['mode'];need(mode in counts,'mode differs');counts[mode]+=1
        need(m['build_sha256']==sha(a.build/'build.json') and m['stdout_sha256']==sha(path/'stdout.json') and
             m['stderr_sha256']==sha(path/'stderr.log') and
             sha(path/'client')==m['host_sha256']==b['build_sha256']['client'] and
             subprocess.run(['codesign','--verify','--strict',str(path/'client')],capture_output=True).returncode==0,'run identity differs')
        start=datetime.datetime.fromisoformat(m['started_at']);end=datetime.datetime.fromisoformat(m['completed_at']);need(start<end,'interval differs');intervals.append((start,end))
        r=m['reservation'];pid=m['debugger_pid'] if debug else m['pid']
        need(r['state']=='terminal' and r['exit_code']==0 and not r['SIGKILL_requested'] and not r['authoritative_ps_status'] and
             r['bootstrap_process_table_checked'] and r['child_birth_observed'] and r['child_PID']==pid and
             r['signed_binary_sha256']==m['host_sha256'] and pid not in pids and r['reservation_id'] not in reservations,'reservation differs')
        pids.add(pid);reservations.add(r['reservation_id']);hardware=mode.startswith('hardware')
        expected_binding={'valid':True,'target_image':'MetalOld.dylib','target_offset':0x29996,'target_symbol':'MTLCopyAllDevicesWithObserver'}
        need(raw['binding_before']==expected_binding and raw['binding_after']==expected_binding and not raw['observer_loaded'] and raw['unique_nvidia_pci_target'] and raw['retained_target_service_verified'],'client observation differs')
        if hardware:need(raw['status']=='CREATE_FAILED' and raw['create_status']==-12906 and raw['frames']==0 and not (path/'decoded.nv12').exists(),'hardware result differs')
        else:need(raw['status']=='PASS' and raw['create_status']==0 and raw['frames']==6 and (path/'decoded.nv12').read_bytes()==(a.build/'reference.nv12').read_bytes(),'software result differs')
        observations=[]
        stderr=(path/'stderr.log').read_text()
        if debug and hardware:
            need(re.fullmatch(r'.* client\['+str(m['target_pid'])+r':\d+\] \[\] <<<< VT-DS >>>> signalled err=-12906 at <>:2627\n',stderr) is not None,'video diagnostic differs')
        else:need(not stderr,'unexpected diagnostic')
        if debug:
            log=(path/'lldb.log').read_text();need(m['runner_sha256']==sha(HERE/'run.py') and m['lldb_log_sha256']==sha(path/'lldb.log') and
                log.count('KM_TRACE_ARM_PASS mode=video')==1 and not any(x in log for x in ('KM_TRACE_ARM_FAIL','KM_TRACE_HIT_FAIL','KP_GUARD_UNRESOLVED','KP_GUARD_NO_PROCESS')) and
                re.findall(r'^KP_PROCESS_EXITED pid=(\d+) code=0$',log,re.M)==[str(m['target_pid'])],'debug receipt differs')
            devices=re.findall(r'^KM_TRACE_DEVICE thread=(\d+) target_match=1 bytes_match=1$',log,re.M)
            lists=re.findall(r'^KM_TRACE_LIST thread=(\d+) nonnull=1 bytes_match=1$',log,re.M)
            batches=re.findall(r'^KM_TRACE_BATCH thread=(\d+) count=(\d+) same_list=1 item_match=1 bytes_match=1$',log,re.M)
            input_hits=re.findall(r'^KM_TRACE_FILTER_INPUT thread=(\d+) device_match=1 bytes_match=1$',log,re.M)
            allocation_hits=re.findall(r'^KM_TRACE_DICT_ALLOC thread=(\d+) nonnull=1 bytes_match=1$',log,re.M)
            output_hits=re.findall(r'^KM_TRACE_FILTER_OUTPUT thread=(\d+) input_match=1 nonnull=1 same_alloc=1 bytes_match=1$',log,re.M)
            reg_hits=re.findall(r'^KM_TRACE_KEY_REG thread=(\d+) nonnull=1 same_dict=1 bytes_match=1$',log,re.M)
            name_hits=re.findall(r'^KM_TRACE_KEY_NAME thread=(\d+) nonnull=1 same_dict=1 bytes_match=1$',log,re.M)
            cmp_in=re.findall(r'^KM_TRACE_COMPARE_INPUT thread=(\d+) name_match=1 key_match=1 bytes_match=1$',log,re.M)
            cmp_out=re.findall(r'^KM_TRACE_COMPARE_RESULT thread=(\d+) same_input=1 equal=0 bytes_match=1$',log,re.M)
            set_in=re.findall(r'^KM_TRACE_SET_INPUT thread=(\d+) distinct_destination=1 key_match=1 value_match=1 bytes_match=1$',log,re.M)
            set_out=re.findall(r'^KM_TRACE_SET_RETURN thread=(\d+) input_match=1 bytes_match=1$',log,re.M)
            next_hits=re.findall(r'^KM_TRACE_NEXT_BATCH thread=(\d+) count=0 same_list=1 bytes_match=1$',log,re.M)
            branch_hits=re.findall(r'^KM_TRACE_BRANCH thread=(\d+) flag=0 same_compare=1 bytes_match=1$',log,re.M)
            path_hits=re.findall(r'^KM_TRACE_PATH thread=(\d+) choice=zero bytes_match=1$',log,re.M)
            apply_hits=re.findall(r'^KM_TRACE_APPLY thread=(\d+) dest_callback_context_match=1 bytes_match=1$',log,re.M)
            callback_hits=re.findall(r'^KM_TRACE_CALLBACK thread=(\d+) key_match=1 value_match=1 context_match=1 bytes_match=1$',log,re.M)
            available_hits=re.findall(r'^KM_TRACE_AVAILABLE thread=(\d+) value=1 bytes_match=1$',log,re.M)
            append_hits=re.findall(r'^KM_TRACE_APPEND_INPUT thread=(\d+) context_value_match=1 bytes_match=1$',log,re.M)
            append_returns=re.findall(r'^KM_TRACE_APPEND_RETURN thread=(\d+) available=1 bytes_match=1$',log,re.M)
            stores=re.findall(r'^KM_TRACE_OUT_STORE thread=(\d+) same_frame=1 same_array=1 slot_nonnull=1 bytes_match=1$',log,re.M)
            outputs=re.findall(r'^KM_TRACE_OUT_AFTER thread=(\d+) same_frame=1 stored_array_match=1 status=0 parent_image=([A-Za-z0-9_.-]+) parent_offset=(\d+) bytes_match=1$',log,re.M)
            count_in=re.findall(r'^KM_TRACE_COUNT_INPUT thread=(\d+) same_array=1 same_caller_frame=1 bytes_match=1$',log,re.M)
            count_out=re.findall(r'^KM_TRACE_COUNT_OUTPUT thread=(\d+) count=(\d+) same_caller_frame=1 bytes_match=1$',log,re.M)
            item_in=re.findall(r'^KM_TRACE_ITEM_INPUT thread=(\d+) same_array=1 index=(\d+) same_caller_frame=1 bytes_match=1$',log,re.M)
            item_out=re.findall(r'^KM_TRACE_ITEM_OUTPUT thread=(\d+) gtx_entry_match=1 same_caller_frame=1 bytes_match=1$',log,re.M)
            request_in=re.findall(r'^KM_TRACE_REQUEST_INPUT thread=(\d+) item_match=1 gtx_entry_match=1 request_nonnull=1 third_zero=1 same_caller_frame=1 bytes_match=1$',log,re.M)
            request_out=re.findall(r'^KM_TRACE_REQUEST_OUTPUT thread=(\d+) input_matched=1 return_byte=(\d+) same_caller_frame=1 bytes_match=1$',log,re.M)
            reason_in=re.findall(r'^KM_TRACE_REASON_INPUT thread=(\d+) parent_match=1 entry_match=1 key_match=1 request_match=1 bytes_match=1$',log,re.M)
            reason_out=re.findall(r'^KM_TRACE_REASON_RESULT thread=(\d+) kind=([a-z]+) nonzero=([01]) same_filter_frame=1 bytes_match=1$',log,re.M)
            held_in=re.findall(r'^KM_TRACE_HELD_PORT thread=(\d+) held_match=1 bytes_match=1$',log,re.M)
            property_in=re.findall(r'^KM_TRACE_PROPERTY_INPUT thread=(\d+) same_filter_frame=1 request_match=1 service_nonzero=1 service_match=1 held_match=1 plane_ioservice=1 options=1 constant_shape=([01]) key=([A-Za-z0-9_]+) bytes_match=1$',log,re.M)
            if hardware:
                need(len(devices)==len(lists)==len(batches)==1 and devices==lists and batches[0]==(lists[0],'1'),'video enumeration identity differs')
                need(input_hits==lists and allocation_hits==lists and output_hits==lists and log.index('KM_TRACE_BATCH thread=')<log.index('KM_TRACE_FILTER_INPUT thread=')<log.index('KM_TRACE_DICT_ALLOC thread=')<log.index('KM_TRACE_FILTER_OUTPUT thread='),'dictionary identity differs')
                need(reg_hits==lists and name_hits==lists and cmp_in==lists and cmp_out==lists and log.index('KM_TRACE_FILTER_OUTPUT thread=')<log.index('KM_TRACE_KEY_REG thread=')<log.index('KM_TRACE_KEY_NAME thread=')<log.index('KM_TRACE_COMPARE_INPUT thread=')<log.index('KM_TRACE_COMPARE_RESULT thread='),'key comparison differs')
                need(set_in==lists and set_out==lists and log.index('KM_TRACE_KEY_NAME thread=')<log.index('KM_TRACE_SET_INPUT thread=')<log.index('KM_TRACE_SET_RETURN thread=')<log.index('KM_TRACE_COMPARE_INPUT thread='),'registration call observation differs')
                need(next_hits==lists and branch_hits==lists and path_hits==lists and log.count('KM_TRACE_PATH thread=')==1 and log.index('KM_TRACE_COMPARE_RESULT thread=')<log.index('KM_TRACE_NEXT_BATCH thread=')<log.index('KM_TRACE_BRANCH thread=')<log.index('KM_TRACE_PATH thread='),'enumeration decision differs')
                need(apply_hits==lists and callback_hits==lists and available_hits==lists and append_hits==lists and append_returns==lists and log.index('KM_TRACE_SET_RETURN thread=')<log.index('KM_TRACE_APPLY thread=')<log.index('KM_TRACE_CALLBACK thread=')<log.index('KM_TRACE_AVAILABLE thread=')<log.index('KM_TRACE_APPEND_INPUT thread=')<log.index('KM_TRACE_APPEND_RETURN thread='),'availability path differs')
                need(stores==lists and len(outputs)==1 and outputs[0][0]==lists[0] and int(outputs[0][2])>0 and log.index('KM_TRACE_APPEND_RETURN thread=')<log.index('KM_TRACE_OUT_STORE thread=')<log.index('KM_TRACE_OUT_AFTER thread='),'output observation differs')
                need(count_in==lists and count_out==[(lists[0],'1')] and item_in==[(lists[0],'0')] and item_out==lists and request_in==lists and request_out==[(lists[0],'0')] and log.index('KM_TRACE_OUT_AFTER thread=')<log.index('KM_TRACE_COUNT_INPUT thread=')<log.index('KM_TRACE_COUNT_OUTPUT thread=')<log.index('KM_TRACE_ITEM_INPUT thread=')<log.index('KM_TRACE_ITEM_OUTPUT thread=')<log.index('KM_TRACE_REQUEST_INPUT thread=')<log.index('KM_TRACE_REQUEST_OUTPUT thread='),'request filter observation differs')
                need(reason_in==lists and reason_out==[(lists[0],'first','0'),(lists[0],'absent','0'),(lists[0],'service','1'),(lists[0],'property','0')] and log.index('KM_TRACE_REQUEST_INPUT thread=')<log.index('KM_TRACE_REASON_INPUT thread=')<log.index('KM_TRACE_REASON_RESULT thread=')<log.index('KM_TRACE_REQUEST_OUTPUT thread='),'reason observation differs')
                need(held_in==lists and property_in==[(lists[0],'1','IOGVACodec')] and log.index('kind=service nonzero=1')<log.index('KM_TRACE_PROPERTY_INPUT thread=')<log.index('kind=property nonzero=0'),'property identity observation differs')
                observations=['property_shape='+property_in[0][1], 'property_key='+property_in[0][2], 'reason='+','.join(kind+':'+value for _,kind,value in reason_out),'filter_return='+request_out[0][1], 'array_count='+count_out[0][1], 'gtx_entry_at_index_zero', 'output_slot_matches_context','output_status_register_zero','parent_image='+outputs[0][1],'parent_offset='+outputs[0][2], 'table_apply_same_destination','callback_key_value_context_match','available_byte_one','append_context_value_match','append_call_returned','registration_key_matches','registration_value_matches','distinct_destination','registration_call_returned','next_batch_zero_same_list','branch_flag_zero_matches_compare','zero_path_reached','key_registry_present','key_name_present','comparison_input_match','comparison_return_zero','device_registry_match','nonnull_list','first_batch_one','first_item_device_match','helper_input_match','dictionary_allocation_nonnull','helper_output_matches_allocation','same_thread']
            else:need(not devices and not lists and not batches and not input_hits and not allocation_hits and not output_hits and not reg_hits and not name_hits and not cmp_in and not cmp_out and not next_hits and not branch_hits and not path_hits and not set_in and not set_out and not apply_hits and not callback_hits and not available_hits and not append_hits and not append_returns and not stores and not outputs and not count_in and not count_out and not item_in and not item_out and not request_in and not request_out and not reason_in and not reason_out and not property_in and not held_in and all(x not in log for x in ('KM_TRACE_DEVICE','KM_TRACE_LIST','KM_TRACE_BATCH','KM_TRACE_FILTER_INPUT','KM_TRACE_DICT_ALLOC','KM_TRACE_FILTER_OUTPUT','KM_TRACE_KEY_REG','KM_TRACE_KEY_NAME','KM_TRACE_COMPARE_INPUT','KM_TRACE_COMPARE_RESULT','KM_TRACE_NEXT_BATCH','KM_TRACE_BRANCH','KM_TRACE_PATH','KM_TRACE_SET_INPUT','KM_TRACE_SET_RETURN','KM_TRACE_APPLY','KM_TRACE_CALLBACK','KM_TRACE_AVAILABLE','KM_TRACE_APPEND_INPUT','KM_TRACE_APPEND_RETURN','KM_TRACE_OUT_STORE','KM_TRACE_OUT_AFTER','KM_TRACE_COUNT_INPUT','KM_TRACE_COUNT_OUTPUT','KM_TRACE_ITEM_INPUT','KM_TRACE_ITEM_OUTPUT','KM_TRACE_REQUEST_INPUT','KM_TRACE_REQUEST_OUTPUT','KM_TRACE_REASON_INPUT','KM_TRACE_REASON_RESULT','KM_TRACE_HELD_PORT','KM_TRACE_PROPERTY_INPUT')),'software observation differs')
        else:
            need(m['status']=='TERMINAL' and m['runner_sha256']==sha(HERE/'experiment.py') and
                 m['system_before']==SYSTEM and m['system_after']==SYSTEM,'plain receipt differs')
        rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'stdout_sha256':sha(path/'stdout.json'),
                     'lldb_log_sha256':sha(path/'lldb.log') if debug else None,'observations':observations,'frames':raw['frames'],'status':raw['create_status']})
    need(all(v==2 for v in counts.values()),'cohort count differs');intervals.sort();need(all(intervals[i-1][1]<=intervals[i][0] for i in range(1,len(intervals))),'overlapping intervals')
    record={'status':'PASS_VT_SERVICE_RETAINED','rows':rows,'hardware_debug_processes':2,'hardware_plain_processes':2,
        'software_frames':24,'software_bytes_compared':2764800,'first_batch_count':1,'next_batch_count':0,'same_list_verified':True,'total_count_conditional_on_fast_enumeration':1,
        'first_device_matches_selected_registry':True,'helper_input_same_device':True,'helper_return_matches_creation_result':True,'creator_slot_verified_at_arm_only':True,'registry_key_present':True,'io_registry_name_key_present':True,'registration_import':'_CFDictionarySetValue','registration_key_and_value_match':True,'registration_call_returned':True,'registration_destination_readback_via_callback':True,'callback_available_byte':1,'append_input_matches_callback':True,'append_call_returned':True,'filter_static_keys':['PresentIORegKeysAndValues','AbsentIORegKeys','Service'],'observed_first_lookup_nonnull':False,'observed_absent_lookup_nonnull':False,'observed_service_lookup_success':True,'observed_property_lookup_nonnull':False,'property_service_port_name_matches_metal_initializer':True,'matching_service_held_across_query':True,'property_service_registry_id_compared_directly_at_call':False,'property_key':'IOGVACodec','property_key_constant_shape_checked':True,'property_target_binding_checked_at_arm':True,'service_target_binding_checked_at_arm':True,'first_key_pointer_matched':True,'full_runtime_key_path_proved':False,'gtx_entry_at_index_zero':True,'filter_return_values':[int(next(x.split('=',1)[1] for x in row['observations'] if x.startswith('filter_return='))) for row in rows if row['mode']=='hardware-debug'],'output_slot_matches_context':True,'status_register_zero':True,'array_contents_after_return_proved':False,'array_consumption_by_decoder_proved':False,'registration_target_at_arm_only':True,'igpu_comparison_return':0,'branch_flag':0,'zero_path_reached':True,'lookup_and_comparator_binding_verified_at_arm_only':True,'dictionary_value_types_proved':False,'all_devices_identity_proved':False,'hardware_video_execution_proved':False,'same_thread_and_list':True,
        'selector':'countByEnumeratingWithState:objects:count:', 'dispatch_target_at_arm':'objc_msgSend',
        'metalold_sha256':sha(metal),'metalold_live_region_sha256':'f2df1f2af9af40e440eb1b78a4010bdbf6f4eaa4618a2d19322c5e4026f7a7fe','cache_uuid':img['UUID'],
        'cache_function_sha256':'f38fc93a01c9f5c715b94b5a2fe6a45c7ebccba26cdd0cedcadb06b7ffe9478b',
        'creator_import':'_CFDictionaryCreateMutable','helper_image_offset':'0x5fea84','helper_region_sha256':'b2b4a259e7b62af742beec8c6b6acbf8351443fc7edc0defe9ecd8ef6d2c1dad',
        'debugger_timing_may_change':True,'build_sha256':sha(a.build/'build.json'),'calibration_sha256':sha(a.calibration/'calibration.json'),
        'audit_sha256':sha(Path(__file__)),'runner_sha256':sha(HERE/'run.py'),'system_modified':False}
    a.out.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':record['status'],'first_batch':1,'first_item_target_match':True,'helper_return_matches_creation_result':True,'igpu_comparison_return':0,'next_batch':0,'path':'zero','registration_call_returned':True,'callback_available':1,'append_call_returned':True}))
if __name__=='__main__':main()
