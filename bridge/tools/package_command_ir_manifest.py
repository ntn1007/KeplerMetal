#!/usr/bin/env python3
"""Freeze this milestone and check every ZIP entry without executing binaries."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/command-ir-manifest-qualification-20261015'
ARCHIVE=ROOT/'KEPLERMETAL_COMMANDES_GPU_GRILLE_2026-10-15.zip'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=json.loads((OUT/'qualification-receipt.json').read_text());assert d['status']=='PASS'and not d['objective_complete'];selected=set()
def add(p):
 p=Path(p);p.relative_to(ROOT)
 if p.is_dir():
  for f in p.rglob('*'):
   if f.is_file()and not f.is_symlink()and f.suffix not in ['.pyc','.o']and '__pycache__'not in f.parts:selected.add(f)
 elif p.is_file()and not p.is_symlink():selected.add(p)
 else:raise FileNotFoundError(p)
for pattern in ['command-ir-manifest-*','command-ir-aligned-threads-*','command-ir-general-*']:
 for p in(ROOT/'results').glob(pattern):
  if p.name=='command-ir-manifest-legacy-sdk-20261015':
   add(p/'bindings-client');add(p/'commands.json');add(p/'build.stdout');add(p/'build.stderr')
  else:add(p)
for p in [ROOT/'src',ROOT/'tools',ROOT/'results/hardware-coverage.json',ROOT/'COMMANDES_GPU_GRILLE_CB0_2026-10-15.txt',ROOT/'results/pipeline-profile-references/cla0c0qmd.h']:add(p)
entries=[{'path':'bridge/'+str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(selected)]
manifest={'files':entries,'Git_branch':'main','Git_commit':None,'source_snapshot_SHA256':d['source_snapshot_SHA256'],'library_SHA256':d['library_SHA256'],'job_ids':[],'objective_complete':False,'system_modified':False,'performance_benchmark':False,'scope':'Bounded L2 native-consumer extension, optional shared memory, uniform1D thread/group dispatch; not installed driver/transparent Metal'}
with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
 for p in sorted(selected):z.write(p,'bridge/'+str(p.relative_to(ROOT)))
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(ARCHIVE)as z:
 assert len(z.namelist())==len(entries)+1 and len(set(z.namelist()))==len(z.namelist())
 for e in entries:
  assert '..'not in Path(e['path']).parts and not e['path'].startswith('/')
  b=z.read(e['path']);assert len(b)==e['bytes']and hashlib.sha256(b).hexdigest()==e['SHA256']
 frozen=json.loads(z.read('bridge/results/command-ir-manifest-qualification-20261015/qualification-receipt.json'));assert frozen==d
 snapshot=json.loads(z.read('bridge/results/command-ir-manifest-qualification-20261015/source-snapshot.json'))
 for e in snapshot['files']:assert hashlib.sha256(z.read('bridge/'+e['path'])).hexdigest()==e['SHA256']
receipt={'status':'PASS','archive':str(ARCHIVE),'SHA256':sha(ARCHIVE),'bytes':ARCHIVE.stat().st_size,'files_including_manifest':len(entries)+1,'all_entry_SHA256_verified':True,'extracted_binaries_executed':False,'objective_complete':False,'job_ids':[]}
with(OUT/'packet-delivery.json').open('x')as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt,indent=2))
