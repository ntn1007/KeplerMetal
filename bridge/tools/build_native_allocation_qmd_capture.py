#!/usr/bin/env python3
"""Freeze a read-only packet capture client against an already qualified archive."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['out','library','client-build']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true',help='Build explicit guarded numerical submission client')
    a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');lib=a.library.resolve();client=a.client_build.resolve()
    lm=json.loads((lib/'manifest.json').read_text());ci=json.loads((client/'inputs.json').read_text())
    assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']==ci['static_library_SHA256']
    for n,h in ci['assets_SHA256'].items():assert sha(client/'assets'/n)==h
    for n,h in ci['runtime_SHA256'].items():assert sha(client/'runtime'/n)==h
    out.mkdir(exist_ok=False);shutil.copytree(client/'assets',out/'assets');shutil.copytree(client/'runtime',out/'runtime')
    sources=['native_allocation_qmd_capture.mm','KeplerNativeAllocation.h']
    if a.execute:sources.insert(0,'native_allocation_qmd_execute.mm')
    for n in sources:shutil.copyfile(lib/'src'/n if n.endswith('.h')else ROOT/'tools'/n,out/n)
    shutil.copyfile(Path(__file__),out/'builder.py')
    cmd=list(map(str,['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/sources[0],lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Foundation','-framework','Metal','-o',out/'application']))
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr)
    (out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-3500:]
    inputs={'source_hashes':{n:sha(out/n)for n in sources},'assets_SHA256':{f.name:sha(f)for f in(out/'assets').iterdir()},
            'runtime_SHA256':{f.name:sha(f)for f in(out/'runtime').iterdir()},'executable_SHA256':sha(out/'application'),
            'static_library_SHA256':lm['static_library_SHA256'],'library_manifest_SHA256':sha(lib/'manifest.json'),
            'parent_client_inputs_SHA256':sha(client/'inputs.json'),'source_generator_SHA256':sha(out/'builder.py'),
            'GPU_execution':False,'client_will_submit':a.execute,'scope':'Ordinary guarded GPU submission with passive packet capture'if a.execute else'Own process read-only encoder snapshots; no commit, packet patch or replay'}
    (out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','library_SHA256':inputs['static_library_SHA256']}))


if __name__=='__main__':main()
