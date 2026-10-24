#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck reusable-context receipts and the complete prior native/NAK cohort.

CPU-only audit of immutable captures. It does not perform or attest a new GPU run.
"""
from pathlib import Path
import argparse,json
from public_large_scratch import read,sha
from public_native_msl_commands import REUSABLE_FLOW_MODES,msl_abi,lower_readonly_members
from audit_native_msl_commands import audit as audit_regression
from verify_command_ir_dataflow import verify


def audit(root):
 root=Path(root);baseline=audit_regression(root/'regression',function_arguments=True,stable_identities=True)
 reusable=root/'reusable';assert {p.name for p in reusable.iterdir()if p.is_dir()}==set(REUSABLE_FLOW_MODES)
 results=[];intervals=[];library=baseline['static_library_SHA256']
 for path in (root/'regression').iterdir():
  if path.is_dir():
   m=read(path/'execution/manifest.json');intervals.append((m['started_at'],m['completed_at']))
 for mode in REUSABLE_FLOW_MODES:
  path=reusable/mode;inp=read(path/'inputs.json');m=read(path/'execution/manifest.json')
  assert inp['kind']=='reusable'and inp['mode']==mode and inp['reusable_contexts_built']
  assert inp['native_function_arguments']and inp['native_stable_pipeline_identities']
  assert inp['static_library_SHA256']==library
  assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
  assert sha(path/'application')==inp['executable_SHA256']==m['original_binary_sha256']
  assert sha(path/'execution/application')==m['signed_binary_sha256']
  for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
   for name,digest in inp[key].items():assert sha(path/folder/name)==digest
  assert (path/'include/KeplerCommandIR.h').read_text()==msl_abi((path/'src/KeplerCommandIR.h').read_text())
  for source,profile in [('gpu_command_frontend_dataflow',{'parameters':('uint',4)}),('native_command_records_probe',{'constants':('uint',3)})]:
   assert (path/'lowered'/(source+'.metal')).read_text()==lower_readonly_members((path/'src'/(source+'.metal')).read_text(),profile)
  proof=verify(path);saved=read(path/'independent-verification.json')
  for key,value in proof.items():assert saved[key]==value,(mode,key)
  results.append({k:v for k,v in proof.items()if k!='raw_SHA256'})
  intervals.append((m['started_at'],m['completed_at']))
 intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
 pairs=0
 for mode in ['basic','barrier','copy']:
  for trial in range(4):
   for field in ['stage0','stage1','stage2','counter']:
    name=f'trial-{trial}-{field}.bin'
    assert (reusable/mode/'outputs'/name).read_bytes()==(root/'regression'/f'native-{mode}'/'outputs'/name).read_bytes();pairs+=1
 return dict(status='PASS',static_library_SHA256=library,signed_terminal_nonoverlapping_processes=len(intervals),
  reusable_processes=len(results),reusable_generations=sum(len(r['generations'])for r in results),
  reusable_exact_consumer_uint32=sum(r['exact_uint32_results']for r in results),
  reusable_consumer_invocations=sum(r['consumer_invocations']for r in results),
  reusable_guard_bytes=sum(r['guard_bytes']for r in results),
  premature_reuse_refusals=sum(r['lease_refusals']for r in results),
  retired_slot_consumers_refused=sum(r['retired_slot_consumers_refused']for r in results),
  stale_CPU_plans_refused=sum(r['stale_CPU_plans_refused']for r in results),
  stale_GPU_roots_refused=sum(r['GPU_stale_roots_refused']for r in results),
  delayed_consumer_processes=sum(r['materializer_completed_before_consumer']for r in results),
  identical_reusable_pointer_stage_counter_files=pairs,
  regression=baseline,cases=results,performance_benchmark=False,Apple_native_ICB_layout=False,
  system_modified=False,full_objective_complete=False)


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();r=audit(a.root)
 if a.out:
  with a.out.open('x')as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in r.items()if k not in ['cases','regression']},indent=2))
