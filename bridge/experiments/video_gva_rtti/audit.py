#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Resolve a pinned constructor's C++ type metadata from a local dyld cache."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from inspect_video_cache import Cache,image_map,inspect
from map_video_stub_targets import exact_symbols

IMAGE='/System/Library/PrivateFrameworks/AppleGVA.framework/Versions/A/AppleGVA'
UUID='ca5414f369373c059ea2d82b35afd4f0'
THUNK='3318c28c191393b96f825b4c97bc875f444c773bbfcc5c727fb6ba00f462143f'
INIT='80adc25382ccad971d4388af6ab616ae65200ab934d6819a7cbd54c9efdba68f'
OBJS=('939514251c976857f48ab64a101a2300f3cafb6ba7fc9b9f8e0b65311ab26cfc',
      '0558dbc3e9d4e10dbbbe781f2ca19aba0aeb467c6a58302aadfcb27ce38618e8')
IDS=('ev_7d4076952810b322845e9284ed3d7db48391119b14346479c2d3f90e734e6f6c',
     'ev_d9dd51fad1f0e876bdc7d52ed3b69c31dbdd46573c4645bf3e2c3d457727f4bb')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)
def branch(data,start,offset,opcode):
    need(offset>=0 and offset+5<=len(data) and data[offset]==opcode,'direct opcode or extent differs')
    return start+offset+5+struct.unpack_from('<i',data,offset+1)[0]
def lea(data,start,offset):
    need(offset>=0 and offset+7<=len(data) and data[offset:offset+3]==b'\x48\x8d\x05','LEA opcode or extent differs')
    return start+offset+7+struct.unpack_from('<i',data,offset+3)[0]
def contains(image,address,length,segment):
    return sum(s['name']==segment and s['VM_address']<=address and length<=s['VM_size'] and
               address-s['VM_address']<=s['VM_size']-length for s in image['segments'])==1
def bounded_name(cache,image,address):
    need(contains(image,address,64,'__TEXT'),'type name outside image text')
    raw=cache.read(address,64);end=raw.find(b'\0');need(0<end<64,'name not terminated')
    try:return raw[:end].decode('ascii')
    except UnicodeDecodeError:raise ValueError('type name is not ASCII')
def verify_rea(path,identity,objectsha,address):
    rows=[x for x in json.loads(path.read_text())['records'] if x['evidence_id']==identity]
    need(len(rows)==1 and rows[0]['operation']=='analyze_function' and rows[0]['provider']['id']=='ghidra' and
         rows[0]['subject']['digest']['sha256']==objectsha and rows[0]['normalized_result']['procedure']['address']==address,'REA identity differs')
