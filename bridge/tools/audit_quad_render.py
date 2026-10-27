#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck combined quad images, controls and same-runtime regressions."""
from datetime import datetime
from pathlib import Path
import argparse,itertools,json,subprocess,sys
PAIRED=tuple(f'gpu{i}' for i in range(8))+('pipeline_first','draw_first','reverse','no_dispatch','reset','foreign_vertex','foreign_fragment','foreign_index','bad_index_header','bad_vertex_header','bad_pipeline_header','bad_fragment_header')
REGRESSIONS=(('triple','verify_triple_render','gpu','native'),('fragment','verify_fragment_binding_render','gpu','native'),('eight','verify_eight_state_fragment','gpu7','native7'))
def audit(root):
 root=Path(root);quad=[(f'final-{name}','verify_quad_render') for mode in PAIRED for name in (mode,('native'+mode[3:] if mode.startswith('gpu') else mode+'_native'))]+[('final-contracts','verify_quad_render')]+[(f'repeat-gpu{i}','verify_quad_render') for i in range(8)]
 runs=quad+[(f'regression-{kind}-{mode}',module) for kind,module,gpu,native in REGRESSIONS for mode in (gpu,native)];proofs={};entries=[];libs=set()
 for name,module in runs:
  path=root/name;code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))';p=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True);proof=json.loads(p.stdout);assert proof['status']=='PASS';proofs[name]=proof
  libs.add(json.loads((path/'inputs.json').read_text())['static_library_SHA256']);receipt=json.loads((path/'execution/manifest.json').read_text());start=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at']);assert start<=end;entries.append((start,end,receipt['pid'],name))
 entries.sort();assert all(a[1]<=b[0] for a,b in zip(entries,entries[1:])) and len({e[2] for e in entries})==len(entries) and len(libs)==1
 image=lambda name:(root/name/'outputs/image.bin').read_bytes()
 for m in PAIRED:assert image('final-'+m)==image('final-'+('native'+m[3:] if m.startswith('gpu') else m+'_native')),m
 imgs=[image(f'final-gpu{i}') for i in range(8)];assert all(a!=b for a,b in itertools.combinations(imgs,2))
 for i in range(8):assert imgs[i]==image(f'repeat-gpu{i}')
 assert imgs[7]==image('final-pipeline_first')==image('final-draw_first')==image('final-contracts')
 assert imgs[0]==image('final-reverse')==image('final-no_dispatch')
 assert all(image('final-reset')==image('final-'+m) for m in ('foreign_vertex','foreign_fragment','foreign_index','bad_index_header','bad_vertex_header','bad_pipeline_header','bad_fragment_header'))
 for kind,_,gpu,native in REGRESSIONS:assert image(f'regression-{kind}-{gpu}')==image(f'regression-{kind}-{native}')
 primary=[proofs[name] for name,_ in quad]
 return {'status':'PASS','quad_hosts':len(quad),'same_runtime_regression_hosts':len(runs)-len(quad),'serialized_hosts':len(entries),'quad_float_channels':sum(p['checked_float_channels'] for p in primary),'texture_float_channels':sum(p['texture_channels'] for p in primary),'index_rows_checked':sum(p['index_rows_checked'] for p in primary),'vertex_rows_checked':sum(p['vertex_rows_checked'] for p in primary),'pipeline_rows_checked':sum(p['pipeline_rows_checked'] for p in primary),'fragment_rows_checked':sum(p['fragment_rows_checked'] for p in primary),'native_image_pairs':len(PAIRED),'repeat_image_pairs':8,'eight_distinct_images':True,'maximum_cpu_error':max(p['maximum_error'] for p in primary),'runtime_sha256':next(iter(libs)),'scope':'adapted client; no transparent Metal or performance claim'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
