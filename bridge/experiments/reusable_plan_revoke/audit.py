#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-audit one refused pilot and three real-plan processes, without GPU work."""
import argparse, hashlib, importlib.util, json, subprocess, sys
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
PIN='09995a149e37ef707381507dbc153219a145ad1ee09802096c07dad3b7cd20ec'
LIB='0275b13126a63372518b85fcd8e546af0cae0b593ceb37cadc5574b4a765d85a'
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--pilot-build',type=Path,required=True);p.add_argument('--runs',nargs=4,type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(not a.out.exists() and len(set(a.runs))==4,'fresh output and four distinct paths');b=a.build.resolve();x=read(b/'inputs.json');need(sha(b/'inputs.json')==PIN and x['library_SHA256']==LIB and x['GPU_dispatches']==0 and sha(b/'application')==x['application_SHA256'],'build')
 for n,h in x['frozen'].items():need(sha(b/'src'/n)==h and (n=='client.mm' or sha(HERE/n)==h),'frozen '+n)
 base=Path(x['base']);need(sha(base/'inputs.json')==x['base_inputs_SHA256'],'base');base_inputs=read(base/'inputs.json')
 need(sha(base/'src/command_ir_dataflow_client.mm')==base_inputs['source_hashes']['src/command_ir_dataflow_client.mm'],'base client')
 spec=importlib.util.spec_from_file_location('plan_witness_experiment',HERE/'experiment.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 need((b/'src/client.mm').read_text()==module.transform((base/'src/command_ir_dataflow_client.mm').read_text()),'derived client')
 old=read(a.pilot_build/'inputs.json');need(sha(a.pilot_build/'application')==old['application_SHA256'] and sha(a.pilot_build/'src/plan_probe.inc')==old['frozen']['plan_probe.inc'] and 'setValue:nil forKey:@"producerBuffer"' not in (a.pilot_build/'src/plan_probe.inc').read_text(),'pilot identity')
 intervals=[];pids=set();proofs=[];rows=[]
 for idx,path in enumerate(a.runs):
  d=path.resolve();m=read(d/'execution/manifest.json');l=m['GPU_reservation'];expected=32 if idx==1 else 0
  need(m['exit_code']==expected and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and l['state']=='terminal' and l['exit_code']==expected and l['child_PID']==m['pid'] and not l['known_signed_processes_live'] and m['pid'] not in pids,'process terminal')
  pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
  expected_binary=old['application_SHA256'] if idx==1 else (read(base/'inputs.json')['executables']['reusable'] if idx==0 else x['application_SHA256'])
  need(sha(d/'application')==m['original_binary_sha256']==expected_binary and sha(d/'execution/application')==m['signed_binary_sha256']==l['signed_binary_sha256'],'binary identity')
  subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
  result=read(d/'execution/execution.stdout')
  if idx==1:
   need(result['failure']=='reserve' and 'Reusable producer reservation is unavailable' in result['error'],'pilot refusal');rows.append({'case':'lease-only-pilot','exit':32,'result_SHA256':sha(d/'execution/execution.stdout')});continue
  need(result==read(d/'results.json'),'raw result')
  inp=read(d/'inputs.json');need(inp['static_library_SHA256']==LIB and inp['source_build_inputs_SHA256']==x['base_inputs_SHA256'] and inp['oracle_SHA256']==base_inputs['oracle_SHA256'],'input identity')
  for n,h in base_inputs['oracle_SHA256'].items():need(sha(d/'oracles'/n)==h,'oracle identity '+n)
  if idx>=2:need(inp['witness_build_inputs_SHA256']==PIN and result['witness_prepared'] and result['witness_before_restore'] and result['witness_after_restore'] and result['witness_stale_status']==0 and result['witness_generation']==result['runs'][0]['generation'],'witness')
  sys.path.insert(0,str(d/'oracles'));import verify_command_ir_dataflow as oracle
  proof=oracle.verify(d);sys.path.pop(0)
  need(proof['status']=='PASS' and proof['generations']==[1,2,3,4] and proof['exact_uint32_results']==457728 and proof['guard_bytes']==5052992,'GPU numerical verification')
  proofs.append(proof);rows.append({'case':'native-control' if idx==0 else 'manual-witness','result_SHA256':sha(d/'results.json'),'pid':m['pid']})
 intervals.sort();need(all(s<=e for s,e in intervals) and all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'overlap')
 names=[f'trial-{i}-{n}.bin' for i in range(4) for n in ('stage0','stage1','stage2','counter')]
 need(all(proofs[0]['raw_SHA256'][n]==p['raw_SHA256'][n] for p in proofs[1:] for n in names),'control readbacks differ')
 receipt={'status':'PASS_BOUNDED_REAL_PLAN_WITNESS','build_inputs_SHA256':PIN,'library_SHA256':LIB,'terminal_nonoverlapping_processes':4,'pilot_refused_exit':32,'native_control_processes':1,'witness_processes':2,'generations_per_process':4,'witness_exact_uint32_values':915456,'witness_guard_bytes':10105984,'control_witness_matching_stage_counter_files':32,'scope':'Manual test-only pending removal and producerBuffer reset after own-process instance revocation; not an exposed cancellation API, automatic factory restoration, concurrent safety or driver modification.','cases':rows}
 with a.out.open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
