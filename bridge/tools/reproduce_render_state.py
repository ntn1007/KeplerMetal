#!/usr/bin/env python3
"""Build application-local shaders and qualify raster/ROP states on the 880M."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import datetime

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/render-state-reproduction')
parser.add_argument('--cases',nargs='*');args=parser.parse_args()
out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
before=sha(driver);assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[];cases=[]
def run(command,label,cwd=root,allowed=(0,)):
    env=os.environ.copy()
    for key in ('KEPLER_VERTEX_CODE','KEPLER_VERTEX_INFO','KEPLER_RENDER_OUTPUT_DIR'):env.pop(key,None)
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode not in allowed:print(result.stderr[-2000:]);raise SystemExit(result.returncode)
    return result
build=root/'build/mesa';entries=json.loads((build/'compile_commands.json').read_text())
entry=next(e for e in entries if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=root/'build/graphics_fragment_compile.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/graphics_fragment_compile.c'),'-o',str(obj)],'graphics-compile',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a',
          'src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a',
          'src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/graphics_fragment_compile'),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'graphics-link',build)
run(['clang++','-O3','-std=c++17','-fno-objc-arc','-dynamiclib',str(root/'src/KeplerProgramImport.mm'),'-framework','Metal','-framework','Foundation',
     '-install_name','@rpath/libKeplerProgramImport.dylib','-o',str(root/'build/libKeplerProgramImport.dylib')],'import-library-build')
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/render_state_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),
     '-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/render_state_probe')],'state-probe-build')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/render_state_carrier.metal'),'-o',str(out/'render_state_carrier.air')],'state-air')
run(['xcrun','-sdk','macosx','metallib',str(out/'render_state_carrier.air'),'-o',str(out/'render_state_carrier.metallib')],'state-metallib')
for tool in ('compiler_output_trace','program_container_test'):
    run(['clang++','-O1','-std=c++17','-fno-objc-arc',str(root/'tools'/f'{tool}.mm'),'-framework','Metal','-framework','Foundation','-o',str(root/'build'/tool)],tool+'-build')
for mode in ('stencil','render-state'):
    capture=out/(mode+'-native-container')
    run([str(root/'build/compiler_output_trace'),str(out/'render_state_carrier.metallib'),str(capture),mode],mode+'-capture')
run([str(root/'build/program_container_test'),str(out/'stencil-native-container/program-0.compiler-output.bin'),
     str(out/'render-state-native-container/program-0.compiler-output.bin')],'container-checks')
shaders=[]
for kind in ('constant','vertex','vertex_half','vertex_near','vertex_far','constant_red','blend','mrt2','mrt4','mrt8','mask0','mask1','mask5','mask15'):
    code=out/(kind+'.sass');info=json.loads(run([str(root/'build/graphics_fragment_compile'),str(code),str(out/(kind+'.asm')),str(out/(kind+'.sph')),kind],kind+'-compile').stdout)
    (out/(kind+'-info.json')).write_text(json.dumps(info,indent=2)+'\n')
    decoded=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],kind+'-decode').stdout
    assert '[unknown' not in decoded
    previous=root/'results/graphics-reproduction'/(kind+'.sass')
    if previous.exists():assert sha(code)==sha(previous),'Old shader changed: '+kind
    shaders.append({'kind':kind,'path':str(code.relative_to(root)),'sha256':sha(code),'registers':info['registers']})
labels=args.cases or ['blend-'+op for op in ('add','subtract','reverse','min','max','one-add','constant')]
if not args.cases:
    labels+=['scissor','color-mask','cull-front','cull-back','mrt2','mrt4','mrt8','stencil-equal','stencil-inverse']
    labels+=['depth-'+op for op in ('never','less','equal','less-equal','greater','not-equal','greater-equal','always','near-first','far-first','write-off')]
    labels+=[f'msaa{samples}-mask{mask}' for samples in (2,4,8) for mask in (0,1,5,15)]
for label in labels:
    for mode in ('native','nak'):
        result=run([str(root/'build/render_state_probe'),str(out/'render_state_carrier.metallib'),str(out),label,mode],label+'-'+mode,allowed=(0,4,6,7,10,77))
        data=json.loads(result.stdout) if result.stdout.strip() else {'error':result.stderr.strip()}
        if result.returncode==0:
            assert data['mismatched_channels']==0 and data['command_status']==4
            if mode=='nak':
                assert len(data['imports'])==data['draws']
                for entry in data['imports']:
                    assert entry['contract_verified']
                    replaced=[e for e in entry['events'] if e.get('code_replaced')]
                    assert len(replaced)==entry['requested_stages'] and all(e['imported_code_identical'] and e['original_graphics_header_preserved'] for e in replaced)
        path=out/(label+'-'+mode+'.json');path.write_text(json.dumps(data,indent=2)+'\n')
        cases.append({'label':label,'mode':mode,'exit_code':result.returncode,'result':str(path.relative_to(root))})
        if mode=='native' and result.returncode:break
after=sha(driver);assert before==after
sources=[root/'tools/graphics_fragment_compile.c',root/'tools/render_state_probe.mm',root/'src/render_state_carrier.metal',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h',root/'tools/compiler_output_trace.mm',root/'tools/program_container_test.mm']
snapshot=out/'source-snapshot';snapshot.mkdir(exist_ok=True)
for path in sources:(snapshot/path.name).write_bytes(path.read_bytes())
runtimeSnapshot=out/'runtime-snapshot';runtimeSnapshot.mkdir(exist_ok=True)
runtimeNames=('libKeplerProgramImport.dylib','render_state_probe','graphics_fragment_compile')
for name in runtimeNames:(runtimeSnapshot/name).write_bytes((root/'build'/name).read_bytes())
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':cases,'shaders':shaders,
          'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2',
          'mesa_texture_patch_sha256':sha(root/'src/mesa-26.2.4-macos-texture-import.patch'),
          'driver_before_sha256':before,'driver_after_sha256':after,'driver_unchanged':True,
          'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],
          'runtime_library_sha256':sha(root/'build/libKeplerProgramImport.dylib'),
          'runtime_snapshot':[{'path':str((runtimeSnapshot/name).relative_to(root)),'sha256':sha(runtimeSnapshot/name)} for name in runtimeNames],
          'probe_sha256':sha(root/'build/render_state_probe'),'compiler_sha256':sha(root/'build/graphics_fragment_compile'),
          'carrier_metallib_sha256':sha(out/'render_state_carrier.metallib'),
          'scope':'fixture-qualified installed raster/ROP transport with application-local NAK graphics stages; no system/OCLP changes, no performance benchmark'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
failures=sum(c['exit_code'] not in (0,77) for c in cases)
print('Cases:',len(cases),'Failures:',failures,'Unsupported:',sum(c['exit_code']==77 for c in cases))
if failures:raise SystemExit(10)
