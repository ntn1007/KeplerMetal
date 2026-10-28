#!/usr/bin/env python3
"""Build a test-only host with a wrong auxiliary digest, without GPU work."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','build','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results')
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    base=json.loads((build/'build.json').read_text());sdk=json.loads((build/'sdk-build.json').read_text())
    for name,digest in base['files_SHA256'].items():
        if sha(build/name)!=digest:raise ValueError('input build differs: '+name)
    if sha(build/'host-sdk')!=sdk['host_SHA256']:raise ValueError('SDK host differs')
    shutil.copytree(build,out);header=out/'src/KeplerConditionalAux.h';before=header.read_bytes()
    needle=b'0x6b,0x67,0x31,0xdc';replacement=b'0x6a,0x67,0x31,0xdc'
    if before.count(needle)!=1:raise ValueError('test digest source differs')
    header.write_bytes(before.replace(needle,replacement))
    target=out/'host-sdk';target.unlink() # Never rewrite a potentially mapped executable.
    cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(out/'src'),
         str(out/'sdk_host.mm'),str(out/'import.mm'),str(out/'sdk_wrapper.mm'),
         '-framework','Metal','-framework','Foundation','-o',str(target)]
    result=subprocess.run(cmd,capture_output=True,timeout=120)
    (out/'negative-build.stderr').write_bytes(result.stderr)
    if result.returncode:raise ValueError('negative host build failed')
    base['files_SHA256']['src/KeplerConditionalAux.h']=sha(header)
    (out/'build.json').write_text(json.dumps(base,indent=2,sort_keys=True)+'\n')
    sdk['host_SHA256']=sha(target)
    (out/'sdk-build.json').write_text(json.dumps(sdk,indent=2,sort_keys=True)+'\n')
    proof={'mode':'wrong-expected-aux-digest','original_header_SHA256':hashlib.sha256(before).hexdigest(),
           'test_header_SHA256':sha(header),'original_host_SHA256':sha(build/'host-sdk'),
           'test_host_SHA256':sha(target),'native_input_modified':False,'GPU_dispatch':False}
    (out/'negative-build.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','mode':proof['mode'],'GPU_dispatch':False}))


if __name__=='__main__':main()
