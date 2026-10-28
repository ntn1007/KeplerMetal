#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-audit the experimental API and the captured reusable regression."""
import argparse, hashlib, importlib.util, json, subprocess, sys
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from audit_reusable_icb_contexts import audit as audit_cohort
from verify_command_ir_dataflow import verify
PIN='69f168d148a24fee4aba2eae015587aeec79f677fc63f692767bd3703b28939a'
LIB='58007bf89bb19826e4c0ec8df582ea546eed6697d5925874609251b0cf00dd3f'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,m):
 if not v:raise ValueError(m)
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--shared',type=Path,required=True);p.add_argument('--positive',type=Path,nargs=2,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve()
 need(not a.out.exists() and len(set([a.shared,*a.positive]))==3,'output and run identity');x=read(b/'inputs.json');need(sha(b/'inputs.json')==PIN and x['library_SHA256']==LIB and x['GPU_dispatches']==0 and sha(b/'application')==x['application_SHA256'],'build identity')
 for n,h in x['frozen'].items():need(sha(b/'src'/n)==h and (n=='client.mm' or sha(HERE/n)==h),'witness source '+n)
 lib=a.library.resolve();lm=read(lib/'manifest.json');need(lm['static_library_SHA256']==sha(lib/'libKeplerMetal.a')==LIB and lm['status']=='PASS','source library')
 for n,h in lm['source_SHA256'].items():need(sha(lib/'src'/n)==h==sha(BRIDGE/'src'/n),'runtime source '+n)
 for n,h in lm['object_SHA256'].items():need(sha(lib/n)==h,'runtime object '+n)
 base=Path(x['base']);base_inputs=read(base/'inputs.json');need(sha(base/'inputs.json')==x['base_inputs_SHA256'] and sha(base/'src/command_ir_dataflow_client.mm')==base_inputs['source_hashes']['src/command_ir_dataflow_client.mm'],'base identity')
 spec=importlib.util.spec_from_file_location('abandon_experiment',HERE/'experiment.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);need((b/'src/client.mm').read_text()==module.transform((base/'src/command_ir_dataflow_client.mm').read_text()),'derived client')
 cpu=json.loads((base/'cpu-lease-contract.stdout').read_text());cases={r['case']:r['PASS'] for r in cpu['cases']};need(cpu['status']=='PASS' and not cpu['GPU_dispatches'] and all(cases.values()) and all(cases.get(n) for n in ['shared_owner_registry','swept_owner_preserves_other','completion_clears_shared_owner','non_native_refused_without_untracking','completion_releases_unowned_lease']),'CPU contract')
 cohort=audit_cohort(a.cohort);need(cohort['status']=='PASS' and cohort['static_library_SHA256']==LIB and cohort['signed_terminal_nonoverlapping_processes']==52,'cohort')
 intervals=[];pids=set();rows=[];proofs=[]
 for d in list((a.cohort/'reusable').iterdir())+list((a.cohort/'regression').iterdir())+[a.shared,*a.positive]:
  m=read(d/'execution/manifest.json');lease=m['GPU_reservation'];need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and not lease['known_signed_processes_live'] and m['pid'] not in pids,'terminal process')
  pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));need(sha(d/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'signed image');subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
  if d in [a.shared,*a.positive]:
   need(sha(d/'application')==m['original_binary_sha256']==x['application_SHA256'],'client executable');inp=read(d/'inputs.json');need(inp['witness_build_inputs_SHA256']==PIN and inp['static_library_SHA256']==LIB and inp['oracle_SHA256']==base_inputs['oracle_SHA256'],'client inputs')
   for n,h in base_inputs['oracle_SHA256'].items():need(sha(d/'oracles'/n)==h,'oracle '+n)
   result=read(d/'results.json');need(result==read(d/'execution/execution.stdout'),'raw result')
   if d==a.shared:need(result['scenario']=='shared_owner' and result['refused'] and result['both_owners_retained'] and not result['producer_submitted'] and not result['system_modified'],'shared-owner refusal')
   else:
    need(result['witness_prepared'] and result['witness_before_restore'] and result['witness_after_restore'] and result['witness_stale_status']==0 and result['witness_completed_refusals']==4 and result['witness_generation']==result['runs'][0]['generation'],'API witness')
    proof=verify(d);need(proof['status']=='PASS' and proof['generations']==[1,2,3,4] and proof['exact_uint32_results']==457728 and proof['guard_bytes']==5052992,'consumer output');proofs.append(proof)
   rows.append({'case':'shared' if d==a.shared else 'positive','pid':m['pid'],'result_SHA256':sha(d/'results.json')})
 intervals.sort();need(all(a<=b for a,b in intervals) and all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'overlapping hosts')
 reference=a.cohort/'reusable/basic'/'outputs';names=[f'trial-{i}-{n}.bin' for i in range(4) for n in ('stage0','stage1','stage2','counter')]
 need(all(p['raw_SHA256'][name]==sha(reference/name) for p in proofs for name in names),'reference differences')
 result={'status':'PASS_EXPERIMENTAL_EXCLUSIVE_PRODUCER','static_library_SHA256':LIB,'build_inputs_SHA256':PIN,'signed_terminal_nonoverlapping_processes':len(intervals),'full_reusable_regression_processes':52,'experimental_positive_processes':2,'shared_owner_refusal_processes':1,'positive_generations':8,'positive_exact_uint32':915456,'positive_guard_bytes':10105984,'reference_matching_stage_counter_files':32,'CPU_mock_cases':len(cases),'full_reusable_regression':{k:v for k,v in cohort.items() if k not in ['cases','regression']},'cases':rows,'scope':'Cooperative explicit producer-only operation; no native driver change, transparent applications, uncoordinated access, cached IMP protection or Metal feature completeness.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result))
if __name__=='__main__':main()
