#!/usr/bin/env python3
"""Rebuild and qualify the experimental Kepler import/memory/compute components."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--out',type=Path,default=root/'results/compute-reproduction')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
expected=json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
before=hashlib.sha256(driver.read_bytes()).hexdigest()
if before!=expected:raise SystemExit('Installed driver changed; revalidate the private program ABI first.')
commands=[];cases=[]
def run(command,label,cwd=root,environment=None):
    env=os.environ.copy()
    if environment:env.update(environment)
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(cwd),'environment':environment or {},'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label,result.returncode,flush=True)
    if result.returncode:
        print(result.stderr[-2000:]);raise SystemExit(result.returncode)
    return result.stdout

run(['clang++','-O3','-std=c++17','-fno-objc-arc','-dynamiclib',str(root/'src/KeplerProgramImport.mm'),
     '-framework','Metal','-framework','Foundation','-install_name','@rpath/libKeplerProgramImport.dylib',
     '-o',str(root/'build/libKeplerProgramImport.dylib')],'library-build')
for tool in ['nak_memory_bench','compute_suite_probe']:
    cmd=['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools'/f'{tool}.mm'),'-I'+str(root/'src'),
         '-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),
         '-framework','Metal','-framework','Foundation']
    if tool=='compute_suite_probe':cmd+=['-framework','Accelerate']
    run(cmd+['-o',str(root/'build'/tool)],tool+'-build')

build=root/'build/mesa';entries=json.loads((build/'compile_commands.json').read_text())
entry=next(e for e in entries if e['file'].endswith('/nak_nir.c'))
flags=[a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj=root/'build/kepler_compute_suite.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/kepler_compute_suite.c'),'-o',str(obj)],'suite-compile',build)
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a',
          'src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a',
          'src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a',
          'src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/kepler_compute_suite'),str(obj)]+archives+
    ['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'suite-link',build)

for stem in ['add_buffers','kepler_carrier','kepler_shared_carrier','kepler_tiled_carrier']:
    run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src'/f'{stem}.metal'),
         '-o',str(root/'build'/f'{stem}.air')],stem+'-air')
    run(['xcrun','-sdk','macosx','metallib',str(root/'build'/f'{stem}.air'),'-o',str(root/'build'/f'{stem}.metallib')],stem+'-metallib')
run(['python3',str(root/'tools/build_air_compiler.py'),'--constant-buffer-index','2'],'air-add-compile')

def check(result):
    if result.get('device')!='NVIDIA GeForce GTX 880M':raise SystemExit('Wrong device')
    if result['mismatches'] or result['changed_guards']:raise SystemExit('Numerical or guard validation failed')
    if not result['import']['contract_verified'] or not result['import']['events']:raise SystemExit('Import contract missing')
    if any(not event['imported_code_identical'] for event in result['import']['events']):raise SystemExit('Different code imported')
    if result.get('dispatch_count_verified') is False:raise SystemExit('Missing GPU dispatches')

for memory in ['shared','managed','private','private_nocopy']:
    for policy in ['resident','roundtrip']:
        label=f'memory-{memory}-{policy}'
        text=run([str(root/'build/nak_memory_bench'),str(root/'build/kepler_carrier.metallib'),
                  str(root/'build/add_buffers-air-cb2.sass'),memory,policy,'1048576'],label)
        result=json.loads(text);check(result)
        path=out/(label+'.json');path.write_text(json.dumps(result,indent=2)+'\n')
        cases.append({'label':label,'result':str(path.relative_to(root)),'code':'build/add_buffers-air-cb2.sass'})

kernels=[('fp64',None,1041,'kepler_carrier'),('atomic32',None,1025,'kepler_carrier'),
         ('shuffle',None,1024,'kepler_carrier'),('shared_reduce',None,64,'kepler_shared_carrier')]
kernels += [('tiled_matmul',n,n*n,'kepler_tiled_carrier') for n in (64,128,256,512,1024)]
for kind,dimension,count,carrier in kernels:
    stem=kind if dimension is None else f'{kind}-{dimension}'
    cmd=[str(root/'build/kepler_compute_suite'),kind,str(root/'build'/f'{stem}.sass'),str(out/f'{stem}.asm')]
    if dimension:cmd.append(str(dimension))
    info=json.loads(run(cmd,stem+'-compile'));infoPath=out/(stem+'-shader-info.json');infoPath.write_text(json.dumps(info,indent=2)+'\n')
    listing=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',
                 str(root/'build'/f'{stem}.sass')],stem+'-decode')
    if '[unknown' in listing:raise SystemExit('Unknown decoded instruction/operand')
    for policy in (['resident','roundtrip'] if dimension==1024 else ['resident']):
        label=stem+'-'+policy
        text=run([str(root/'build/compute_suite_probe'),str(root/'build'/f'{carrier}.metallib'),
                  str(root/'build'/f'{stem}.sass'),str(infoPath),str(count),'nocopy',policy],
                  label,environment={'VECLIB_MAXIMUM_THREADS':'4'})
        result=json.loads(text);check(result)
        if result['blas_reference_mismatches']:raise SystemExit('Accelerate differs from independent CPU reference')
        path=out/(label+'.json');path.write_text(json.dumps(result,indent=2)+'\n')
        cases.append({'label':label,'result':str(path.relative_to(root)),'code':f'build/{stem}.sass'})

stem='tiled_counted-1024'
info=json.loads(run([str(root/'build/kepler_compute_suite'),'tiled_counted',str(root/'build'/f'{stem}.sass'),str(out/f'{stem}.asm'),'1024'],stem+'-compile'))
infoPath=out/(stem+'-shader-info.json');infoPath.write_text(json.dumps(info,indent=2)+'\n')
listing=run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(root/'build'/f'{stem}.sass')],stem+'-decode')
if '[unknown' in listing:raise SystemExit('Unknown counted-kernel instruction')
for batch in (1,4,12):
    label=f'{stem}-batch{batch}'
    text=run([str(root/'build/compute_suite_probe'),str(root/'build/kepler_tiled_carrier.metallib'),
              str(root/'build'/f'{stem}.sass'),str(infoPath),'1048576','nocopy','resident',str(batch)],
              label,environment={'VECLIB_MAXIMUM_THREADS':'4'})
    result=json.loads(text);check(result);assert result['dispatch_count_verified']
    path=out/(label+'.json');path.write_text(json.dumps(result,indent=2)+'\n')
    cases.append({'label':label,'result':str(path.relative_to(root)),'code':f'build/{stem}.sass'})

after=hashlib.sha256(driver.read_bytes()).hexdigest()
for case in cases:case['code_sha256']=hashlib.sha256((root/case['code']).read_bytes()).hexdigest()
manifest={'driver_before_sha256':before,'driver_after_sha256':after,'driver_unchanged':before==after,'cases':cases,
          'scope':'isolated application-local components; no system/OCLP installation or hardware register change'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if before!=after:raise SystemExit('Driver changed during the experiment')
run(['python3',str(root/'tools/make_compute_report.py'),'--input',str(out)],'report')
print('Results:',out)
