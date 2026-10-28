#!/usr/bin/env python3
"""Build a passive conditional-CAS command observer; no GPU work."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from run_repair import PINS

EXPERIMENT=Path(__file__).resolve().parent
BRIDGE=EXPERIMENT.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','base','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();base=a.base.resolve();out=a.out.resolve()
    base.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    manifest=json.loads((base/'build.json').read_text())
    for name,digest in manifest['files_SHA256'].items():need(sha(base/name)==digest,'base input changed: '+name)
    sdk=json.loads((base/'sdk-build.json').read_text())
    need(sha(base/'certificate.json')==sdk['certificate_SHA256'] and
         sha(base/'sdk_wrapper.mm')==sdk['wrapper_SHA256']==sha(EXPERIMENT/'sdk_wrapper.mm'), 'SDK certificate or wrapper differs')
    for name,digest in PINS.items():need(sha(base/name)==digest,'pinned input changed: '+name)
    need(sha(base/'import.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
         sha(base/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc') and
         sha(base/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h'), 'runtime source differs')
    out.mkdir();shutil.copytree(base/'src',out/'src')
    for name in ('import.mm','sdk_wrapper.mm','shader.metallib','original.sass','repaired.sass','certificate.json'):
        shutil.copyfile(base/name,out/name)
    shutil.copyfile(EXPERIMENT/'observe_cb0.mm',out/'observe.mm')
    shutil.copyfile(BRIDGE/'tools/ICBTextureNativeMetadata.inc',out/'ICBTextureNativeMetadata.inc')
    cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(out/'src'),'-I',str(out),
         str(out/'observe.mm'),str(out/'import.mm'),str(out/'sdk_wrapper.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'host')]
    r=subprocess.run(cmd,capture_output=True,timeout=120);(out/'build.stderr').write_bytes(r.stderr)
    need(r.returncode==0,'observer build failed')
    files={str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()}
    (out/'build.json').write_text(json.dumps({'files_SHA256':files,'GPU_dispatch':False,
        'source_build_SHA256':sha(base/'build.json')},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'host_sha256':sha(out/'host')}))

if __name__=='__main__':main()
