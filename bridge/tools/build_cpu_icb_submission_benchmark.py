#!/usr/bin/env python3
"""Build a public-header-only client against the already-qualified immutable SDK."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--sdk',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
sdk=a.sdk.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'runtime').mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=json.loads((sdk/'BUILD_MANIFEST.json').read_text())
assert sha(sdk/'lib/libKeplerMetal.a')==manifest['static_library_SHA256']=='9d518d1cff252ff60f0e8bd50117f41405265884483dae015aef9c0e059ef754'
assert not (sdk/'src').exists()
source=ROOT/'sdk-combined/examples/cpu_icb_submission_benchmark.mm';shutil.copyfile(source,out/source.name);shutil.copyfile(sdk/'include/KeplerCPUICB.h',out/'KeplerCPUICB.h')
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/source.name),'-L',str(sdk/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-2000:]
shutil.copyfile(sdk/'assets/gpu_copy_integer.metallib',out/'library.metallib')
for n in ['lab_gpu_reservation.py','run_sdk_host.py']:shutil.copyfile(sdk/'runtime'/n,out/'runtime'/n)
(out/'inputs.json').write_text(json.dumps({'source_SHA256':{n:sha(out/n)for n in [source.name,'KeplerCPUICB.h']},'library_SHA256':sha(out/'library.metallib'),'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(sdk/'lib/libKeplerMetal.a'),'runtime_SHA256':{n:sha(out/'runtime'/n)for n in ['lab_gpu_reservation.py','run_sdk_host.py']},'core_source_compilations':0,'SDK_build_manifest_SHA256':sha(sdk/'BUILD_MANIFEST.json'),'GPU_execution':False},indent=2)+'\n');print('Build PASS, core compilations0; existing qualified SDK')
