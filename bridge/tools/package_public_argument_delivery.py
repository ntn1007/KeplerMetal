#!/usr/bin/env python3
"""Package the final candidate and complete selected raw evidence, not caches."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();files=set();empty=set()
def add(p):
 p=Path(p).resolve();p.relative_to(ROOT)
 if p.is_dir():
  for f in p.rglob('*'):
   if'__pycache__'in f.parts:continue
   if f.is_file():files.add(f)
   elif f.is_dir()and not any(f.iterdir()):empty.add(f)
 else:assert p.is_file();files.add(p)
progress=ROOT/'results/argument-binding-runtime-progress-20261015';r=json.loads((progress/'qualification-receipt.json').read_text());assert r['candidate_scenarios']==192
for e in json.loads((progress/'source-snapshot-final.json').read_text())['files']:assert sha(ROOT/e['path'])==e['SHA256'];add(ROOT/e['path'])
for name in ['argument-binding-runtime-progress-20261015','argument-binding-runtime-library-build-20261015-06','public-argument-client-final-build-20261015','public-argument-legacy-final-build-20261015','public-argument-refusals-final-build-20261015','public-argument-lifetime-regression-build-20261015','public-argument-final-qualification-20261015','public-argument-final-reuse-20261015','public-argument-final-refusals-20261015','public-argument-final-legacy-basic-20261015','public-argument-M1-final-return-20261015','public-argument-M1-source-20261015-02','command-ir-dataflow-client-build-20261015-04','command-ir-lifetime-final-client-build-20261015']:add(ROOT/'results'/name)
for pattern in ['public-argument-final-dataflow-*','public-argument-final-lifetime-*']:
 for p in(ROOT/'results').glob(pattern):add(p)
for n in ['public-argument-M1-source-20261015-02-transfer.json','public-argument-M1-source-20261015-02-delivery.json','hardware-coverage.json']:add(ROOT/'results'/n)
for n in ['collect_m1_dataflow_reference.py','transfer_m1_source_directory.py','package_public_argument_delivery.py']:add(ROOT/'tools'/n)
add(ROOT/'ARGUMENTS_ICB_PUBLICS_2026-10-15.txt')
lm=json.loads((ROOT/'results/argument-binding-runtime-library-build-20261015-06/manifest.json').read_text())
for p,h in lm['reused_object_SHA256'].items():assert sha(p)==h;add(p)
add(ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK/BUILD_MANIFEST.json')
mp=progress/'PACKAGE_MANIFEST.json';manifest={'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(files)],'empty_directories':[str(p.relative_to(ROOT))for p in sorted(empty)],'source_snapshot_SHA256':r['source_snapshot_SHA256'],'candidate_library_SHA256':r['candidate_library_SHA256'],'objective_complete':False}
with mp.open('x')as f:json.dump(manifest,f,indent=2);f.write('\n')
archive=ROOT/'KEPLERMETAL_ARGUMENTS_ICB_PUBLICS_2026-10-15.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
 for p in sorted(files):z.write(p,'bridge/'+str(p.relative_to(ROOT)))
 for p in sorted(empty):z.writestr('bridge/'+str(p.relative_to(ROOT))+'/',b'')
 z.write(mp,'bridge/'+str(mp.relative_to(ROOT)))
with zipfile.ZipFile(archive)as z:
 assert len(z.namelist())==len(set(z.namelist()))==len(files)+len(empty)+1
 for e in manifest['files']:
  data=z.read('bridge/'+e['path']);assert len(data)==e['bytes']and hashlib.sha256(data).hexdigest()==e['SHA256']
receipt={'status':'PASS','path':str(archive),'SHA256':sha(archive),'bytes':archive.stat().st_size,'files':len(files)+1,'empty_directories':len(empty),'all_manifest_files_rehashed':True,'objective_complete':False};(progress/'package-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
