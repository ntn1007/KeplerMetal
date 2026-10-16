#!/usr/bin/env python3
"""Freeze the explicit native/CAS contention and unrelated-native-passthrough cohort."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['out','library','client-build']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    lib=a.library.resolve();client=a.client_build.resolve();lm=json.loads((lib/'manifest.json').read_text());ci=json.loads((client/'inputs.json').read_text())
    assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']==ci['static_library_SHA256']
    for n,h in ci['assets_SHA256'].items():assert sha(client/'assets'/n)==h
    shutil.copytree(client/'assets',out/'assets');shutil.copytree(client/'runtime',out/'runtime')
    sdk=ROOT/'results/native-cas-sdk-build-20261014-02/KeplerNativeCAS'
    for row in json.loads((sdk/'FILE_MANIFEST.json').read_text())['files']:assert sha(sdk/row['path'])==row['SHA256']
    m=json.loads((sdk/'assets/client-manifest.json').read_text());profile=next(row for row in m['profiles']if row['candidate'])
    library_name='concurrent-cas.metallib';certificate_name='concurrent-cas.certificate.json'
    assert sha(sdk/'assets'/m['library'])==m['library_SHA256']
    assert sha(sdk/'assets'/profile['certificate'])==profile['certificate_SHA256']
    shutil.copyfile(sdk/'assets'/m['library'],out/'assets'/library_name)
    shutil.copyfile(sdk/'assets'/profile['certificate'],out/'assets'/certificate_name)
    profile=dict(profile,certificate=certificate_name)
    (out/'assets/concurrent-cas-manifest.json').write_text(json.dumps({'library':library_name,'library_SHA256':m['library_SHA256'],'profile':profile},indent=2)+'\n')
    sources=['native_allocation_concurrency_probe.mm','NativeAllocationExecution.inc','KeplerNativeAllocation.h','KeplerNativeCAS.h']
    for name in sources:shutil.copyfile(lib/'src'/name if name.endswith('.h')else ROOT/'tools'/name,out/name)
    cmd=list(map(str,['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/'native_allocation_concurrency_probe.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Foundation','-framework','Metal','-o',out/'application']))
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr)
    (out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
    d={'source_hashes':{n:sha(out/n)for n in sources},'assets_SHA256':{f.name:sha(f)for f in(out/'assets').iterdir()},
       'runtime_SHA256':ci['runtime_SHA256'],'executable_SHA256':sha(out/'application'),'static_library_SHA256':lm['static_library_SHA256'],
       'library_manifest_SHA256':sha(lib/'manifest.json'),'origin_client_inputs_SHA256':sha(client/'inputs.json'),
       'source_generator_SHA256':sha(Path(__file__)),'GPU_execution':False,'scope':'Controlled constructor overlap; GPU kernels execute serially after all factory threads join'}
    (out/'inputs.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'status':'PASS','library_SHA256':d['static_library_SHA256']}))

if __name__=='__main__':main()