def verify_object(path,region,vm):
    obj=path.read_bytes();need(len(obj)>=64 and obj[:6]==b'\x7fELF\x02\x01','ELF header differs')
    shoff=struct.unpack_from('<Q',obj,40)[0];shsize,shnum=struct.unpack_from('<HH',obj,58)
    need(shsize==64 and 1<shnum<=64 and shoff+shsize*shnum<=len(obj),'ELF section table differs')
    matches=[]
    for i in range(shnum):
        off=shoff+i*shsize;kind=struct.unpack_from('<I',obj,off+4)[0];address,fileoff,length=struct.unpack_from('<QQQ',obj,off+16)
        if kind==1 and length==len(region) and fileoff+length<=len(obj) and obj[fileoff:fileoff+length]==region:matches.append(address)
    need(matches==[vm],'ELF source bytes differ')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('cache','thunk','init','thunk-rea','init-rea','witness-audit','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required')
    pinned={'thunk_rea':'88f5ac6c037e7dac2883a9d16ba96a4a8db7f3ef16ce1d93f49f6b1f3e241765',
            'init_rea':'5f2fe115a1a8ee540cca544ac975dd0c7380ed600e463b94c739b60e7ecaee1b',
            'witness_audit':'1ed7bc1ae23e73ed3875eb876e8cdbb5f744a5444ae2877b83386d3b90f509f9'}
    for key,digest in pinned.items():need(sha(getattr(a,key))==digest,key+' differs')
    for path,expected,offset,obj in ((a.thunk,THUNK,233054,OBJS[0]),(a.init,INIT,232918,OBJS[1])):
        meta=json.loads((path/'metadata.json').read_text());region=meta['region']
        need(meta['image']['UUID']==UUID and region['target_image_offset']==offset and
             region['SHA256']==expected and sha(path/'function-region.private.bin')==expected and
             sha(path/'analysis.private.o')==obj,'capture differs')
        verify_object(path/'analysis.private.o',(path/'function-region.private.bin').read_bytes(),region['start_VM'])
    verify_rea(a.thunk_rea,IDS[0],OBJS[0],'0x7ffa0d946e5e')
    verify_rea(a.init_rea,IDS[1],OBJS[1],'0x7ffa0d946dd6')
    witness=json.loads(a.witness_audit.read_text());need(witness['status']=='PASS_BOUNDED_REGISTER_OBSERVATION' and
         witness['observed_selector']==2 and witness['current_board_observations']==3 and
         witness['hardware_images']==0 and witness['counterfactual_property_and_policy_used'],'runtime witness differs')
    cache=Cache(a.cache.resolve());mapped=image_map(a.cache.with_name(a.cache.name+'.map'),IMAGE)
    base=mapped[0]['start'];image,starts=inspect(cache,base,IMAGE);need(image['UUID']==UUID,'cache image differs')
    thunk=(a.thunk/'function-region.private.bin').read_bytes();init=(a.init/'function-region.private.bin').read_bytes()
    need(cache.read(base+233054,len(thunk))==thunk and cache.read(base+232918,len(init))==init,'cache code differs')
    need(thunk[:5]==bytes.fromhex('554889e55d') and branch(thunk,233054,5,0xe9)==232918 and
         branch(init,232918,9,0xe8)==117024 and init[21:24]==bytes.fromhex('488903'),'constructor chain differs')
    vptr=lea(init,base+232918,14);need(contains(image,vptr-16,24,'__DATA_CONST'),'vtable outside GVA data')
    info=cache.pointer_v2(vptr-8);need(contains(image,info,24,'__DATA_CONST'),'typeinfo outside GVA data')
    type_vptr=cache.pointer_v2(info);nameptr=cache.pointer_v2(info+8);parent=cache.pointer_v2(info+16)
    need(contains(image,parent,16,'__DATA_CONST'),'base typeinfo outside GVA data')
    parent_vptr=cache.pointer_v2(parent);parent_name=cache.pointer_v2(parent+8)
    derived=bounded_name(cache,image,nameptr);base_name=bounded_name(cache,image,parent_name)
    need(derived=='8Flow_QT0' and base_name=='4Flow','RTTI names differ')
    library='/usr/lib/libc++abi.dylib';libbase=image_map(a.cache.with_name(a.cache.name+'.map'),library)[0]['start']
    lib,_=inspect(cache,libbase,library);need(lib['UUID']=='53d7fc1acf383f409c54b63291e1675c','libc++abi identity differs')
    names=exact_symbols(cache,lib,{type_vptr-16,parent_vptr-16})
    need(names[type_vptr-16]==['__ZTVN10__cxxabiv120__si_class_type_infoE'] and
         names[parent_vptr-16]==['__ZTVN10__cxxabiv117__class_type_infoE'],'RTTI vtable symbols differ')
    candidate_slots=[cache.pointer_v2(vptr+i*8) for i in range(10)]
    expected_slots=[233074,233084,233956,234752,235048,235772,235984,236888,237318,237476]
    need([x-base for x in candidate_slots]==expected_slots and
         all(contains(image,x,1,'__TEXT') and x in starts for x in candidate_slots),'candidate slots differ')
    # Local, original classes independently exercise this compiler's RTTI layout.
    with tempfile.TemporaryDirectory(prefix='gva-rtti-cpu-',dir=out.parent) as d:
        exe=Path(d)/'calibrate';r=subprocess.run(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-Wall','-Wextra','-Werror',str(HERE/'calibrate.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=60)
        need(r.returncode==0,'CPU ABI compile failed: '+r.stderr[-1000:])
        r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10);need(r.returncode==0,'CPU ABI test failed')
        calibration=json.loads(r.stdout);need(calibration['status']=='PASS' and not calibration['GPU_execution'] and not calibration['vendor_execution'],'CPU ABI outcome differs')
        binary_sha=sha(exe)
    result={'status':'PASS_STATIC_RTTI_AND_BOUNDED_RUNTIME_SELECTOR','observed_selector':2,'runtime_selector_receipt_sha256':pinned['witness_audit'],
            'thunk_offset':233054,'thunk_target_offset':232918,'base_constructor_target_offset':117024,
            'constructor_vtable_address_point_image_offset':vptr-base,'derived_type':'Flow_QT0','base_type':'Flow',
            'first_ten_candidate_slot_targets_image_offsets':expected_slots,'vtable_extent_proved':False,
            'candidate_slot_runtime_dispatch_proved':False,
            'metadata_interpretation':'C++ Itanium-style single inheritance; independently checked with current compiler and libc++abi',
            'static_type_evidence_not_live_object_readback':True,'constructor_completed_at_runtime_proved':False,
            'video_engine_execution_proved':False,'counterfactual_property_and_policy_used':True,
            'REA_evidence_ids':list(IDS),'region_sha256':[THUNK,INIT],'analysis_container_sha256':list(OBJS),
            'source_evidence_sha256':pinned,'auditor_sha256':sha(Path(__file__)),
            'cpu_calibration_source_sha256':sha(HERE/'calibrate.cpp'),
            'cpu_abi_calibration':calibration,'cpu_calibration_binary_sha256':binary_sha,
            'vendor_execution_during_audit':False,'GPU_execution_during_audit':False,'system_modified':False}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
