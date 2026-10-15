#!/usr/bin/env python3
"""Freeze current lifetime evidence and exact built prerequisites for reproduction."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/command-ir-lifetime-progress-20261015';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();r=json.loads((OUT/'qualification-receipt.json').read_text());assert r['status']=='PASS'and not r['objective_complete'];selected=set()
def add(p):
 p=Path(p);p.relative_to(LAB)
 if p.is_dir():
  for f in p.rglob('*'):
   if f.is_file()and not f.is_symlink()and f.suffix!='.pyc'and'__pycache__'not in f.parts:selected.add(f)
 elif p.is_file()and not p.is_symlink():selected.add(p)
 else:raise FileNotFoundError(p)
for p in(ROOT/'results').glob('command-ir-lifetime-*'):add(p)
for p in [ROOT/'src',ROOT/'tools',ROOT/'COMMANDES_GPU_DUREE_VIE_2026-10-15.txt',ROOT/'results/hardware-coverage.json',ROOT/'results/command-ir-dataflow-library-build-20261015-03',ROOT/'results/command-ir-dataflow-materializer-build-20261015-02',ROOT/'results/command-ir-dataflow-compiler-build-20261015',ROOT/'results/command-ir-dataflow-client-build-20261015-04',ROOT/'results/command-ir-dataflow-progress-20261015/qualification-receipt.json',ROOT/'results/command-ir-dataflow-progress-20261015/packet-delivery.json',ROOT/'results/command-ir-dataflow-progress-20261015/qualification-source-snapshot.json',ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK',ROOT/'results/gpu-command-ir-host-build-20261015-04/command_ir_carrier.metallib']:add(p)
for kind in ['grid3d','v1','v2-three','v2-combined']:add(ROOT/'results'/('command-ir-dataflow-'+kind+'-client-20261015'))
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(selected)];manifest={'files':entries,'Git_branch':'main','Git_commit':None,'source_snapshot_SHA256':r['source_snapshot_SHA256'],'library_SHA256':r['library_SHA256'],'objective_complete':False,'job_ids':[],'scope':'L2 SDK/caller ownership; exact prebuilt runtime/compiler and preserved diagnostics. Prior core129qualification referenced at same library hash, not rerun. Full third-party source rebuild and installed-driver upgrade not included.'};archive=ROOT/'KEPLERMETAL_DUREE_VIE_2026-10-15.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
 for p in sorted(selected):z.write(p,str(p.relative_to(LAB)))
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive)as z:
 assert len(z.namelist())==len(entries)+1 and len(set(z.namelist()))==len(z.namelist())
 for e in entries:
  assert not e['path'].startswith('/')and'..'not in Path(e['path']).parts;b=z.read(e['path']);assert len(b)==e['bytes']and hashlib.sha256(b).hexdigest()==e['SHA256']
 assert json.loads(z.read('bridge/results/command-ir-lifetime-progress-20261015/qualification-receipt.json'))==r
 for e in json.loads(z.read('bridge/results/command-ir-lifetime-progress-20261015/source-snapshot.json'))['files']:assert hashlib.sha256(z.read('bridge/'+e['path'])).hexdigest()==e['SHA256']
delivery={'status':'PASS','path':str(archive),'SHA256':sha(archive),'bytes':archive.stat().st_size,'files_including_manifest':len(entries)+1,'all_entry_SHA256_verified':True,'extracted_binaries_executed':False,'objective_complete':False,'job_ids':[]}
with(OUT/'packet-delivery.json').open('x')as f:json.dump(delivery,f,indent=2);f.write('\n')
print(json.dumps(delivery,indent=2))
