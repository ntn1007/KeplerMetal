#!/usr/bin/env python3
"""Build and qualify uniform/storage/image bindings through the installed driver."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shlex
import subprocess
import shutil

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/resource-reproduction');parser.add_argument('--quick',action='store_true')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver)
assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(command,label,cwd=root,allowed=(0,)):
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode not in allowed:print(result.stderr[-2500:]);raise SystemExit(result.returncode)
    return result
run(['python3',str(root/'tools/prepare_resources.py')],'native-bindings')
build=root/'build/mesa';entry=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=root/'build/resource_compile.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/resource_compile.c'),'-o',str(obj)],'resource-compile',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/resource_compile'),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'resource-link',build)
shaders=[]
for kind in ('buffers_a','buffers_b','image'):
    code=out/(kind+'.sass');info=json.loads(run([str(root/'build/resource_compile'),kind,str(code),str(out/(kind+'.asm'))],kind+'-compile').stdout)
    (out/(kind+'-info.json')).write_text(json.dumps(info,indent=2)+'\n')
    decoded=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],kind+'-decode').stdout
    assert '[unknown' not in decoded
    shaders.append({'kind':kind,'path':str(code.relative_to(root)),'sha256':sha(code),'info':info})
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/resource_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/resource_probe')],'probe-build')
cases=[]
specifications=[]
for kind in ('buffers_a','buffers_b'):
    for shape in ([(17,13,3)] if args.quick else [(257,1,1),(17,13,3),(32,24,2)]):
        for memory in (['managed'] if args.quick else ['managed','nocopy','private']):
            for variant in ([0] if args.quick else [0,1]):specifications.append((kind,shape,memory,'none',variant,(4,8,1)))
for fmt in (['rgba32f'] if args.quick else ['rgba32f','rgba16f','rgba8','r32f']):
    for shape in ([(64,48,1)] if args.quick else [(64,48,1),(33,17,1)]):specifications.append(('image',shape,'nocopy',fmt,0,(4,8,1)))
if not args.quick:
    for local in ((1,1,1),(32,1,1),(8,4,2),(4,4,4),(1,1,64),(32,32,1)):
        for variant in (0,1):specifications.append(('buffers_a',(17,13,3),'private','none',variant,local))
for kind,shape,memory,fmt,variant,local in specifications:
    for mode in ('native','nak'):
        label='-'.join((kind,mode,memory,fmt,'x'.join(map(str,shape)),str(variant),'local'+'x'.join(map(str,local))))
        result=run([str(root/'build/resource_probe'),str(root/'results/resource-native/resource_carrier.metallib'),str(out),kind,mode,memory]+list(map(str,shape))+[fmt,str(variant)]+list(map(str,local)),label,allowed=(0,3,4,5,10))
        data=json.loads(result.stdout) if result.stdout.strip() else {'error':result.stderr.strip()}
        if result.returncode==0:
            assert data['device']=='NVIDIA GeForce GTX 880M' and data['mismatches']==0 and data['changed_guards']==0 and data['command_status']==4
            if mode=='nak':assert data['import']['contract_verified'] and all(e['imported_code_identical'] for e in data['import']['events'])
        path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n')
        cases.append({'label':label,'exit_code':result.returncode,'result':str(path.relative_to(root))})
assert before==sha(driver)
sourceSnapshot=out/'source-snapshot';sourceSnapshot.mkdir(exist_ok=True)
sources=[root/'src/resource_carrier.metal',root/'src/KeplerResourceABI.h',root/'tools/resource_compile.c',root/'tools/resource_probe.mm',root/'tools/prepare_resources.py',root/'tools/compiler_output_trace.mm',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h']
for source in sources:(sourceSnapshot/source.name).write_bytes(source.read_bytes())
runtime=out/'runtime-snapshot';runtime.mkdir(exist_ok=True)
for name in ('resource_compile','resource_probe','libKeplerProgramImport.dylib'):(runtime/name).write_bytes((root/'build'/name).read_bytes())
carrier=root/'results/resource-native/resource_carrier.metallib';(out/'resource_carrier.metallib').write_bytes(carrier.read_bytes())
shutil.copytree(root/'results/resource-native',out/'native-captures',dirs_exist_ok=True)
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'driver_unchanged':True,'quick':args.quick,
          'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','shaders':shaders,'cases':cases,
          'source_snapshot':[{'path':str((sourceSnapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],
          'runtime_snapshot':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in runtime.iterdir() if p.is_file()],
          'carrier_metallib_sha256':sha(carrier),'scope':'sample-qualified CB1/CB2 bindings, 3D dispatch and surface stores through installed driver; no system/OCLP changes or performance benchmark'}
manifest['native_captures']=[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in sorted((out/'native-captures').rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');failures=sum(c['exit_code']!=0 for c in cases)
print('Cases',len(cases),'Failures',failures)
if failures:raise SystemExit(10)
