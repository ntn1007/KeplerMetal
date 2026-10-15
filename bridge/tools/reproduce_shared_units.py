#!/usr/bin/env python3
"""Build and execute shared-memory/atomic fixtures through the installed driver."""
from pathlib import Path
import argparse,datetime,hashlib,json,shlex,shutil,struct,subprocess
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/shared-units-reproduction');parser.add_argument('--quick',action='store_true');parser.add_argument('--kinds',choices=('all','capacity','atomics'),default='all');parser.add_argument('--import-library',type=Path,default=root/'build/libKeplerProgramImport.dylib')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');assert not out.exists();out.mkdir(parents=True)
library=args.import_library.resolve();library.relative_to(root);assert library.name=='libKeplerProgramImport.dylib' and library.is_file();libraryDir=library.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver);assert before==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
commands=[]
def run(command,label,cwd=root,timeout=60):
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'exit_code':result.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode:print(result.stderr[-2000:]);raise SystemExit(result.returncode)
    return result
def signed(exe,directory,arguments,label,timeout=20):
    return run(['python3',str(root/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(directory),'--timeout',str(timeout),'--']+arguments,label,timeout=timeout+20)
build=root/'build/mesa';entry=next(e for e in json.loads((build/'compile_commands.json').read_text()) if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=out/'compiler.o';compiler=out/'shared_units_compile';probe=out/'shared_units_probe'
run(['clang','-O1']+flags+['-c',str(root/'tools/shared_units_compile.c'),'-o',str(obj)],'compiler-object',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(compiler),str(obj)]+archives+['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'compiler-link',build)
run(['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools/shared_units_probe.mm'),'-I'+str(root/'src'),'-L'+str(libraryDir),'-lKeplerProgramImport','-Wl,-rpath,'+str(libraryDir),'-framework','Metal','-framework','Foundation','-o',str(probe)],'probe-build')
shaders=[];carriers={};cases=[]
kinds=[]
if args.kinds in ('all','capacity'):kinds += [('capacity',b) for b in ((16384,) if args.quick else (16384,32768,49152))]
if args.kinds in ('all','atomics'):kinds += [(kind,4) for kind in ('add','exchange','cas')]
for kind,shared in kinds:
    label=f'{kind}-{shared}';code=out/(label+'.sass');infoPath=out/(label+'-info.json')
    signed(compiler,out/('compile-'+label),[kind,str(code),str(out/(label+'.asm')),str(shared)],label+'-compile')
    info=json.loads((out/('compile-'+label)/'execution.stdout').read_text());infoPath.write_text(json.dumps(info,indent=2)+'\n')
    signed(root/'build/envydis-only/envydis/envydis',out/('decode-'+label),['-m','gf100','-V','gk104','-i','-n',str(code)],label+'-decode')
    decoded=(out/('decode-'+label)/'execution.stdout').read_text();assert '[unknown' not in decoded
    if kind!='capacity':assert 'ld lock' in decoded and 'st unlock' in decoded, decoded[-1000:]
    words=shared//4 if kind=='capacity' else 4096
    if words not in carriers:
        carrier=out/(f'carrier-{words}.metallib');air=out/(f'carrier-{words}.air')
        run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-DSHARED_WORDS='+str(words),'-c',str(root/'src/shared_units_carrier.metal'),'-o',str(air)],f'carrier-{words}-air')
        run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(carrier)],f'carrier-{words}-metallib');carriers[words]=carrier
    carrier=carriers[words]
    shaders.append({'kind':kind,'path':str(code.relative_to(root)),'sha256':sha(code),'info':info,'carrier':str(carrier.relative_to(root)),'independent_decode':str((out/('decode-'+label)/'execution.stdout').relative_to(root))})
    fixtures=[(128,1,0,0,'nocopy')] if kind=='capacity' and args.quick else ([(32,1,31,0,'nocopy')] if args.quick else None)
    if fixtures is None:
        if kind=='capacity':fixtures=[(local,groups,0,0,staging) for local in (128,1024) for groups in (1,3) for staging in ('managed','nocopy')]
        else:fixtures=[(local,groups,active,variant,staging) for local,active in ((32,31),(128,33),(1024,1024)) for groups in (1,3) for variant in (0,1) for staging in ('managed','nocopy')]
    for local,groups,active,variant,staging in fixtures:
        for mode in ('nak','reference','control'):
            name=f'{label}-l{local}-g{groups}-a{active}-v{variant}-{staging}-{mode}'
            cases.append({'label':name,'carrier':str(carrier),'code':str(code),'info':info,'mode':mode,'local':local,'groups':groups,'active':active,'variant':variant,'staging':staging,'dump_prefix':str(out/(name+'-data'))})
