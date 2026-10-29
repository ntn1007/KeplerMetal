#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare pinned selector descriptors offline; never issue an IOKit request."""
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load_local_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

dispatch=load_local_module('kepler_video_dispatch_audit',ROOT/'bridge/experiments/video_dispatch/audit.py')
profile=load_local_module('kepler_video_profile',ROOT/'bridge/tools/compare_video_profile.py')
validate_table=dispatch.validate_table
file_bytes=profile.file_bytes
symbols_and_external_relocations=profile.symbols_and_external_relocations

OLD_SHA='25a0bccd7caa884d6aa964743b35f879ec326c46d255dc6212c47e7a20f6f38e'
NEW_SHA='37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8'
PINS={'video-dispatch-validation.json':'1759b2f62d244bc5be2b78101fbaabe90d412dc7def1352d69b74e604254cad5',
      'video-method-contract-validation.json':'8b008472d677222b694c64bb761bda6ab1134748f12676f134b5e16fe700bb87',
      'video-selector-path-validation.json':'fe0645917c9a7cf44e6689223896e75a768e7d0c177fe879e07094fa26cef200'}

def sha(data):return hashlib.sha256(data).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)

def assess(old,current):
    """Describe a low-byte proposal, not a valid remapping or permission to call."""
    index=int(old['selector'],16)-0x100
    need(0<=index<13 and current.get('selector')==index,'unrelated method pair')
    shape=('flags','count0','count1')
    return {'legacy_selector':old['selector'],'legacy_method':old['function_name'],
            'candidate_index':index,'current_method':current.get('method_symbol'),
            'same_shape':all(old[n]==current[n] for n in shape),
            'legacy_shape':[old[n] for n in shape],'current_shape':[current[n] for n in shape],
            'member_pointer_kind':current.get('member_pointer_kind'),
            'decision':'REJECT_UNQUALIFIED','mapping_authorized':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('legacy-geforce','current-ioaccel','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    need(sha((ROOT/'bridge/experiments/video_dispatch/audit.py').read_bytes())=='c4e9d52baeaea26ba10adb2ca61e0700f636570ad59e97da23c12631b9a6a876' and sha((ROOT/'bridge/tools/compare_video_profile.py').read_bytes())=='3f0e6b796f90de5f7a578dd9abe6fc924530ad2853086ef8c583990953ac0506','helper source differs')
    docs=ROOT/'docs';receipts={}
    for name,pin in PINS.items():
        data=(docs/name).read_bytes();need(sha(data)==pin,'receipt changed: '+name);receipts[name]=json.loads(data)
    old=a.legacy_geforce.read_bytes();new=a.current_ioaccel.read_bytes()
    need(sha(old)==OLD_SHA and sha(new)==NEW_SHA,'kernel component profile differs')
    symbols,_=symbols_and_external_relocations(old);_,table=file_bytes(old,0x88a30,13*48)
    oldrows=validate_table(table,symbols);prior=receipts['video-dispatch-validation.json']
    need(prior['status']=='STATIC_DISPATCH_COMPARISON_PASS' and prior['historical_entries']==oldrows and prior['current_base_static_index_max']==7,'historical audit differs')
    methods=receipts['video-method-contract-validation.json']['methods'];need(len(methods)==8,'current method count')
    for i,row in enumerate(methods):
        start=row['file_offset'];data=new[start:start+48];need(len(data)==48 and sha(data)==row['descriptor_SHA256'] and row['selector']==i,'current descriptor')
        fields=struct.unpack('<6Q',data);target=int(row['method_address'],16) if row['method_address'] else 0
        need(fields==(0,target,row['this_adjustment'],row['flags'],row['count0'],row['count1']),'current descriptor fields')
    rows=[assess(oldrows[i],methods[i]) for i in range(8)]
    need(rows[1]['same_shape'] and rows[1]['legacy_method']=='set_source_size' and 'set_client_info' in rows[1]['current_method'],'same-shape example differs')
    need(not rows[5]['same_shape'] and rows[5]['legacy_method']=='acquire_channel' and 'finish_fence_event' in rows[5]['current_method'] and rows[5]['legacy_shape']==[0,1,2] and rows[5]['current_shape']==[0,1,0],'channel example differs')
    need(rows[6]['member_pointer_kind']=='null','special selector differs')
    conditional=receipts['video-selector-path-validation.json'];need(conditional['status']=='STATIC_CONDITIONAL_SYNC_PATH_PASS' and conditional['selector_0x105_model']=='CONDITIONAL_UNSUPPORTED' and not conditional['observed_live_selector'],'conditional evidence differs')
    result={'status':'PASS_STATIC_SELECTOR_COMPARISON','legacy_geforce_sha256':sha(old),'current_ioaccel_sha256':sha(new),
            'source_receipt_sha256':PINS,'audit_source_sha256':sha(Path(__file__).read_bytes()),'dispatch_helper_sha256':'c4e9d52baeaea26ba10adb2ca61e0700f636570ad59e97da23c12631b9a6a876','profile_helper_sha256':'3f0e6b796f90de5f7a578dd9abe6fc924530ad2853086ef8c583990953ac0506','low_index_proposals':rows,
            'legacy_indices_above_current_table':[r['selector'] for r in oldrows[8:]],
            'exact_shape_does_not_imply_semantic_compatibility':True,
            'any_mapping_authorized':False,'actual_live_dispatch_observed':False,
            'any_selector_called':False,'hardware_video_execution_proved':False,
            'limits':'Static file profiles only; semantic equivalence and other dispatch routes remain unproved.'}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'low_index_proposals':len(rows),'any_mapping_authorized':False}))
if __name__=='__main__':main()
