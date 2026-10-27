#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck eight-state transitions, sixteen candidates and same-runtime regressions."""
from datetime import datetime
from pathlib import Path
import argparse,itertools,json,subprocess,sys

EIGHT=tuple(f'{p}{i}' for i in range(8) for p in ('gpu','native'))+('foreign','foreign_native','contracts')
SIXTEEN=('gpu0','native0','gpu3','native3','gpu7','native7','foreign','foreign_native','contracts')
REGRESSIONS=(('triple','verify_triple_render'),('fragment','verify_fragment_binding_render'))

def audit(root):
 root=Path(root);runs=[('final-'+m,'verify_eight_state_fragment') for m in EIGHT]+[('sixteen-'+m,'verify_sixteen_slot_fragment') for m in SIXTEEN]+[(f'regression-{kind}-{mode}',module)for kind,module in REGRESSIONS for mode in ('gpu','native')]
 proofs={};entries=[];libraries=set()
 for name,module in runs:
  path=root/name;code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
  p=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True);proof=json.loads(p.stdout);assert proof['status']=='PASS';proofs[name]=proof
  libraries.add(json.loads((path/'inputs.json').read_text())['static_library_SHA256'])
  receipt=json.loads((path/'execution/manifest.json').read_text());start=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at']);assert start<=end;entries.append((start,end,receipt['pid'],name))
 entries.sort();assert all(a[1]<=b[0] for a,b in zip(entries,entries[1:])) and len({e[2]for e in entries})==len(entries) and len(libraries)==1
 image=lambda name:(root/name/'outputs/image.bin').read_bytes()
 eight=[image('final-gpu'+str(i)) for i in range(8)];assert all(a!=b for a,b in itertools.combinations(eight,2))
 for i in range(8):assert eight[i]==image('final-native'+str(i))
 assert image('final-foreign')==image('final-foreign_native') and image('final-contracts')==eight[7]
 for i in (0,3,7):assert image('sixteen-gpu'+str(i))==image('sixteen-native'+str(i))==eight[(i+1)%8]
 assert image('sixteen-foreign')==image('sixteen-foreign_native')==image('final-foreign')
 assert image('sixteen-contracts')==eight[0]
 for kind,_ in REGRESSIONS:assert image(f'regression-{kind}-gpu')==image(f'regression-{kind}-native')
 return {'status':'PASS','eight_state_hosts':len(EIGHT),'sixteen_candidate_hosts':len(SIXTEEN),'same_runtime_regression_hosts':4,'serialized_hosts':len(entries),'eight_state_float_channels':sum(proofs['final-'+m]['checked_float_channels'] for m in EIGHT),'sixteen_float_channels':sum(proofs['sixteen-'+m]['checked_float_channels'] for m in SIXTEEN),'texture_float_channels':sum(proofs['final-'+m]['texture_channels'] for m in EIGHT)+sum(proofs['sixteen-'+m]['texture_channels'] for m in SIXTEEN),'sixteen_candidate_witnesses':sum(proofs['sixteen-'+m]['materializer_candidates_checked'] for m in SIXTEEN),'eight_distinct_images':True,'native_image_pairs':13,'maximum_cpu_error':max(p['maximum_error'] for p in proofs.values()),'runtime_sha256':next(iter(libraries)),'scope':'adapted client; no transparent Metal, combined quad GPU execution or performance claim'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
