#!/usr/bin/env python3
"""Qualify raw SULDGA reads, unpacking and independent CPU/native controls."""
from pathlib import Path
import argparse,datetime,hashlib,json,shlex,struct,subprocess
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/image-load-reproduction');parser.add_argument('--quick',action='store_true')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');assert not out.exists();out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver);assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(command,label,cwd=root,allowed=(0,)):
    r=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True)
    if r.returncode not in allowed:print(r.stderr[-2000:]);raise SystemExit(r.returncode)
    return r
def signed(exe,folder,arguments,label,allowed=(0,)):
    return run(['python3',str(root/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(folder),'--timeout','20','--']+arguments,label,allowed=allowed)
build=root/'build/mesa';entry=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=out/'compiler.o';compiler=out/'image_load_compile';probe=out/'image_load_probe'
run(['clang','-O1']+flags+['-c',str(root/'tools/image_load_compile.c'),'-o',str(obj)],'compiler-object',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(compiler),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'compiler-link',build)
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/image_load_probe.mm'),'-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),'-framework','Metal','-framework','Foundation','-o',str(probe)],'probe-build')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/image_load_carrier.metal'),'-o',str(out/'carrier.air')],'carrier-air')
carrier=out/'carrier.metallib';run(['xcrun','-sdk','macosx','metallib',str(out/'carrier.air'),'-o',str(carrier)],'carrier-metallib')
signed(root/'build/compiler_output_trace',out/'capture',[str(carrier),str(out/'native-capture'),'compute','surface_load_carrier'],'native-capture')
b=(out/'native-capture/program-0.compiler-output.bin').read_bytes();offset=8
while True:
    next_,kind,size=struct.unpack_from('<QII',b,offset)
    if kind==0x10005:(out/'native.sass').write_bytes(b[offset+16:offset+16+size])
    if not next_:break
    offset+=next_
signed(root/'build/envydis-only/envydis/envydis',out/'native-decode',['-m','gf100','-V','gk104','-i','-n',str(out/'native.sass')],'native-decode')
native=(out/'native-decode/execution.stdout').read_text();assert 'c1[0x108]' in native and 'c1[0x400]' in native and 'c1[0x6e8]' in native
cases=[];shaders=[]
for fmt in ('rgba32f','rgba16f','rgba8','r32f'):
    code=out/(fmt+'.sass');compileFolder=out/('compile-'+fmt)
    signed(compiler,compileFolder,[fmt,str(code),str(out/(fmt+'.asm'))],fmt+'-compile')
    info=json.loads((compileFolder/'execution.stdout').read_text());infoPath=out/(fmt+'-info.json');infoPath.write_text(json.dumps(info,indent=2)+'\n')
    signed(root/'build/envydis-only/envydis/envydis',out/('decode-'+fmt),['-m','gf100','-V','gk104','-i','-n',str(code)],fmt+'-decode')
    decoded=(out/('decode-'+fmt)/'execution.stdout').read_text();assert '[unknown' not in decoded and 'suldg' in decoded
    shaders.append({'format':fmt,'path':str(code.relative_to(root)),'sha256':sha(code),'info':info,'independent_decode':str((out/('decode-'+fmt)/'execution.stdout').relative_to(root))})
    for W,H in ((64,48),) if args.quick else ((64,48),(33,17)):
        for variant in (0,) if args.quick else (0,1):
            for staging in ('nocopy',) if args.quick else ('nocopy','managed'):
                for mode in ('nak','reference','control'):
                    label=f'{fmt}-{W}x{H}-v{variant}-{staging}-{mode}';folder=out/label;prefix=out/(label+'-data')
                    result=signed(probe,folder,[str(carrier),str(code),str(infoPath),mode,fmt,str(W),str(H),str(variant),staging,str(prefix)],label,allowed=(0,3,4,5,6,7,10,124))
                    stdout=folder/'execution.stdout';data=json.loads(stdout.read_text()) if stdout.exists() and stdout.stat().st_size else {'error':result.stderr}
                    if result.returncode==0:
                        assert data['mismatches']==data['raw_mismatches']==data['guard_mismatches']==0 and data['command_status']==4 and data['device']=='NVIDIA GeForce GTX 880M'
                        if mode=='nak':assert data['import']['contract_verified'] and all(e['imported_code_identical'] for e in data['import']['events'])
                    path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n');cases.append({'label':label,'result':str(path.relative_to(root)),'exit_code':result.returncode})
                    if result.returncode:raise SystemExit('GPU case failed; evidence kept; no further cases launched')
assert sha(driver)==before
sources=[root/'src/image_load_carrier.metal',root/'src/KeplerResourceABI.h',root/'tools/image_load_compile.c',root/'tools/image_load_probe.mm',root/'tools/run_signed_probe.py',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h']
snapshot=out/'source-snapshot';snapshot.mkdir()
for p in sources:(snapshot/p.name).write_bytes(p.read_bytes())
library=out/'libKeplerProgramImport.dylib';library.write_bytes((root/'build/libKeplerProgramImport.dylib').read_bytes())
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'driver_unchanged':True,'quick':args.quick,'cases':cases,'shaders':shaders,'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','compiler_archive_sha256':sha(build/'src/nouveau/compiler/libnak_rs.a'),'carrier_sha256':sha(carrier),'library_sha256':sha(library),'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],'scope':'SULDGA raw surface reads via existing write-carrier descriptor ABI; explicit format unpack, CPU/raw oracle and native read-only reference; no general read_write API qualification or benchmark'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Completed image-load cases',len(cases))
