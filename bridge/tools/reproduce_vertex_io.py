#!/usr/bin/env python3
"""Build resource-backed graphics fixtures in an isolated folder."""
from pathlib import Path
import argparse
import json
import shlex
import subprocess
import hashlib
import datetime
import itertools

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/vertex-io-reproduction');parser.add_argument('--compile-only',action='store_true')
parser.add_argument('--draws',nargs='+');parser.add_argument('--interpolations',nargs='+');parser.add_argument('--modes',nargs='+');parser.add_argument('--memories',nargs='+')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
commands=[]
def run(command,label,cwd=root,allowed=(0,)):
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode not in allowed:print(result.stderr[-2500:]);raise SystemExit(result.returncode)
    return result
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver)
assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
build=root/'build/mesa';entries=json.loads((build/'compile_commands.json').read_text());entry=next(e for e in entries if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=root/'build/vertex_io_compile.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/vertex_io_compile.c'),'-o',str(obj)],'io-compile',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/vertex_io_compile'),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'io-link',build)
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/vertex_io_carrier.metal'),'-o',str(out/'vertex_io_carrier.air')],'io-air')
run(['xcrun','-sdk','macosx','metallib',str(out/'vertex_io_carrier.air'),'-o',str(out/'vertex_io_carrier.metallib')],'io-metallib')
run(['clang++','-O1','-std=c++17','-fno-objc-arc',str(root/'tools/compiler_output_trace.mm'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/compiler_output_trace')],'capture-build')
shaders=[]
for kind in ('vertex','smooth','linear','flat','arguments'):
    code=out/(kind+'.sass');info=json.loads(run([str(root/'build/vertex_io_compile'),kind,str(code),str(out/(kind+'.asm')),str(out/(kind+'.sph'))],kind+'-compile').stdout)
    (out/(kind+'-info.json')).write_text(json.dumps(info,indent=2)+'\n')
    decoded=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],kind+'-decode').stdout
    assert '[unknown' not in decoded
    shaders.append({'kind':kind,'path':str(code.relative_to(root)),'sha256':sha(code),'info':info})
for kind in ('smooth','linear','flat'):
    run([str(root/'build/compiler_output_trace'),str(out/'vertex_io_carrier.metallib'),str(out/(kind+'-native')), 'vertex-io',kind],kind+'-capture')
assert before==sha(driver)
(out/'compile-manifest.json').write_text(json.dumps({'driver_sha256':before,'driver_unchanged':True,'shaders':shaders},indent=2)+'\n')
if args.compile_only:raise SystemExit(0)
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/vertex_io_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport',
     '-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/vertex_io_probe')],'io-probe-build')
if any((args.draws,args.interpolations,args.modes,args.memories)):
    combinations=list(itertools.product(args.interpolations or ['smooth'],args.draws or ['direct'],args.modes or ['both'],args.memories or ['managed']))
else:
    combinations=list(itertools.product(['smooth','linear','flat'],['direct'],['native','vertex','fragment','both'],['managed']))
    draws=['vertex-start','indexed16','indexed32','base-vertex','negative-base-vertex','instanced','base-instance','indirect','indirect-indexed','indirect-control']
    combinations+=list(itertools.product(['smooth'],draws,['native','both'],['private']))
    combinations+=list(itertools.product(['smooth','linear','flat'],['direct'],['both'],['nocopy','private']))
cases=[]
for interpolation,draw,mode,memory in combinations:
    label='-'.join((interpolation,draw,mode,memory))
    result=run([str(root/'build/vertex_io_probe'),str(out/'vertex_io_carrier.metallib'),str(out),interpolation,draw,mode,memory],label,allowed=(0,5,6,7,10))
    data=json.loads(result.stdout) if result.stdout.strip() else {'error':result.stderr.strip()}
    if result.returncode==0:
        assert data['device']=='NVIDIA GeForce GTX 880M' and data['mismatched_channels']==0 and data['argument_mismatches']==0 and data['changed_argument_guards']==0
        for key in ('render_import','compute_import'):
            evidence=data[key]
            if evidence:
                assert evidence['contract_verified'];replaced=[e for e in evidence['events'] if e.get('code_replaced',True)]
                expected=2 if key=='render_import' and mode=='both' else 1
                assert len(replaced)==expected and all(e['imported_code_identical'] for e in replaced)
    path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n')
    cases.append({'label':label,'exit_code':result.returncode,'result':str(path.relative_to(root))})
snapshot=out/'source-snapshot';snapshot.mkdir(exist_ok=True)
sources=[root/'src/vertex_io_carrier.metal',root/'tools/vertex_io_compile.c',root/'tools/vertex_io_probe.mm',root/'tools/compiler_output_trace.mm',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h']
for source in sources:(snapshot/source.name).write_bytes(source.read_bytes())
runtime=out/'runtime-snapshot';runtime.mkdir(exist_ok=True)
for name in ('libKeplerProgramImport.dylib','vertex_io_compile','vertex_io_probe'):(runtime/name).write_bytes((root/'build'/name).read_bytes())
assert before==sha(driver)
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'driver_unchanged':True,
          'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','shaders':shaders,'cases':cases,
          'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],
          'runtime_snapshot':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in runtime.iterdir() if p.is_file()],
          'carrier_metallib_sha256':sha(out/'vertex_io_carrier.metallib'),'scope':'resource-backed graphics and GPU-produced indirect draws through installed driver; fixture correctness, no performance benchmark'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');failures=sum(c['exit_code']!=0 for c in cases)
print('Cases',len(cases),'Failures',failures)
if failures:raise SystemExit(10)
