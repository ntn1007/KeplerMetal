#!/usr/bin/env python3
"""Package exact sources and bounded proofs, without installed binaries/secrets."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--progress',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);args=p.parse_args();folder=args.progress.resolve();folder.relative_to(ROOT/'results');archive=args.archive.resolve();archive.relative_to(ROOT)
paths=set();empty_directories=set()
def add(p):
 p=Path(p).resolve();p.relative_to(ROOT)
 if p.is_dir():
  for f in p.rglob('*'):
   if f.is_file()and'__pycache__'not in f.parts:paths.add(f)
   elif f.is_dir()and'__pycache__'not in f.parts and not any(f.iterdir()):empty_directories.add(f)
 else:assert p.is_file();paths.add(p)
prefixes=['graphics-factory-lifetime-','graphics-arguments-progress-','managed-abandonment-','argument-encoder-']
for p in(ROOT/'results').iterdir():
 if any(p.name.startswith(x)for x in prefixes):add(p)
receipt=json.loads((folder/'qualification-receipt.json').read_text());snapshot=json.loads((folder/'source-snapshot.json').read_text())
for e in snapshot['files']:assert sha(ROOT/e['path'])==e['SHA256'];add(ROOT/e['path'])
for name in ['run_command_ir_runtime.py','lab_gpu_reservation.py','transfer_m1_source_directory.py','verify_graphics_factory_lifetime_phase.py','verify_managed_abandonment_probe.py','package_graphics_arguments_phase.py']:add(ROOT/'tools'/name)
add(ROOT/'RESSOURCES_ARGUMENTS_METAL_2026-10-15.txt');add(ROOT/'results/hardware-coverage.json')
for name in ['command-ir-dataflow-library-build-20261015-03','command-ir-dataflow-client-build-20261015-04']:add(ROOT/'results'/name)
for name in ['run_sdk_host.py','lab_gpu_reservation.py']:add(ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK/runtime'/name)
v=ROOT/'results/vertex-io-qualified';t=ROOT/'results/tessellation-capture-final';r=ROOT/'results/resource-final'
for p in [v/'manifest.json',v/'vertex_io_carrier.metallib',t/'manifest.json',t/'carrier.metallib',t/'capture.sass',r/'manifest.json',r/'resource_carrier.metallib']:add(p)
vm=json.loads((v/'manifest.json').read_text())
for row in vm['shaders']:
 if row['kind']in ['vertex','flat']:assert sha(ROOT/row['path'])==row['sha256'];add(ROOT/row['path'])
manifest={'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(paths)],'empty_directories':[str(p.relative_to(ROOT))for p in sorted(empty_directories)],'scope':'Selected sources, frozen binaries and new/referenced proofs. No installed macOS binaries, SSH configuration or tokens.','source_snapshot_SHA256':receipt['source_snapshot_SHA256'],'objective_complete':False}
mp=folder/'PACKAGE_MANIFEST.json'
with mp.open('x')as f:json.dump(manifest,f,indent=2);f.write('\n')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
 for p in sorted(paths):z.write(p,'bridge/'+str(p.relative_to(ROOT)))
 for p in sorted(empty_directories):z.writestr('bridge/'+str(p.relative_to(ROOT))+'/',b'')
 z.write(mp,'bridge/'+str(mp.relative_to(ROOT)))
with zipfile.ZipFile(archive)as z:
 names=z.namelist();assert len(names)==len(set(names))==len(paths)+len(empty_directories)+1
 for e in manifest['files']:
  data=z.read('bridge/'+e['path']);assert len(data)==e['bytes']and hashlib.sha256(data).hexdigest()==e['SHA256']
pack={'status':'PASS','path':str(archive),'SHA256':sha(archive),'bytes':archive.stat().st_size,'files':len(paths)+1,'empty_directories':len(empty_directories),'every_manifest_file_rehashed_from_ZIP':True,'manifest_SHA256':sha(mp),'objective_complete':False}
(folder/'package-verification.json').write_text(json.dumps(pack,indent=2)+'\n');print(json.dumps(pack,indent=2))
