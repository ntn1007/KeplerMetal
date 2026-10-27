#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline extraction of the pinned Kepler video-context method table.

Reads local on-disk binaries and an archived REA evidence bundle. Compiles SDK
layout assertions only. Never opens a device or sends IOKit/GPU/RM requests.
"""
import argparse, hashlib, json, platform, struct, subprocess
from pathlib import Path
from compare_video_profile import file_bytes, symbols_and_external_relocations

ROOT=Path(__file__).resolve().parents[1]
IO_SHA='37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8'
GE_SHA='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
REA_SHA='acb34e18ff3a9fff305f988ee12430c25ea5e8ce668c18ddd1ba245bab19fd4d'
GET_DATA_REA_SHA='a1d16102765eb56d78066019ca4a91cb6ac2a056562f847675940745bfd5a5d7'
GET_BUFFER_REA_SHA='7bead58f8621856548e64a66d6db7c9fee4d40357ad4bcce3b5d7eada98c6f5b'
TABLE='__ZN15IOAccelContext215sContextMethodsE'
OVERRIDE='__ZN15IOAccelContext240sSubmitDataBuffersForegroundOnlyOverrideE'
VTABLE='__ZTV14nvVideoContext'
EXTERNAL='__ZN15IOAccelContext214externalMethodEjP25IOExternalMethodArgumentsP24IOExternalMethodDispatchP8OSObjectPv'
TARGET='__ZN15IOAccelContext226getTargetAndMethodForIndexEPP9IOServicej'
GET_DATA='__ZN15IOAccelContext213getDataBufferEP29IOAccelContextGetDataBufferInP30IOAccelContextGetDataBufferOutP22IOAccelResourcePrivatey'
ALLOC='__ZN15IOAccelContext218allocOneDataBufferEbj'
LIMITS='__ZN15IOAccelContext219getDataBufferLimitsEv'

# Expected original-disk metadata; this is not permission to invoke any selector.
EXPECTED=[
 ('__ZN15IOAccelContext26finishEv',0x679c,0,0,0),
 ('__ZN15IOAccelContext215set_client_infoEP17IOAccelClientInfoy',0x67aa,4,0,0xffffffff),
 ('__ZN15IOAccelContext219submit_data_buffersEP33IOAccelContextSubmitDataBuffersInP34IOAccelContextSubmitDataBuffersOutyPy',0x67d2,3,136,0xffffffff),
 ('__ZN15IOAccelContext215get_data_bufferEP29IOAccelContextGetDataBufferInP30IOAccelContextGetDataBufferOutyPy',0x7144,3,8,0xffffffff),
 ('__ZN15IOAccelContext217reclaim_resourcesEv',0x7290,0,0,0),
 ('__ZN15IOAccelContext218finish_fence_eventEj',0x7450,0,1,0),
 (None,0,0,0,0),
 ('__ZN15IOAccelContext224set_background_renderingEj',0x7628,0,1,0)]

def sha(data):return hashlib.sha256(data).hexdigest()
def symbol_one(symbols,name):
    matches=[x for x in symbols if x['name']==name and x['type']&0x0e==0x0e]
    if len(matches)!=1:raise ValueError('Missing/ambiguous defined symbol: '+name)
    return matches[0]

def descriptor(data,address,expected,relocations,symbols):
    offset,raw=file_bytes(data,address,48)
    obj,func,adjust,flags,count0,count1=struct.unpack('<QQQI4xQQ',raw)
    name,target,ex_flags,ex_0,ex_1=expected
    if (obj,func,adjust,flags,count0,count1)!=(0,target,0,ex_flags,ex_0,ex_1):
        raise ValueError('Method descriptor differs at '+hex(address))
    if any(relocations.get(address+off) for off in (0,8,16,24,32,40)):
        raise ValueError('Unresolved external relocation in method descriptor')
    if name and symbol_one(symbols,name)['value']!=target:
        raise ValueError('Method target symbol differs')
    return {'address':hex(address),'file_offset':offset,'descriptor_SHA256':sha(raw),
            'member_pointer_kind':'direct' if func else 'null','method_symbol':name,
            'method_address':hex(func) if func else None,'this_adjustment':adjust,
            'flags':flags,'count0':count0,'count1':count1}

def static_contract(io_path,ge_path,rea_path):
    io,ge=Path(io_path).read_bytes(),Path(ge_path).read_bytes()
    if sha(io)!=IO_SHA or sha(ge)!=GE_SHA or sha(Path(rea_path).read_bytes())!=REA_SHA:
        raise ValueError('Exact binary/evidence profile differs')
    symbols,relocs=symbols_and_external_relocations(io)
    table=symbol_one(symbols,TABLE);override=symbol_one(symbols,OVERRIDE)
    if table['value']!=0x6e3a0 or override['value']!=0x6e520:
        raise ValueError('Method table symbols moved')
    methods=[dict(selector=i,**descriptor(io,table['value']+48*i,row,relocs,symbols)) for i,row in enumerate(EXPECTED)]
    expected_override=(EXPECTED[2][0],EXPECTED[2][1],0x13,EXPECTED[2][3],EXPECTED[2][4])
    foreground=descriptor(io,override['value'],expected_override,relocs,symbols)
    ge_symbols,ge_relocs=symbols_and_external_relocations(ge)
    if symbol_one(ge_symbols,VTABLE)['value']!=0x90fe8:raise ValueError('nvVideoContext vtable differs')
    links=[]
    for cell,name in ((0x91848,EXTERNAL),(0x91938,TARGET),(0x919e8,LIMITS),(0x91a60,GET_DATA),(0x91a68,ALLOC)):
        matches=ge_relocs.get(cell,[])
        if len(matches)!=1 or matches[0]['symbol']['name']!=name or (matches[0]['external'],matches[0]['length_code'],matches[0]['type'],matches[0]['pc_relative'])!=(1,3,0,0):
            raise ValueError('Vtable relocation differs: '+hex(cell))
        _,word=file_bytes(ge,cell,8)
        if word!=b'\0'*8:raise ValueError('Expected unresolved file relocation')
        links.append({'cell':hex(cell),'slot_from_vptr':hex(cell-0x90ff8),'external_symbol':name,
                      'target_on_disk':hex(symbol_one(symbols,name)['value']),'runtime_relocation_observed':False})
    bundle=json.loads(Path(rea_path).read_text())
    wanted={'0x8656':'ev_3fa93b6b92aaf5f590c5d5f85eb2af3e982d7e9e99a2d559f53f1029796512fd',
            '0x860a':'ev_908982903c561a85746b8abba566390302e9af730bdfd9746484c9ab99c4bf01',
            '0xadec':'ev_99f570af976f00a966363ca531f34c8b84e8c4b27b684be9ba2af75b486f0575',
            '0x7a9c':'ev_cdf7ab79e67a28410b7f9c96a0efa68db74e71bfcf7f3ca039c465eaea50391f'}
    evidence=[]
    for address,eid in wanted.items():
        rows=[r for r in bundle['records'] if r['operation']=='analyze_function' and r['normalized_result']['procedure']['address']==address and r['evidence_id']==eid]
        if len(rows)!=1 or rows[0]['subject']['digest']['sha256']!=IO_SHA:raise ValueError('Pinned REA function evidence differs')
        anchors={'0xadec':['0xadff: MOV EAX, 0x2','0xae04: MOV dword ptr [RBX], EAX'],
                 '0x7a9c':['0x7c85: CALL qword ptr [RAX + 0x9f0]','0x7c8e: MOV dword ptr [RBX + 0x6dc], ECX']}
        if not all(x in rows[0]['normalized_result']['assembly'] for x in anchors.get(address,[])):
            raise ValueError('Archived class-limit instruction differs')
        evidence.append({'address':address,'evidence_id':eid,'provider':rows[0]['provider'],'limitations':rows[0]['limitations']})
    return {'IOAccelerator_SHA256':IO_SHA,'GeForce_SHA256':GE_SHA,'archived_REA_SHA256':REA_SHA,
            'table_address':hex(table['value']),'stride_bytes':48,'methods':methods,'foreground_override':foreground,
            'nvVideoContext_vtable_links':links,'archived_REA_functions':evidence,
            'static_candidate_classes':{'count_written_by_limits':2,'candidate_indices':[0,1],
                'initialization_is_conditional':True,'current_runtime_value_observed':False},
            'native_calls':0,'GPU_commands':0,'hardware_video_execution_proved':False,
            'scope':'Pinned on-disk tables and static REA evidence; no live selector dispatch or resource semantics proved'}

def get_data_evidence(path):
    raw=Path(path).read_bytes()
    if sha(raw)!=GET_DATA_REA_SHA:raise ValueError('get_data_buffer evidence changed')
    r=json.loads(raw);n=r['normalized_result']
    if (r['operation']!='analyze_function' or r['subject']['digest']['sha256']!=IO_SHA or
        r['evidence_id']!='ev_9ef4aee42a6f2eee153d0e5ff80c39bb8a4771f391d11562decd68341dbbbd03' or
        r['provider']!={'id':'ghidra','name':'Ghidra','version':'12.1.4'} or
        r['analysis_profile']['digest']!='c027fac311b23874c52441ed55610273dff33987b0370a0589c90be8f6d72b7a' or
        n['procedure']['address']!='0x7144' or n['procedure']['body']['total_bytes']!=331):
        raise ValueError('get_data_buffer identity differs')
    anchors=['0x7166: CMP RCX, 0x8','0x716a: JC 0x0000727d',
             '0x7173: CMP qword ptr [R8], 0x30','0x7177: JC 0x0000727d',
             '0x71fe: CALL qword ptr [RAX + 0xa68]']
    if not all(x in n['assembly'] for x in anchors):raise ValueError('Bounds/indirect-call observations differ')
    return {'address':'0x7144','evidence_id':r['evidence_id'],'REA_SHA256':GET_DATA_REA_SHA,
            'function_bytes':331,'input_bytes_minimum_in_body':8,'output_capacity_minimum_in_body':48,
            'next_virtual_slot_from_vptr':'0xa68','next_target_runtime_observed':False,
            'qualification':'Static disassembly only; resource ownership, contents and live behavior unknown'}

def get_buffer_evidence(path):
    raw=Path(path).read_bytes()
    if sha(raw)!=GET_BUFFER_REA_SHA:raise ValueError('getDataBuffer evidence changed')
    r=json.loads(raw);n=r['normalized_result']
    if (r['operation']!='analyze_function' or r['subject']['digest']['sha256']!=IO_SHA or
        r['evidence_id']!='ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9' or
        r['provider']!={'id':'ghidra','name':'Ghidra','version':'12.1.4'} or
        r['analysis_profile']['digest']!='c027fac311b23874c52441ed55610273dff33987b0370a0589c90be8f6d72b7a' or
        n['procedure']['address']!='0x9f70' or n['procedure']['body']['total_bytes']!=2532):
        raise ValueError('getDataBuffer identity differs')
    anchors=['0x9f84: MOV R9D, dword ptr [RSI]',
             '0x9fa1: CMP R9D, dword ptr [RDI + 0x6dc]',
             '0x9fa8: JNC 0x0000a0c0',
             '0x9fe5: MOV EAX, dword ptr [RSI + 0x4]',
             '0x9fff: CALL 0x00009ede',
             '0xa3b1: CALL qword ptr [RAX + 0xa70]']
    if not all(x in n['assembly'] for x in anchors):raise ValueError('Input/allocator observations differ')
    return {'address':'0x9f70','evidence_id':r['evidence_id'],'REA_SHA256':GET_BUFFER_REA_SHA,
            'function_bytes':2532,'first_input_word':'u32 compared against context + 0x6dc',
            'second_input_word':'u32 used in a conditional size-update calculation',
            'buffer_allocation_virtual_slot':'0xa70','allocation_runtime_observed':False,
            'qualification':'Static disassembly only; valid class values, returned resource and release ownership unknown'}

def sdk_assertions(out):
    if platform.system()!='Darwin' or platform.machine()!='x86_64':raise ValueError('Qualified SDK host required')
    sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
    if subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip()!='26.2':raise ValueError('Qualified SDK changed')
    hdr=Path(sdk)/'System/Library/Frameworks/Kernel.framework/Headers';source=ROOT/'tools/video_method_sdk_layout.cpp'
    base=['xcrun','clang++','-arch','x86_64','-std=c++17','-fsyntax-only','-I',str(hdr),str(source)]
    outputs=[]
    for label,argv in [('kernel',base[:6]+['-DKERNEL']+base[6:]),('user_negative',base)]:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=60)
        (out/(label+'.stdout')).write_text(p.stdout);(out/(label+'.stderr')).write_text(p.stderr)
        outputs.append({'mode':label,'exit_code':p.returncode,'stdout_SHA256':sha(p.stdout.encode()),'stderr_SHA256':sha(p.stderr.encode())})
    if outputs[0]['exit_code']!=0 or outputs[1]['exit_code']==0 or '40 == 48' not in (out/'user_negative.stderr').read_text():
        raise ValueError('SDK kernel/negative layout controls failed')
    return {'SDK_version':'26.2','kernel_layout_compile':'PASS','nonkernel_compile':'EXPECTED_FAILURE',
            'source_SHA256':sha(source.read_bytes()),'IOUserClient_header_SHA256':sha((hdr/'IOKit/IOUserClient.h').read_bytes()),
            'IOTypes_header_SHA256':sha((hdr/'IOKit/IOTypes.h').read_bytes()),'compiler_runs':outputs}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ioaccel',type=Path,required=True);p.add_argument('--geforce',type=Path,required=True);p.add_argument('--prior-rea',type=Path,required=True);p.add_argument('--get-data-rea',type=Path);p.add_argument('--get-buffer-rea',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output directory required')
    contract=static_contract(a.ioaccel,a.geforce,a.prior_rea);contract['get_data_buffer_observation']=get_data_evidence(a.get_data_rea) if a.get_data_rea else None;contract['getDataBuffer_observation']=get_buffer_evidence(a.get_buffer_rea) if a.get_buffer_rea else None;out.mkdir();contract['SDK_layout']=sdk_assertions(out)
    (out/'result.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(json.dumps({'status':'PASS','selectors':len(contract['methods']),'kernel_layout':'PASS','nonkernel_layout':'EXPECTED_FAILURE','GPU_commands':0}))

if __name__=='__main__':main()
