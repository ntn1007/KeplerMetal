#!/usr/bin/env python3
"""Freeze qualified XYZ/IR evidence and the separate public-glue comparison."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
OUT=ROOT/'results/command-ir-multidimensional-progress-20261015'
ARCHIVE=ROOT/'KEPLERMETAL_IR_XYZ_2026-10-15.zip'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt=json.loads((OUT/'qualification-receipt.json').read_text());assert receipt['status']=='PASS'and not receipt['objective_complete'];selected=set()
def add(p):
 p=Path(p);p.relative_to(LAB)
 if p.is_dir():
  for f in p.rglob('*'):
   if f.is_file()and not f.is_symlink()and f.suffix not in ['.o','.pyc']and'__pycache__'not in f.parts:selected.add(f)
 elif p.is_file()and not p.is_symlink():selected.add(p)
 else:raise FileNotFoundError(p)
for pattern in ['command-ir-v2-*','command-ir-grid3d-*','command-ir-multidimensional-*']:
 for p in(ROOT/'results').glob(pattern):add(p)
for p in [ROOT/'src',ROOT/'tools',ROOT/'results/hardware-coverage.json',ROOT/'COMMANDES_GPU_XYZ_IR_V2_2026-10-15.txt']:add(p)
research=LAB/'driver-research-2026-10-13'
for p in [research/'reports/FREEBSD_LINUX_470_256_02_2026-10-15.txt',research/'comparison/FreeBSD-Linux-470.256.02-public-headers',research/'comparison/FreeBSD-Linux-470.256.02-recheck-20261015',research/'extracted/FreeBSD-470.256.02-public-sources',research/'archives/freebsd-470.256.02-manifest.json',research/'archives/NVIDIA-FreeBSD-x86_64-470.256.02.tar.xz.sha256sum',research/'tools/compare_freebsd_linux_470.py']:add(p)
for p in json.loads((research/'comparison/FreeBSD-Linux-470.256.02-public-headers/pairs.json').read_text())['pairs']:add(research/p['Linux'])
add(research/'extracted/470.256.02/kernel/nvidia/os-interface.c')
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(selected)]
manifest={'files':entries,'Git_branch':'main','Git_commit':None,'source_snapshot_SHA256':receipt['source_snapshot_SHA256'],'library_SHA256':receipt['library_SHA256'],'job_ids':[],'objective_complete':False,'system_modified':False,'performance_benchmark':False,'scope':'L2 uniform XYZ command IR and reflected3/4buffer consumers; separate static FreeBSD/Linux comparison. Not an installed driver or complete Metal support.'}
with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
 for p in sorted(selected):z.write(p,str(p.relative_to(LAB)))
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(ARCHIVE)as z:
 assert len(z.namelist())==len(entries)+1 and len(set(z.namelist()))==len(z.namelist())
 for e in entries:
  assert'..'not in Path(e['path']).parts and not e['path'].startswith('/');b=z.read(e['path']);assert len(b)==e['bytes']and hashlib.sha256(b).hexdigest()==e['SHA256']
 frozen=json.loads(z.read('bridge/results/command-ir-multidimensional-progress-20261015/qualification-receipt.json'));assert frozen==receipt
 snapshot=json.loads(z.read('bridge/results/command-ir-multidimensional-progress-20261015/source-snapshot.json'))
 for e in snapshot['files']:assert hashlib.sha256(z.read('bridge/'+e['path'])).hexdigest()==e['SHA256']
delivery={'status':'PASS','path':str(ARCHIVE),'SHA256':sha(ARCHIVE),'bytes':ARCHIVE.stat().st_size,'files_including_manifest':len(entries)+1,'all_entry_SHA256_verified':True,'extracted_binaries_executed':False,'objective_complete':False,'job_ids':[]}
with(OUT/'packet-delivery.json').open('x')as f:json.dump(delivery,f,indent=2);f.write('\n')
print(json.dumps(delivery,indent=2))
