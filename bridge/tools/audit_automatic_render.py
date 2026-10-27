#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck opt-in ordinary-client evidence and scoped-runtime regressions."""
from datetime import datetime
from pathlib import Path
import argparse,json,subprocess,sys
MODES=('auto','auto_multiple','direct','auto_direct','no_auto','unsupported','manual','guard_restore')
REG=(('quad-gpu7','verify_quad_render'),('quad-native7','verify_quad_render'),('fragment-gpu','verify_fragment_binding_render'),('fragment-native','verify_fragment_binding_render'),('compute-basic','verify_command_ir_dataflow'),('compute-encoder_reuse','verify_command_ir_dataflow'),('compute-contracts','verify_native_library_contracts'))

def audit(root):
 root=Path(root);runs=[(f'accepted-{m}-{n:02}','verify_automatic_render')for n in (1,2)for m in MODES]+[(f'regression-{name}',module)for name,module in REG];proofs={};intervals=[];libs=set();clienthash=set()
 for name,module in runs:
  path=root/name;code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))';p=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True);proof=json.loads(p.stdout);assert proof['status']=='PASS';proofs[name]=proof
  inputs=json.loads((path/'inputs.json').read_text());libs.add(inputs['static_library_SHA256'])
  receipt=json.loads((path/'execution/manifest.json').read_text());assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status'] and receipt['GPU_reservation']['state']=='terminal';start=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at']);assert start<=end;intervals.append((start,end,receipt['pid'],name))
  if module=='verify_automatic_render':
   clienthash.add(inputs['frozen']['assets/client.dylib']);plugin=path/'assets/client.dylib'
   symbols=subprocess.run(['nm','-u',str(plugin)],capture_output=True,text=True,check=True).stdout;assert 'Kepler' not in symbols and 'KPCPU' not in symbols
   subprocess.run(['codesign','--verify','--strict',str(plugin)],capture_output=True,text=True,check=True)
   deps=subprocess.run(['otool','-L',str(plugin)],capture_output=True,text=True,check=True).stdout.splitlines()[2:];assert deps and all(line.strip().startswith(('/System/Library/Frameworks/','/usr/lib/')) for line in deps),deps
 intervals.sort();assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])) and len({e[2] for e in intervals})==len(intervals) and len(libs)==1 and len(clienthash)==1
 image=lambda m,n,i=0:(root/f'accepted-{m}-{n:02}'/'outputs'/f'frame-{i}.bin').read_bytes()
 for n in (1,2):
  direct=image('direct',n);assert all(image(m,n)==direct for m in ('auto','auto_direct','manual','guard_restore'))
  assert all(image('auto_multiple',n,i)==direct for i in range(3));assert image('no_auto',n)!=direct
 for m in MODES:
  for i in range(3 if m=='auto_multiple' else 1):assert image(m,1,i)==image(m,2,i),(m,i)
 for kind,gpu,native in [('quad','gpu7','native7'),('fragment','gpu','native')]:assert (root/f'regression-{kind}-{gpu}/outputs/image.bin').read_bytes()==(root/f'regression-{kind}-{native}/outputs/image.bin').read_bytes()
 main=[proofs[f'accepted-{m}-{n:02}']for n in (1,2)for m in MODES]
 return {'status':'PASS','ordinary_client_hosts':len(main),'regression_hosts':len(REG),'serialized_hosts':len(intervals),'frames':sum(p['frames'] for p in main),'checked_float_channels':sum(p['checked_float_channels'] for p in main),'ordinary_client_binary_sha256':next(iter(clienthash)),'same_runtime_sha256':next(iter(libs)),'compute_regression_kinds':['library basic','library encoder_reuse','library_contracts pointer'],'supported_ICB_executions':sum(p['frames'] for p in main if p['ICB_executed']),'guarded_unsupported_passes':sum(p['unsupported_pass_guarded_native_draw'] for p in main),'unmodified_existing_app':False,'performance_benchmark':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
