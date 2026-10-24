#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit immutable native library registration and zero-submission contracts."""
from pathlib import Path
import json
from public_large_scratch import sha,read
from verify_local_memory import verify_device_identity
NEGATIVES=['empty_source','bad_hash','empty_names','duplicate_names','wrong_name_type','missing_function','partial_after_valid','opposite_ABI','old_opaque']
CASES=NEGATIVES+['immutable_registration','duplicate_registration']
for library in range(3):CASES +=[f'unlisted_passthrough_{library}']+[f'function_{library}_{f}'for f in range(9)]
CASES+=['native_objects_restored','inactive_registration']


def verify(root):
 root=Path(root);d=read(root/'results.json');inp=read(root/'inputs.json');m=read(root/'execution/manifest.json')
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
 for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
  for name,digest in inp[key].items():assert sha(root/folder/name)==digest
 verify_device_identity(d);assert d['status']=='PASS'and not d['system_modified']and d['GPU_dispatches']==d['GPU_submissions']==0
 tagged=inp['mode']=='reusable';assert bool(d['generation_tagged_root'])==tagged
 assert d['source_SHA256']==inp['assets_SHA256']['reusable_producer.metallib'if tagged else'native_producer.metallib']
 assert [e['case']for e in d['cases']]==CASES and all(e['PASS']for e in d['cases'])
 assert[(e['library'],e['function'],e['pipeline'])for e in d['factories']]==[(l,f,p)for l in range(3)for f in range(9)for p in range(6)]
 for e in d['factories']:
  assert e['PASS'];r=e['receipt'];p=e['pipeline'];assert r['pipeline_factory']==p and r['pipeline_callbacks']==int(p>=3)and r['native_reflection']==(p not in[0,3])and r['pipeline_class']=='NVMTLComputePipelineState'
  assert r['pipeline_members']==([dict(index=i,type=t,offset=i*8)for i,t in enumerate([85 if tagged else 60,85,60,60,60,60])]if p not in[0,3]else[])
 events=d['events'];reg=[e for e in events if e.get('operation')=='register_native_source_IRv2_library'];assert len(reg)==1
 e=reg[0];assert e['source_SHA256']==d['source_SHA256']and e['functions']==['encode_dataflow_basic']and e['prepared_native_pipelines']==1 and not e['instruction_import']and not e['GPU_execution']and bool(e['generation_tagged_root'])==tagged
 assert not any(e.get('operation')in['IRv2_pipeline_contract_request','new_registered_IRv2_pipeline','register_native_source_IRv2_function']for e in events)
 assert len([e for e in events if e.get('operation')=='restore_IRv2_libraries'])==1
 assert len([e for e in events if e.get('operation')=='automatic_compute_factories_restored'and e['queue_class_restored']])==1
 return dict(status='PASS',contract_cases=len(CASES),expected_refusals=len(NEGATIVES)+2,native_factory_observations=162,unlisted_function_passthroughs=3,GPU_dispatches=0,GPU_submissions=0,generation_tagged_root=tagged,full_objective_complete=False)
