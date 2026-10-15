#!/usr/bin/env python3
"""Check archived native/factory witnesses; not a no-leak conformance test."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[]
for case in ['native:clean','factory:clean','native:dirty','factory:dirty','native:cancel','factory:cancel','native:bytes','native:bytes_cancel']:
 root=ROOT/'results'/('managed-abandonment-'+case.replace(':','-')+'-20261015');d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 assert d['registry_id']==4294968458 and d['device']=='NVIDIA GeForce GTX 880M'and d['mode']==case and not d['original_commands_submitted']and not d['private_calls']and not d['system_modified']and len(d['runs'])==4
 for i,r in enumerate(d['runs']):
  assert r['trial']==i and not r['original_committed']and not r['abandoned_object_alive']and r['unrelated_empty_command_status']==4
  for k in ['alive_after_pool','alive_after_idle','alive_after_unrelated_submission']:assert r[k]in [0,3]
  if case.endswith(':clean'):assert r['alive_after_pool']==r['alive_after_idle']==r['alive_after_unrelated_submission']==0
  if case.endswith(':dirty')or case.endswith(':bytes')or case.endswith(':bytes_cancel'):assert r['alive_after_pool']==r['alive_after_idle']==r['alive_after_unrelated_submission']==3
 rows.append({'case':case,'directory':str(root),'results_SHA256':sha(root/'results.json'),'executable_SHA256':inp['executable_SHA256'],'observations':d['runs']})
v={'diagnostic_integrity':'PASS','cases':8,'trials':32,'actual_GPU_user_kernels_dispatched':0,'unrelated_empty_submissions':32,'no_leak_conformance_proved':False,'permanent_memory_leak_proved':False,'workaround_implemented':False,'rows':rows,'full_objective_complete':False}
with a.out.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in v.items()if k!='rows'}))
