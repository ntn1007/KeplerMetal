#!/usr/bin/env python3
"""Equivalent MSL/NAK resident kernels with GPU progress proofs and paired trials."""
from pathlib import Path
import argparse,datetime,hashlib,json,shlex,shutil,struct,subprocess
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/shared-benchmark-reproduction');parser.add_argument('--quick',action='store_true');parser.add_argument('--import-library',type=Path,default=root/'build/import-audit/libKeplerProgramImport.dylib')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');assert not out.exists();out.mkdir(parents=True)
library=args.import_library.resolve();library.relative_to(root);assert library.name=='libKeplerProgramImport.dylib' and library.exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver);assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(cmd,label,cwd=root,timeout=60):
    r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    commands.append({'label':label,'command':cmd,'cwd':str(cwd),'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True)
    if r.returncode:print(r.stderr[-1500:]);raise SystemExit(r.returncode)
    return r
def signed(exe,path,arguments,label,timeout=20):return run(['python3',str(root/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(path),'--timeout',str(timeout),'--']+arguments,label,timeout=timeout+15)
build=root/'build/mesa';e=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'));flags=[a for a in shlex.split(e['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=out/'compiler.o';compiler=out/'shared_benchmark_compile';probe=out/'shared_benchmark_probe'
run(['clang','-O1']+flags+['-c',str(root/'tools/shared_benchmark_compile.c'),'-o',str(obj)],'compiler-object',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(compiler),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'compiler-link',build)
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/shared_benchmark_probe.mm'),'-I'+str(root/'src'),'-L'+str(library.parent),'-lKeplerProgramImport','-Wl,-rpath,'+str(library.parent),'-framework','Metal','-framework','Foundation','-o',str(probe)],'probe-build')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-DSHARED_WORDS=12288','-c',str(root/'src/shared_benchmark.metal'),'-o',str(out/'carrier.air')],'carrier-air');carrier=out/'carrier.metallib';run(['xcrun','-sdk','macosx','metallib',str(out/'carrier.air'),'-o',str(carrier)],'carrier-metallib')
shaders=[];cases=[];captures=[]
for kind,shared in (('capacity',49152),('add',4)):
    code=out/(kind+'.sass');signed(compiler,out/('compile-'+kind),[kind,str(code),str(out/(kind+'.asm')),str(shared)],kind+'-compile');info=json.loads((out/('compile-'+kind)/'execution.stdout').read_text());(out/(kind+'-info.json')).write_text(json.dumps(info,indent=2)+'\n')
    signed(root/'build/envydis-only/envydis/envydis',out/('decode-'+kind),['-m','gf100','-V','gk104','-i','-n',str(code)],kind+'-decode');decoded=(out/('decode-'+kind)/'execution.stdout').read_text();assert '[unknown' not in decoded and 'red add' in decoded
    for role in ('reference','carrier'):
        label=kind+'-'+role;folder=out/('native-'+label);signed(root/'build/compiler_output_trace',out/('capture-'+label),[str(carrier),str(folder),'compute','shared_'+kind+'_'+role],label+'-capture')
        b=(folder/'program-0.compiler-output.bin').read_bytes();offset=8;registers=0
        while True:
            next_,section,size=struct.unpack_from('<QII',b,offset)
            if section==0x10004:registers=struct.unpack_from('<I',b,offset+16+28)[0]
            if section==0x10005:(out/(label+'-native.sass')).write_bytes(b[offset+16:offset+16+size])
            if not next_:break
            offset+=next_
        captures.append({'kind':kind,'role':role,'compiler_metadata_registers':registers,'code_bytes':(out/(label+'-native.sass')).stat().st_size,'capture':str(folder.relative_to(root))})
    shaders.append({'kind':kind,'info':info,'path':str(code.relative_to(root)),'sha256':sha(code)})
    geometries=[(128,1,1)] if args.quick else ([(128,g,b) for g in (8,64) for b in (1,16,64)] if kind=='capacity' else [(128,g,b) for g in (8,64) for b in (1,16,64)])
    for local,groups,batch in geometries:
        label=f'{kind}-l{local}-g{groups}-b{batch}';cases.append({'label':label,'kind':kind,'info':info,'carrier':str(carrier),'code':str(code),'local':local,'groups':groups,'batch':batch,'result':str(out/(label+'.json'))})
for start in range(0,len(cases),3):
    n=start//3;plan=out/(f'plan-{n}.json');plan.write_text(json.dumps(cases[start:start+3],indent=2)+'\n');signed(probe,out/(f'gpu-{n}'),[str(plan)],f'gpu-{n}',timeout=60)
assert sha(driver)==before
snapshot=out/'source-snapshot';snapshot.mkdir();sources=[root/'src/shared_benchmark.metal',root/'tools/shared_benchmark_compile.c',root/'tools/shared_benchmark_probe.mm',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h',root/'tools/run_signed_probe.py']
for p in sources:shutil.copyfile(p,snapshot/p.name)
shutil.copyfile(library,out/library.name)
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'quick':args.quick,'driver_unchanged':True,'driver_sha256':before,'library_sha256':sha(out/library.name),'carrier_sha256':sha(carrier),'shaders':shaders,'native_compiler_profiles':captures,'cases':[{'label':c['label'],'kind':c['kind'],'local':c['local'],'groups':c['groups'],'batch':c['batch'],'result':str(Path(c['result']).relative_to(root))}for c in cases],'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)}for p in sources],'mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','actual_occupancy_measured':False,'GPU_timestamps_qualified':False,'scope':'manual equivalent NIR and MSL kernels with equal group completion/result-checksum counters; paired alternating compiler order; resident Private resources, Managed readback; no generalized application/Metal-family speed claim'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Completed benchmark cases',len(cases))
