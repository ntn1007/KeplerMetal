#!/usr/bin/env python3
"""Qualify native tessellation and application-local NAK evaluation stage."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import struct
import subprocess
import datetime

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/tessellation-reproduction')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver);assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(command,label,cwd=root,environment=None,allowed=(0,)):
    env=os.environ.copy();env.pop('KEPLER_TESS_PIXELS_FILE',None)
    if environment:env.update(environment)
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'environment':environment or {},'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode not in allowed:print(result.stderr[-2500:]);raise SystemExit(result.returncode)
    return result
build=root/'build/mesa';entry=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=root/'build/tessellation_compile.o';run(['clang','-O1']+flags+['-c',str(root/'tools/tessellation_compile.c'),'-o',str(obj)],'tess-compile',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/tessellation_compile'),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'tess-link',build)
code=out/'evaluation.sass';info=json.loads(run([str(root/'build/tessellation_compile'),str(code),str(out/'evaluation.asm')],'evaluation-compile').stdout);infoPath=out/'evaluation-info.json';infoPath.write_text(json.dumps(info,indent=2)+'\n')
decoded=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],'evaluation-decode').stdout;assert '[unknown' not in decoded
run(['clang++','-O3','-std=c++17','-fno-objc-arc','-dynamiclib',str(root/'src/KeplerProgramImport.mm'),'-framework','Metal','-framework','Foundation','-install_name','@rpath/libKeplerProgramImport.dylib','-o',str(root/'build/libKeplerProgramImport.dylib')],'library-build')
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/tessellation_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/tessellation_probe')],'probe-build')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/tessellation_carrier.metal'),'-o',str(out/'tessellation_carrier.air')],'carrier-air')
run(['xcrun','-sdk','macosx','metallib',str(out/'tessellation_carrier.air'),'-o',str(out/'tessellation_carrier.metallib')],'carrier-metallib')
cases=[]
for factor in (0,1,2,4,8,16,32,64):
    images={}
    for mode in ('native','nak'):
        label=f'{mode}-factor{factor}';pixels=out/(label+'.bin');command=[str(root/'build/tessellation_probe'),str(out/'tessellation_carrier.metallib'),str(factor)]
        if mode=='nak':command += [str(code),str(infoPath)]
        result=run(command,label,environment={'KEPLER_TESS_PIXELS_FILE':str(pixels)},allowed=(0,3,4,5,10))
        data=json.loads(result.stdout) if result.stdout.strip() else {'error':result.stderr.strip()}
        # Keep the native/NAK comparison even if the independent ideal bound fails.
        if result.returncode in (0,10) and pixels.exists():images[mode]=struct.unpack('<'+str(64*48*4)+'f',pixels.read_bytes())
        if result.returncode==0:
            assert data['mismatches']==0 and data['command_status']==4
            if mode=='nak':
                assert data['import']['contract_verified'];replaced=[e for e in data['import']['events'] if e.get('code_replaced')]
                assert len(replaced)==1 and replaced[0]['stage']==2 and replaced[0]['imported_code_identical'] and replaced[0]['original_graphics_header_preserved']
        path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n');cases.append({'label':label,'result':str(path.relative_to(root)),'exit_code':result.returncode})
    if len(images)==2:
        errors=[abs(b-((a*.5+.125) if factor and i%4<3 else a)) for i,(a,b) in enumerate(zip(images['native'],images['nak']))]
        mismatches=sum(e>2e-6 for e in errors)
        comparison={'factor':factor,'values':len(errors),'maximum_error':max(errors),'mismatches':mismatches,
                    'scope':'CPU affine transform of native raster reference; higher factors are not an independent topology oracle'}
        (out/f'comparison-factor{factor}.json').write_text(json.dumps(comparison,indent=2)+'\n')
        assert mismatches==0
assert before==sha(driver)
sources=[root/'src/tessellation_carrier.metal',root/'tools/tessellation_compile.c',root/'tools/tessellation_probe.mm',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h']
sourceSnapshot=out/'source-snapshot';sourceSnapshot.mkdir(exist_ok=True)
for p in sources:(sourceSnapshot/p.name).write_bytes(p.read_bytes())
runtime=out/'runtime-snapshot';runtime.mkdir(exist_ok=True)
for name in ('tessellation_compile','tessellation_probe','libKeplerProgramImport.dylib'):(runtime/name).write_bytes((root/'build'/name).read_bytes())
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'driver_unchanged':True,'cases':cases,
          'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','code_sha256':sha(code),'shader_info':info,
          'source_snapshot':[{'path':str((sourceSnapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],
          'runtime_snapshot':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in runtime.iterdir() if p.is_file()],
          'scope':'application-local NAK tessellation evaluation; native hardware tessellator/transport retained; no new Metal family qualification'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');failures=sum(c['exit_code']!=0 for c in cases);print('Cases',len(cases),'Failures',failures)
if failures:raise SystemExit(10)
