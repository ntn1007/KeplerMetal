#!/usr/bin/env python3
"""Freeze exact dataflow evidence, current runtime and its legacy regressions."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/command-ir-dataflow-progress-20261015';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=json.loads((OUT/'qualification-receipt.json').read_text());assert r['status']=='PASS'and not r['objective_complete'];selected=set()
def add(p,object_file=False):
 p=Path(p);p.relative_to(LAB)
 if p.is_dir():
  for f in p.rglob('*'):
   if f.is_file()and not f.is_symlink()and f.suffix not in ['.o','.pyc']and'__pycache__'not in f.parts:selected.add(f)
 elif p.is_file()and not p.is_symlink()and(p.suffix!='.o'or object_file):selected.add(p)
 else:raise FileNotFoundError(p)
for p in(ROOT/'results').glob('command-ir-dataflow-*'):add(p)
for p in [ROOT/'src',ROOT/'tools',ROOT/'results/hardware-coverage.json',ROOT/'COMMANDES_GPU_FLUX_NATIFS_2026-10-15.txt',ROOT/'results/command-ir-grid3d-M1-return-20261015',ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK',ROOT/'results/gpu-command-ir-host-build-20261015-04/command_ir_carrier.metallib']:add(p)
for e in json.loads((ROOT/'results/command-ir-dataflow-primer-controls-20261015/receipt.json').read_text())['streams']:add(ROOT/e['path'])
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(selected)]
manifest={'files':entries,'Git_branch':'main','Git_commit':None,'source_snapshot_SHA256':r['source_snapshot_SHA256'],'library_SHA256':r['library_SHA256'],'objective_complete':False,'system_modified':False,'performance_benchmark':False,'job_ids':[],'scope':'L2 bounded GPU command dataflow. Exact built compiler/runtime and native assets included for client reproduction; full third-party compiler source rebuild is a separate prerequisite.'}
archive=ROOT/'KEPLERMETAL_FLUX_NATIFS_2026-10-15.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
 for p in sorted(selected):z.write(p,str(p.relative_to(LAB)))
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive)as z:
 assert len(z.namelist())==len(entries)+1 and len(set(z.namelist()))==len(z.namelist())
 for e in entries:
  assert not e['path'].startswith('/')and'..'not in Path(e['path']).parts;b=z.read(e['path']);assert len(b)==e['bytes']and hashlib.sha256(b).hexdigest()==e['SHA256']
 assert json.loads(z.read('bridge/results/command-ir-dataflow-progress-20261015/qualification-receipt.json'))==r
 for e in json.loads(z.read('bridge/results/command-ir-dataflow-progress-20261015/qualification-source-snapshot.json'))['files']:assert hashlib.sha256(z.read('bridge/'+e['path'])).hexdigest()==e['SHA256']
delivery={'status':'PASS','path':str(archive),'SHA256':sha(archive),'bytes':archive.stat().st_size,'files_including_manifest':len(entries)+1,'all_entry_SHA256_verified':True,'extracted_binaries_executed':False,'objective_complete':False,'job_ids':[]}
with(OUT/'packet-delivery.json').open('x')as f:json.dump(delivery,f,indent=2);f.write('\n')
print(json.dumps(delivery,indent=2))
