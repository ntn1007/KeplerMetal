#!/usr/bin/env python3
"""Freeze current runtime with unchanged legacy fixtures for relinked regressions."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,tarfile
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);old=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK';library=a.library.resolve();bm=json.loads((library/'manifest.json').read_text())
for f in json.loads((old/'FILE_MANIFEST.json').read_text())['files']:assert sha(old/f['path'])==f['SHA256']
assert sha(library/'libKeplerMetal.a')==bm['static_library_SHA256'];sdk=out/'KeplerMetalSDK';shutil.copytree(old,sdk);shutil.copyfile(library/'libKeplerMetal.a',sdk/'lib/libKeplerMetal.a')
for p in(library/'src').iterdir():shutil.copyfile(p,sdk/'src'/p.name)
for n in ['KeplerCPUICB.h','KeplerCommandIR.h','KeplerNativeCommands.h']:shutil.copyfile(library/'src'/n,sdk/'include'/n)
(sdk/'BUILD_MANIFEST.json').write_text(json.dumps({'status':'BUILT_PENDING_GPU_REGRESSION','source_SHA256':{str(p.relative_to(sdk/'src')):sha(p)for p in(sdk/'src').iterdir()},'static_library_SHA256':sha(sdk/'lib/libKeplerMetal.a'),'reused_build_provenance':bm,'historical_qualification_not_transferred':True},indent=2)+'\n')
(sdk/'qualification.json').write_text(json.dumps({'client_GPU_qualification_pending':True,'ordinary_applications_transparent':False,'all_hardware_functions_supported':False},indent=2)+'\n');(sdk/'FILE_MANIFEST.json').unlink();entries=[{'path':str(p.relative_to(sdk)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(sdk.rglob('*'))if p.is_file()];(sdk/'FILE_MANIFEST.json').write_text(json.dumps({'files':entries},indent=2)+'\n');archive=out/'SDK-for-regression.tar.gz'
with tarfile.open(archive,'x:gz')as t:
 for p in sorted(sdk.rglob('*')):
  if p.is_file():raw=p.read_bytes();i=tarfile.TarInfo('KeplerMetalSDK/'+str(p.relative_to(sdk)));i.mode=0o644;i.size=len(raw);i.mtime=0;t.addfile(i,io.BytesIO(raw))
print(json.dumps({'status':'PASS','archive':str(archive),'SHA256':sha(archive),'files':len(entries)+1,'static_library_SHA256':bm['static_library_SHA256']}))
