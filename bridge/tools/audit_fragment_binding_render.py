#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently recheck serial fragment and same-runtime regression evidence."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

MODES=('gpu','native','no_dispatch','no_dispatch_native','disabled','disabled_native','foreign','foreign_native','reverse','reverse_native','missing','missing_native','bad_header','bad_header_native','contracts')
REGRESSIONS=(('triple',('gpu','native','contracts','foreign_vertex'),'verify_triple_render'),('pipeline',('gpu','native','contracts'),'verify_pipeline_binding_integrated'))

def audit(root):
 root=Path(root); entries=[]; libraries=set(); proofs={}; regression=[]
 runs=[(f'cohort-{cohort:02}-{mode}','verify_fragment_binding_render',(cohort,mode)) for cohort in (1,2) for mode in MODES]
 runs += [(f'regression-{prefix}-{mode}',module,None) for prefix,modes,module in REGRESSIONS for mode in modes]
 for name,module,key in runs:
  path=root/name; code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
  p=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True); proof=json.loads(p.stdout); assert proof['status']=='PASS'
  if key is None: regression.append(proof)
  else: proofs[key]=proof
  libraries.add(json.loads((path/'inputs.json').read_text())['static_library_SHA256'])
  receipt=json.loads((path/'execution/manifest.json').read_text()); start=datetime.fromisoformat(receipt['started_at']); end=datetime.fromisoformat(receipt['completed_at']); assert start<=end
  entries.append((start,end,receipt['pid'],name))
 entries.sort(); assert all(a[1]<=b[0] for a,b in zip(entries,entries[1:])); assert len({x[2] for x in entries})==len(entries) and len(libraries)==1
 def image(c,m):return (root/f'cohort-{c:02}-{m}'/'outputs/image.bin').read_bytes()
 for c in (1,2):
  for m in ('gpu','no_dispatch','disabled','foreign','reverse','missing','bad_header'):
   assert image(c,m)==image(c,'native' if m=='gpu' else m+'_native'),(c,m)
  assert image(c,'gpu')==image(c,'contracts')
  assert image(c,'no_dispatch')==image(c,'disabled')==image(c,'reverse')
  assert image(c,'gpu')!=image(c,'no_dispatch')
  assert image(c,'foreign')==image(c,'missing')==image(c,'bad_header')
 for m in MODES: assert image(1,m)==image(2,m),m
 for prefix,_,_ in REGRESSIONS: assert (root/f'regression-{prefix}-gpu/outputs/image.bin').read_bytes()==(root/f'regression-{prefix}-native/outputs/image.bin').read_bytes()
 return {'status':'PASS','fragment_hosts':len(proofs),'regression_hosts':len(regression),'serialized_hosts':len(entries),'fragment_float_channels':sum(p['checked_float_channels'] for p in proofs.values()),'texture_float_channels':sum(p['texture_channels'] for p in proofs.values()),'native_image_pairs':14,'repeat_image_pairs':15,'expected_alias_refusals':2,'maximum_cpu_error':max(p['maximum_error'] for p in proofs.values()),'runtime_sha256':next(iter(libraries)),'scope':'adapted client; no transparent Metal or performance claim'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
