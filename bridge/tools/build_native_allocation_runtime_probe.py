#!/usr/bin/env python3
"""Create native allocation certificates and link the numerical client to the common runtime."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['out','library','native-build','observations']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--lifetime',action='store_true');a=p.parse_args()
    out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    library=a.library.resolve();native=a.native_build.resolve();observations=a.observations.resolve()
    lm=json.loads((library/'manifest.json').read_text());ni=json.loads((native/'inputs.json').read_text())
    od=json.loads((observations/'observations.json').read_text())
    assert sha(library/'libKeplerMetal.a')==lm['static_library_SHA256']
    assert od['native_build_inputs_SHA256']==sha(native/'inputs.json')
    assert json.loads((observations/'status.json').read_text())['status']=='PASS'
    for n,h in ni['assets_SHA256'].items():assert sha(native/'assets'/n)==h
    shutil.copytree(native/'assets',out/'assets');shutil.copytree(native/'runtime',out/'runtime')
    manifest={'library_sha256':sha(out/'assets/control_flow.metallib'),'certificates':{}}
    legacy={}
    for row in od['records']:
        name=row['function'];w=row['metadata_words']
        assert sha(observations/name/'capture/native.sass')==row['code_SHA256']
        assert row['code_bytes']<=104000 and w[12]<=4656 and w[9]==64*w[12]+w[11]and w[12]==w[13]
        cert={'schema':1,'intent':'native_control_reservation','function':name,
              'driver_sha256':od['driver_SHA256'],'library_sha256':manifest['library_sha256'],
              'native_code_sha256':row['code_SHA256'],'code_bytes':row['code_bytes'],
              'metadata_words':w,'control_reserve':4096}
        file=out/'assets'/('allocation-'+name+'.json');file.write_text(json.dumps(cert,sort_keys=True,indent=2)+'\n')
        manifest['certificates'][name]={'file':file.name,'SHA256':sha(file)}
        legacy[name]={'metadata_words':w,'code_SHA256':row['code_SHA256']}
    (out/'assets/native-allocation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    config={'variant':ni.get('variant','nested'),'entry_witness':ni.get('entry_witness',False),
            'depths':[r['source_depth']for r in od['records']],'certificates':legacy,'control_reserve':4096}
    (out/'assets/control_flow_config.json').write_text(json.dumps(config,indent=2)+'\n')
    sources=['native_allocation_runtime_probe.mm','control_flow_probe.mm','KeplerNativeAllocation.h']
    for name in sources:
        source=library/'src'/name if name.endswith('.h')else ROOT/'tools'/name
        shutil.copyfile(source,out/name)
    cmd=list(map(str,['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',
        '-DKP_NATIVE_RESERVE_EXPERIMENT=1','-DKP_ALLOCATION_LIFETIME='+str(int(a.lifetime)),
        '-I',out,out/'native_allocation_runtime_probe.mm',library/'libKeplerMetal.a','-Wl,-ObjC',
        '-framework','Foundation','-framework','Metal','-o',out/'application']))
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    (out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr)
    (out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n')
    assert not r.returncode,r.stderr[-3000:]
    inputs={'source_hashes':{n:sha(out/n)for n in sources},
            'assets_SHA256':{f.name:sha(f)for f in(out/'assets').iterdir()},
            'runtime_SHA256':{f.name:sha(f)for f in(out/'runtime').iterdir()},
            'executable_SHA256':sha(out/'application'),'native_build_inputs_SHA256':sha(native/'inputs.json'),
            'observations_SHA256':sha(observations/'observations.json'),'reserve_mode':'4096',
            'static_library_SHA256':sha(library/'libKeplerMetal.a'),'library_manifest_SHA256':sha(library/'manifest.json'),
            'lifetime_probe':a.lifetime,'source_generator_SHA256':sha(Path(__file__)),'GPU_execution':False}
    (out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    print(json.dumps({'status':'PASS','library_SHA256':inputs['static_library_SHA256'],'lifetime':a.lifetime}))


if __name__=='__main__':main()
