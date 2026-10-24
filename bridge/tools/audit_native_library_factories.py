#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute ordinary native library reception and its full preceding cohort.

Offline capture audit only; this command performs no Metal/GPU execution.
"""
from pathlib import Path
import argparse,json
from public_large_scratch import read,sha
from public_native_msl_commands import STABLE_FLOW_MODES,REUSABLE_FLOW_MODES,msl_abi,lower_readonly_members
from audit_reusable_icb_contexts import audit as baseline_audit
from verify_command_ir_dataflow import verify as flow_verify
from verify_native_library_contracts import verify as contracts_verify


def audit(root):
 root=Path(root)
 # Also qualify the separately staged optional native-root fixture bank.
 for manifest in root.rglob('inputs.json'):
  if manifest.parent.name=='execution':continue
  inp=read(manifest)
  for name,digest in inp.get('legacy_assets_SHA256',{}).items():assert sha(manifest.parent/'legacy-assets'/name)==digest
 baseline=baseline_audit(root/'baseline');library=baseline['static_library_SHA256'];expected={}
 for mode in ['pointer','reusable']:expected['contracts/'+mode]=('library_contracts',mode,'0:0:0')
 expected.update({'library/'+m:('library',m,f'{i%3}:{i%9}:{i%6}')for i,m in enumerate(STABLE_FLOW_MODES)})
 expected.update({'library_reusable/'+m:('library_reusable',m,f'{(i+1)%3}:{(i+4)%9}:{(i+2)%6}')for i,m in enumerate(REUSABLE_FLOW_MODES)})
 expected.update({'legacy/'+m:('legacy_library',m,r)for m,r in [('basic','0:0:0'),('barrier','2:6:5')]})
 for group in ['contracts','library','library_reusable','legacy']:
  assert{str(p.relative_to(root))for p in(root/group).iterdir()if p.is_dir()}=={s for s in expected if s.startswith(group+'/')}
 intervals=[];cases=[]
 for p in(root/'baseline').rglob('execution/manifest.json'):
  m=read(p);intervals.append((m['started_at'],m['completed_at']))
 for label,(kind,mode,route)in expected.items():
  path=root/label;inp=read(path/'inputs.json');m=read(path/'execution/manifest.json');d=read(path/'results.json')
  assert(inp['kind'],inp['mode'],inp['library_route'])==(kind,mode,route)and inp['static_library_SHA256']==library
  assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
  assert sha(path/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(path/'execution/application')==m['signed_binary_sha256']
  for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
   for name,digest in inp[key].items():assert sha(path/folder/name)==digest
  assert(path/'include/KeplerCommandIR.h').read_text()==msl_abi((path/'src/KeplerCommandIR.h').read_text())
  for source,profile in [('gpu_command_frontend_dataflow',{'parameters':('uint',4)}),('native_command_records_probe',{'constants':('uint',3)})]:
   assert(path/'lowered'/(source+'.metal')).read_text()==lower_readonly_members((path/'src'/(source+'.metal')).read_text(),profile)
  proof=contracts_verify(path)if kind=='library_contracts'else flow_verify(path)
  saved=read(path/'independent-verification.json')
  for key,value in proof.items():assert saved[key]==value,(label,key)
  if kind=='legacy_library':
   assert d['producer_backend']=='NAK'and d['ordinary_library_function_factories']and d['automatic_encoders']
   assert d['manual_function_registration_calls']==d['manual_compute_adaptation_calls']==0 and d['native_factory_restored']and d['unregistered_native_failure_preserved']
   events=d['function_events'];regs=[e for e in events if e.get('operation')=='register_IRv2_library'];assert len(regs)==1 and regs[0]['source_SHA256']=='a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db'
   assert not any(e.get('operation')=='register_native_source_IRv2_library'for e in events)
   assert all(not e['native_source_lowering']for e in events if e.get('operation')=='automatic_IRv2_function')
  intervals.append((m['started_at'],m['completed_at']));cases.append(dict(case=label,kind=kind,route=route,**{k:v for k,v in proof.items()if k!='raw_SHA256'}))
 intervals.sort();assert len(intervals)==94 and all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
 pairs=0
 for label,(kind,mode,route)in expected.items():
  if kind=='library_contracts':continue
  reference=root/'baseline'/('reusable/'+mode if kind=='library_reusable'else'regression/'+('nak-'if kind=='legacy_library'else'native-')+mode)
  for trial in range(4):
   for field in ['stage0','stage1','stage2','counter']:
    name=f'trial-{trial}-{field}.bin';assert(root/label/'outputs'/name).read_bytes()==(reference/'outputs'/name).read_bytes(),(label,name);pairs+=1
 native=[r for r in cases if r['kind']in ['library','library_reusable']];contracts=[r for r in cases if r['kind']=='library_contracts'];legacy=[r for r in cases if r['kind']=='legacy_library']
 for kind in ['library','library_reusable']:
  routes=[list(map(int,r['route'].split(':')))for r in native if r['kind']==kind]
  for index,count in enumerate([3,9,6]):assert{r[index]for r in routes}==set(range(count))
 return dict(status='PASS',signed_terminal_nonoverlapping_processes=len(intervals),static_library_SHA256=library,
  native_library_processes=len(native),native_library_exact_consumer_uint32=sum(r['exact_uint32_results']for r in native),native_library_active_consumer_invocations=sum(r['consumer_invocations']for r in native),
  native_library_guard_bytes=sum(r['guard_bytes']for r in native),native_library_API_refusals=sum(r['API_refusals']for r in native),
  library_constructors_per_schema=3,function_variants_per_schema=9,pipeline_factories_per_schema=6,
  native_library_registration_processes=len(contracts),registration_contract_cases=sum(r['contract_cases']for r in contracts),registration_expected_refusals=sum(r['expected_refusals']for r in contracts),
  native_factory_metadata_observations=sum(r['native_factory_observations']for r in contracts),legacy_library_processes=len(legacy),legacy_library_consumer_uint32=sum(r['exact_uint32_results']for r in legacy),
  identical_new_baseline_stage_counter_files=pairs,manual_function_registrations=0,manual_compute_adaptations=0,native_producer_instruction_import=False,
  baseline=baseline,cases=cases,performance_benchmark=False,Apple_native_ICB_layout=False,full_objective_complete=False)


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();r=audit(a.root)
 if a.out:
  with a.out.open('x')as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in r.items()if k not in ['baseline','cases']},indent=2))
