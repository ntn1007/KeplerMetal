#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline evidence audit: video and ordinary resource reply address provenance.

Does not open a device, evaluate a live response or authorize a selector.
"""
import argparse,hashlib,json
from pathlib import Path
from compare_video_profile import file_bytes
IO_SHA='37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8'
OLD_SHA='7bead58f8621856548e64a66d6db7c9fee4d40357ad4bcce3b5d7eada98c6f5b'
BUNDLE_SHA='2b495cf244219ff82bc88d68a27a5dab44daeed33cb3b11c5fc2d9aa4d8c18bd'
CASES={
 'resource':('ev_96202f162ea88502ff6568d8488de45dd586c1f9d38099f911bea7570ecc9932',0x23baa,30,'a240064908acc4c7999341e7a0fb7d3b0be436458650e43f65d343f267fe59fd'),
 'namespace':('ev_48229cf29413a8fc19babaea90fc6c7b1492cf8a5d20abe9313aec4e01c24e52',0x29300,59,'0269faaa59c968a6cc17fac0c2c374591d041590edeee0767a9581702af862c1'),
 'machine':('ev_1e269c37f956818dbb4b05eeb92074a4d0bd6b1fdb3078e35e66db4772268227',0x28dd6,79,'3a3522181c0b04368175f837cc58c644abeae5f1804fe513afb1af49c3b9fb28'),
 'ordinary':('ev_a0789b08c009780d402edf2bfb453ee445063f7da7e6243e98e6b475a03a2c29',0x2b806,3155,'6442047166a21b81fe32f5c8f4732d5b73db3674c977dfdb83fbef3e889984ab')}
ANCHORS={
 'resource':['0x23bb4: MOV RAX, qword ptr [RDI + 0x38]','0x23bb8: MOV RDI, qword ptr [RDI + 0x68]','0x23bbc: MOV ESI, dword ptr [RAX + 0x100]','0x23bc3: JMP 0x00029300'],
 'namespace':['0x29313: ADD RDI, 0x50','0x29317: CALL 0x00028dd6','0x2931c: ADD R15, 0x90','0x29336: JMP 0x00028dd6'],
 'machine':['0x28ddd: DIV dword ptr [RDI + 0x38]','0x28de0: CMP EAX, dword ptr [RDI + 0x34]','0x28df4: TEST RAX, RAX','0x28df7: JZ 0x00028e07','0x28dfb: IMUL RDX, qword ptr [RDI + 0x18]','0x28e03: MOV qword ptr [RCX], RDX','0x28e20: CALL 0x00155600'],
 'ordinary':['0x2c316: LEA RSI, [RCX + 0x10]','0x2c31a: LEA RDX, [RCX + 0x18]','0x2c324: CALL 0x00023baa']}
VIDEO=['0xa6da: MOV RAX, qword ptr [R13 + 0x38]','0xa6de: MOV EAX, dword ptr [RAX + 0x100]','0xa6e4: MOV dword ptr [RBX + 0x28], EAX','0xa6e7: LEA RSI, [RBX + 0x18]','0xa6eb: LEA RDX, [RBX + 0x20]','0xa6f2: CALL 0x00023baa','0xa712: MOV qword ptr [RBX], RCX','0xa74e: MOV qword ptr [RBX + 0x8], RAX','0xa8a5: MOV qword ptr [RBX + 0x10], RCX']
def sha(b):return hashlib.sha256(b).hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def validate_records(old,bundle):
 need(old['evidence_id']=='ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9' and old['subject']['digest']['sha256']==IO_SHA and old['normalized_result']['procedure']['address']=='0x9f70','video evidence identity')
 need(all(x in old['normalized_result']['assembly'] for x in VIDEO),'video field anchors')
 records={r['evidence_id']:r for r in bundle['records']};need(len(records)==len(bundle['records']),'duplicate evidence IDs')
 for name,(eid,address,size,_) in CASES.items():
  need(eid in records,'missing evidence '+name);r=records[eid];n=r['normalized_result'];body=n['procedure']['body']
  need(r['subject']['digest']['sha256']==IO_SHA and n['procedure']['address']==hex(address) and body['available'] and body['total_bytes']==size and all(x in n['assembly'] for x in ANCHORS[name]),'evidence differs '+name)
 need(any(c['address']=='0x155600' and '_panic' in c['name'] for c in records[CASES['machine'][0]]['normalized_result']['callees']),'panic target differs')
def audit(driver,prior,bundle):
 image=driver.read_bytes();old=prior.read_bytes();raw=bundle.read_bytes();need(sha(image)==IO_SHA and sha(old)==OLD_SHA and sha(raw)==BUNDLE_SHA,'pinned input differs');validate_records(json.loads(old),json.loads(raw))
 bodies={'video':(0x9f70,2532,'1846ead1bc333cb0249a67da9a727e7c76e0e1558e62103dfe5b0b9c08f6c59b')};bodies.update({k:(v[1],v[2],v[3]) for k,v in CASES.items()})
 for name,(addr,n,digest) in bodies.items():
  _,code=file_bytes(image,addr,n);need(sha(code)==digest,'file bytes differ '+name)
 return {'status':'PASS_STATIC_VIDEO_REPLY_IDENTITY','ioaccel_sha256':IO_SHA,'prior_evidence_sha256':OLD_SHA,'rea_bundle_sha256':BUNDLE_SHA,'function_bodies_sha256':{n:x[2] for n,x in bodies.items()},'rea_evidence_ids':{n:x[0] for n,x in CASES.items()},'video_evidence_id':'ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9','video_reply_offsets':{'shared_address_outputs':['0x18','0x20'],'resource_id_u32':'0x28','other_outputs':['0x00','0x08','0x10']},'ordinary_resource_reply_offsets':['0x10','0x18'],'shared_namespace_lookup_checks_index_and_mapping':True,'panic_target_statically_present':True,'native_method_called':False,'live_resource_or_reply_observed':False,'hardware_video_execution_proved':False,'system_modified':False,'limits':['Static file and decompiler evidence; live code, object identity and layout are unverified.','Conditional panic path is not an observed failure and no untrusted selector input is claimed to reach it.','Returned values are not established as GPU addresses, valid mappings or safe to use.','No selector, channel, ownership or cleanup is authorized.']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--driver',type=Path,required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--rea',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');r=audit(a.driver,a.prior,a.rea)
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
