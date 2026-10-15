#!/usr/bin/env python3
"""Capture buffer-only native/NAK tessellation outputs and check CPU arithmetic."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shlex,struct,subprocess

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/tessellation-capture-reproduction')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver)
assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(command,label,cwd=root,environment=None,allowed=(0,)):
    env=os.environ.copy();env.pop('KEPLER_TESS_CAPTURE_PREFIX',None)
    if environment:env.update(environment)
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'environment':environment or {},'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode not in allowed:print(result.stderr[-2500:]);raise SystemExit(result.returncode)
    return result
build=root/'build/mesa';entry=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=root/'build/tessellation_capture_compile.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/tessellation_capture_compile.c'),'-o',str(obj)],'capture-compile',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/tessellation_capture_compile'),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'capture-link',build)
code=out/'capture.sass';info=json.loads(run([str(root/'build/tessellation_capture_compile'),str(code),str(out/'capture.asm')],'sass-compile').stdout)
infoPath=out/'capture-info.json';infoPath.write_text(json.dumps(info,indent=2)+'\n')
decoded=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],'sass-decode').stdout;assert '[unknown' not in decoded
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/tessellation_capture_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/tessellation_capture_probe')],'probe-build')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/tessellation_capture.metal'),'-o',str(out/'carrier.air')],'carrier-air')
run(['xcrun','-sdk','macosx','metallib',str(out/'carrier.air'),'-o',str(out/'carrier.metallib')],'carrier-metallib')
run(['clang++','-O2','-std=c++17','-fno-objc-arc',str(root/'tools/compiler_output_trace.mm'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/compiler_output_trace')],'trace-build')
run([str(root/'build/compiler_output_trace'),str(out/'carrier.metallib'),str(out/'native-capture'),'tessellation','capture'],'native-capture')
cases=[];comparisons=[]
for factor in (0,1,2,4,8,16,32,64):
    captures={}
    for mode in ('native','nak'):
        label=f'{mode}-factor{factor}';prefix=out/label;command=[str(root/'build/tessellation_capture_probe'),str(out/'carrier.metallib'),str(factor)]
        if mode=='nak':command += [str(code),str(infoPath)]
        result=run(command,label,environment={'KEPLER_TESS_CAPTURE_PREFIX':str(prefix)},allowed=(0,3,4,5,10))
        data=json.loads(result.stdout) if result.stdout.strip() else {'error':result.stderr.strip()}
        if result.returncode==0:
            assert data['mismatches']==data['guard_mismatches']==data['tail_mismatches']==0 and data['command_status']==4
            if mode=='nak':
                assert data['import']['contract_verified'];events=[e for e in data['import']['events'] if e.get('code_replaced')]
                assert len(events)==1 and events[0]['stage']==2 and events[0]['imported_code_identical'] and events[0]['original_graphics_header_preserved']
            raw=(out/(label+'.coords.bin')).read_bytes();coords=list(struct.iter_unpack('<4f',raw))
            values=list(struct.iter_unpack('<4f',(out/(label+'.values.bin')).read_bytes()))
            captures[mode]=sorted(zip(coords,values))
        path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n')
        cases.append({'label':label,'result':str(path.relative_to(root)),'exit_code':result.returncode,'invocations':data.get('invocations')})
    if len(captures)==2:
        native=captures['native'];nak=captures['nak'];assert len(native)==len(nak)
        coordError=max((abs(a-b) for n,k in zip(native,nak) for a,b in zip(n[0],k[0])),default=0)
        valueError=max((abs(b-(a*.5+.125 if c<3 else a)) for n,k in zip(native,nak) for c,(a,b) in enumerate(zip(n[1],k[1]))),default=0)
        assert coordError==0 and valueError<=1e-7
        comparisons.append({'factor':factor,'invocations':len(native),'max_coordinate_difference':coordError,'max_affine_value_difference':valueError,'scope':'unordered coordinate multiset and CPU affine transform of native values; CPU square oracle also checked independently by probe'})
assert before==sha(driver)
sources=[root/'src/tessellation_capture.metal',root/'src/KeplerResourceABI.h',root/'tools/tessellation_capture_compile.c',root/'tools/tessellation_capture_probe.mm',root/'tools/compiler_output_trace.mm',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h']
snapshot=out/'source-snapshot';snapshot.mkdir(exist_ok=True)
for p in sources:(snapshot/p.name).write_bytes(p.read_bytes())
runtime=out/'runtime-snapshot';runtime.mkdir(exist_ok=True)
for name in ('tessellation_capture_compile','tessellation_capture_probe','compiler_output_trace','libKeplerProgramImport.dylib'):(runtime/name).write_bytes((root/'build'/name).read_bytes())
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'driver_unchanged':True,'cases':cases,'comparisons':comparisons,'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','shader_info':info,'code_sha256':sha(code),'carrier_metallib_sha256':sha(out/'carrier.metallib'),'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],'runtime_snapshot':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in runtime.iterdir() if p.is_file()],'scope':'buffer-only triangle tessellation evaluation; independent CPU square per captured hardware coordinate; topology and raster precision not qualified'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');failures=sum(c['exit_code']!=0 for c in cases);print('Cases',len(cases),'Failures',failures)
if failures:raise SystemExit(10)
