#!/usr/bin/env python3
"""Build, decode and numerically qualify GK104 uint64 global atomic operations."""
from pathlib import Path
import argparse,datetime,hashlib,json,shlex,subprocess
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/atomic64-reproduction');parser.add_argument('--quick',action='store_true')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');assert not out.exists(),'Use a fresh evidence directory';out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver)
assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(command,label,cwd=root,allowed=(0,)):
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'exit_code':result.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label,result.returncode,flush=True)
    if result.returncode not in allowed:print(result.stderr[-2000:]);raise SystemExit(result.returncode)
    return result
def signed(exe,folder,arguments,label,allowed=(0,)):
    return run(['python3',str(root/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(folder),'--timeout','20','--']+arguments,label,allowed=allowed)
# Archive rebuild is a prerequisite, independently recorded. Do not execute old
# unsigned Rust/ninja paths and do not pretend applying a source patch rebuilt it.
patch=json.loads((root/'results/atomic64-compiler-patch.json').read_text());assert sha(root/patch['file'])==patch['after_sha256']
archive=root/'build/mesa/src/nouveau/compiler/libnak_rs.a';rebuild=json.loads((root/'results/atomic64-build-tools/rebuild-result.json').read_text());assert rebuild['exit_code']==0 and sha(archive)==rebuild['after_archive_sha256']
build=root/'build/mesa';entry=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
compiler=out/'atomic64_compile';obj=out/'compiler.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/atomic64_compile.c'),'-o',str(obj)],'compiler-object',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(compiler),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'compiler-link',build)
probe=out/'atomic64_probe'
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/atomic64_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(probe)],'probe-build')
carrier=out/'kepler_carrier.metallib';carrier.write_bytes((root/'results/native-execution-signed/qualified-carrier.metallib').read_bytes())
shaders=[];cases=[]
kinds=('add','cas','exchange') if args.quick else ('add','cas','exchange','add_drop','cas_drop','exchange_drop')
for kind in kinds:
    compileFolder=out/('compile-'+kind);code=out/(kind+'.sass')
    signed(compiler,compileFolder,[kind,str(code),str(out/(kind+'.asm'))],kind+'-compile')
    info=json.loads((compileFolder/'execution.stdout').read_text());infoPath=out/(kind+'-info.json');infoPath.write_text(json.dumps(info,indent=2)+'\n')
    assert info['sm']==30 and not info['scratch_bytes'] and not info['crs_bytes']
    decodeFolder=out/('decode-'+kind)
    signed(root/'build/envydis-only/envydis/envydis',decodeFolder,['-m','gf100','-V','gk104','-i','-n',str(code)],kind+'-decode')
    decoded=(decodeFolder/'execution.stdout').read_text();assert '[unknown' not in decoded
    if kind.startswith('add'):assert 'u64' in decoded and ('ld add' in decoded or 'add u64' in decoded)
    if kind.startswith('cas'):assert 'cas b64' in decoded
    if kind.startswith('exchange'):assert 'exch b64' in decoded
    shaders.append({'kind':kind,'path':str(code.relative_to(root)),'sha256':sha(code),'info':info,'independent_decode':str((decodeFolder/'execution.stdout').relative_to(root))})
    operation=info['operation'];drop=not info['return_values']
    counts=(1,) if args.quick else ((1,33,1025) if operation=='cas' or drop else (1,31,32,33,257,1025))
    variants=(0,) if args.quick else (range(3) if operation=='cas' else range(2))
    rounds=(1,4) if operation=='add' and not args.quick else (1,)
    for count in counts:
        for variant in variants:
            for repeat in rounds:
                staging='managed' if variant==1 else 'nocopy';label=f'{kind}-n{count}-v{variant}-r{repeat}-{staging}';caseFolder=out/label;prefix=out/(label+'-data')
                result=signed(probe,caseFolder,[str(carrier),str(code),str(infoPath),str(count),str(variant),str(repeat),staging,str(prefix)],label,allowed=(0,3,4,5,6,7,10,124))
                data=json.loads((caseFolder/'execution.stdout').read_text()) if (caseFolder/'execution.stdout').exists() and (caseFolder/'execution.stdout').stat().st_size else {'error':result.stderr}
                if result.returncode==0:
                    assert data['mismatches']==data['guard_mismatches']==0 and data['command_status']==4 and data['invocations_counted']==count*repeat
                    assert data['device']=='NVIDIA GeForce GTX 880M' and data['import']['contract_verified']
                    assert all(e['imported_code_identical'] for e in data['import']['events'])
                path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n');cases.append({'label':label,'result':str(path.relative_to(root)),'exit_code':result.returncode})
                if result.returncode:raise SystemExit('GPU case failed; preserved evidence; no further GPU cases launched')
assert sha(driver)==before
sources=[root/'tools/atomic64_compile.c',root/'tools/atomic64_probe.mm',root/'tools/prepare_atomic64_compiler.py',root/'tools/run_signed_probe.py',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h',root/'src/mesa-26.2.4-atomic64-import.patch']
snapshot=out/'source-snapshot';snapshot.mkdir()
for p in sources:(snapshot/p.name).write_bytes(p.read_bytes())
library=out/'libKeplerProgramImport.dylib';library.write_bytes((root/'build/libKeplerProgramImport.dylib').read_bytes())
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'driver_unchanged':True,'quick':args.quick,'shaders':shaders,'cases':cases,'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','compiler_archive_sha256':sha(archive),'compiler_patch':patch,'carrier_sha256':sha(carrier),'library_sha256':sha(library),'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],'scope':'sample global uint64 atomic add/exchange/CAS, returned and discarded results, CPU bit-exact checks and guards; no full API qualification or benchmark'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Qualified cases',len(cases),'all CPU comparisons and guards pass')
