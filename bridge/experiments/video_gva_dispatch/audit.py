#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Correlate a pinned static GVA selector table with earlier recorded stacks.

This never executes or imports vendor code and does not infer actual register values.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

START=115359
SIZE=719
TABLE=0x291
EXPECTED={2:115449,3:115811,4:115811,5:115644,6:115811,7:115811,
          8:115685,9:115449,10:115811,11:115728,12:115811,13:115811,
          14:115497,15:115547,16:115597}
REGION='cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c'
OBJECT='5ebac1c972a7b134e8676aa0bc20c2a51fdc8418145daea30e9a526cf2f8b7e5'
EVIDENCE='ev_415b2e7d3c80855d44d12dfda5e5c80d10b1e10779b86551758f41664a4570ef'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def decode_table(data,start,table_offset,count):
    need(isinstance(start,int) and start>=0 and isinstance(table_offset,int) and table_offset>=0 and count==15 and
         table_offset+count*4<=len(data),'invalid table extent')
    table=start+table_offset;result={}
    for i in range(count):
        dest=table+struct.unpack_from('<i',data,table_offset+i*4)[0]
        need(start<=dest<start+len(data),'table target outside region')
        result[i+2]=dest
    return result

def validate_region(data):
    need(len(data)==SIZE and hashlib.sha256(data).hexdigest()==REGION,'region hash differs')
    need(data[0x1e:0x26].hex()=='b80700000083ff11' and
         data[0x32:0x3a].hex()=='b809000000418d4e' and
         data[0x4a:0x5a].hex()=='488d154002000048630c8a4801d1ffe1','selector guard or jump differs')
    table=decode_table(data,START,TABLE,15)
    need(table==EXPECTED,'decoded destinations differ')
    # Verify the instruction that ends at the recorded 115492 return address.
    site=115487-START;need(data[site]==0xe8,'constructor call opcode differs')
    target=115492+struct.unpack_from('<i',data,site+1)[0]
    need(target==233054,'constructor call target differs')
    return table,target

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('region','metadata','object','rea','stack-map','cohort-audit','stub-map','out'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    pins={'metadata':'b5725e6ea80f9f67136dddf43f2a295958ffed560face7bf56bf55a80f4596ca',
          'object':OBJECT,'rea':'a72946af5c1d95acccf4c723fd6b62eb119b73a53cb040e0ab68bd5d11d649c5',
          'stack_map':'d5ae8902628d7193c32fb159fcfced0f02070c00bf84fbdfc8e5cb34bd0c219d',
          'cohort_audit':'03bf49514bacec7383f5d6230edd1bf77fe78c887fe3bd13b864ae8508fd501f',
          'stub_map':'b8aacf6ec7b4c1a0613bd82c6a1aaa53e2854d2194ac8ebc0a9412699a5680c0'}
    for name,digest in pins.items():need(sha(getattr(a,name))==digest,name+' differs')
    data=a.region.read_bytes();mapping,target=validate_region(data)
    meta=json.loads(a.metadata.read_text());need(meta['image']['UUID']=='ca5414f369373c059ea2d82b35afd4f0' and
         meta['region']['target_image_offset']==START and meta['region']['bytes']==SIZE and meta['region']['SHA256']==REGION and
         not meta['resident_code_identity_proved'],'capture metadata differs')
    # Independently bind the ELF analysis section to the captured source bytes.
    obj=a.object.read_bytes();need(obj[:6]==b'\x7fELF\x02\x01','ELF profile differs')
    shoff=struct.unpack_from('<Q',obj,40)[0];shsize,shnum=struct.unpack_from('<HH',obj,58)
    need(shsize==64 and 1<shnum<=64 and shoff+shsize*shnum<=len(obj),'ELF section table differs')
    sections=[]
    for i in range(shnum):
        off=shoff+i*shsize;typ=struct.unpack_from('<I',obj,off+4)[0];address,offset,length=struct.unpack_from('<QQQ',obj,off+16)
        if typ==1 and length==SIZE and offset+length<=len(obj) and obj[offset:offset+length]==data:sections.append(address)
    need(len(sections)==1 and sections[0]==meta['region']['start_VM'],'ELF text source differs')
    evidence=json.loads(a.rea.read_text());records=[r for r in evidence['records'] if r['evidence_id']==EVIDENCE]
    need(len(records)==1 and records[0]['subject']['digest']['sha256']==OBJECT and records[0]['provider']['id']=='ghidra','REA evidence differs')
    api=records[0]['normalized_result']['native_api'];tables=api['jump_tables']
    need(len(tables)==1 and tables[0]['dispatch_address']=='0x7ffa0d92a2f7','REA dispatch differs')
    rebased=sections[0]+0x100000
    cases={r['case_value']:int(r['target_address'],16)-rebased+START for r in tables[0]['mappings']}
    nondefault={k:v for k,v in mapping.items() if v!=115811}
    need(cases==nondefault,'REA case mapping differs')
    stack=json.loads(a.stack_map.read_text());need(stack['status']=='STATIC_AND_RECORDED_STACK' and
         stack['image_UUID']==meta['image']['UUID'] and stack['live_code_identity_proved_for_every_frame'] is False and
         any(r['return_offset']==115492 and r['cache_function_start']==START and r['static_direct_call_target']==target for r in stack['rows']),'stack map differs')
    cohort=json.loads(a.cohort_audit.read_text());need(cohort['status']=='PASS' and cohort['GVA_property_runs']==9 and
         cohort['hardware_required_failures']==10 and cohort['hardware_images']==0,'cohort differs')
    stubs=json.loads(a.stub_map.read_text());matches=[r for r in stubs['rows'] if r['caller_offset']==115461]
    need(stubs['status']=='STATIC_ONLY' and len(matches)==1 and matches[0]['exact_defined_symbols']==['__ZnwmRKSt9nothrow_t'] and
         matches[0]['runtime_target_proved'] is False,'allocator stub differs')
    result={'status':'PASS_STATIC_AND_ARCHIVED_STACK','image_UUID':meta['image']['UUID'],'region_SHA256':REGION,
        'selector_case_targets':{str(k):v for k,v in mapping.items()},'observed_stack_return_offset':115492,
        'static_call_target_offset':target,'possible_cases_if_pinned_entry_flow_applies':[2,9],
        'actual_case_observed':False,'live_code_identity_proved_for_every_frame':False,'stack_complete':False,
        'counterfactual_property_and_policy_used':True,'hardware_video_execution_proved':False,
        'allocator_static_symbol':'__ZnwmRKSt9nothrow_t','allocator_runtime_target_proved':False,
        'REA_evidence_id':EVIDENCE,'REA_subject_SHA256':OBJECT,'source_evidence_sha256':pins,'GPU_or_vendor_execution_during_audit':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