captures=[]
for kind,shared in (kinds[:1] + ([kinds[-1]] if len(kinds)>1 else [])):
    label=f'{kind}-{shared}';words=shared//4 if kind=='capacity' else 4096;function=f'shared_{kind}_carrier'
    capture=out/('native-'+label);signed(root/'build/compiler_output_trace',out/('capture-'+label),[str(carriers[words]),str(capture),'compute',function],label+'-native-capture')
    container=(capture/'program-0.compiler-output.bin').read_bytes();offset=8
    while True:
        next_,section,size=struct.unpack_from('<QII',container,offset)
        if section==0x10005:(out/(label+'-native.sass')).write_bytes(container[offset+16:offset+16+size])
        if not next_:break
        offset+=next_
    signed(root/'build/envydis-only/envydis/envydis',out/('native-decode-'+label),['-m','gf100','-V','gk104','-i','-n',str(out/(label+'-native.sass'))],label+'-native-decode')
    captures.append(str(capture.relative_to(root)))
for start in range(0,len(cases),36):
    batch=cases[start:start+36];number=start//36;plan=out/(f'plan-{number}.json');plan.write_text(json.dumps(batch,indent=2)+'\n')
    signed(probe,out/(f'gpu-batch-{number}'),[str(plan)],f'gpu-batch-{number}',timeout=60)
    for case in batch:
        data=json.loads(Path(case['dump_prefix']+'.json').read_text());assert data['mismatches']==data['guard_mismatches']==0 and data['command_status']==4
        if case['mode']=='nak':assert data['import']['contract_verified'] and all(e['imported_code_identical'] for e in data['import']['events'])
assert sha(driver)==before
sources=[root/'src/shared_units_carrier.metal',root/'src/KeplerResourceABI.h',root/'tools/shared_units_compile.c',root/'tools/shared_units_probe.mm',root/'tools/run_signed_probe.py',Path(__file__).resolve(),root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h']
snapshot=out/'source-snapshot';snapshot.mkdir()
for path in sources:shutil.copyfile(path,snapshot/path.name)
shutil.copyfile(library,out/'libKeplerProgramImport.dylib')
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'quick':args.quick,'kinds':args.kinds,'driver_sha256':before,'driver_unchanged':True,'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2','compiler_archive_sha256':sha(build/'src/nouveau/compiler/libnak_rs.a'),'library_sha256':sha(out/'libKeplerProgramImport.dylib'),'shaders':shaders,'carriers':[{'path':str(c.relative_to(root)),'sha256':sha(c)} for c in carriers.values()],'source_snapshot':[{'path':str((snapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],'cases':[{'label':c['label'],'result':str(Path(c['dump_prefix']+'.json').relative_to(root)),'dump':str(Path(c['dump_prefix']+'.output.bin').relative_to(root)),'configuration':{k:c[k] for k in ('mode','local','groups','active','variant','staging')}} for c in cases],'native_captures':captures,'scope':'own-process native program import; existing driver owns shared-memory allocation and GPU submission; no general API family or performance qualification'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Completed shared-unit cases',len(cases))
