#!/usr/bin/env python3
"""Extend identical AIR/native and AIR/NAK CAS to warps, partial warps and contention."""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, subprocess

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--locals',default='32,33,128');parser.add_argument('--groups',type=int,default=3)
args=parser.parse_args();locals_=[int(v) for v in args.locals.split(',')]
assert locals_ and len(set(locals_))==len(locals_) and all(1<=n<=128 for n in locals_)
assert 1<=args.groups<=3
OUT=args.out.resolve();OUT.relative_to(ROOT/'results');assert not OUT.exists();OUT.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'),
       Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin'),
       Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')]
before={str(p):sha(p) for p in files};commands=[];records=[]
def run(cmd,label,allowed=(0,),timeout=55):
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    (OUT/(label+'.stdout')).write_text(p.stdout);(OUT/(label+'.stderr')).write_text(p.stderr)
    commands.append({'label':label,'argv':cmd,'exit_code':p.returncode})
    (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,p.returncode,flush=True)
    if p.returncode not in allowed:raise SystemExit(p.stderr[-4000:] or f'{label}: {p.returncode}')
    return p
def signed(exe,label,argv,allowed=(0,)):
    execution=OUT/(label+'-execution')
    run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),
         '--timeout','20','--']+argv,label+'-launch',allowed,45)
    process=json.loads((execution/'manifest.json').read_text())
    if process['authoritative_ps_status']:raise SystemExit('HALT: live signed child; do not restart')
    return execution,process

compiler_dir=ROOT/'results/cas-lowering-final';compiler=compiler_dir/'air_cas_compile'
compiler_manifest=json.loads((compiler_dir/'manifest.json').read_text())
assert sha(compiler)==compiler_manifest['compiler_sha256']
source=OUT/'air_cas_probe.mm';carrier_source=OUT/'air_cas_carrier.metal'
shutil.copyfile(ROOT/'tools/air_cas_probe.mm',source);shutil.copyfile(ROOT/'src/air_cas_carrier.metal',carrier_source)
shutil.copyfile(Path(__file__),OUT/Path(__file__).name)
library=ROOT/'build/import-audit/libKeplerProgramImport.dylib'
assert sha(library)=='7719a27c9b659d6b4d87e1d6015c51b4d2cefb3238c47eae11073c3dd975dcd6'
probe=OUT/'air_cas_probe'
run(['clang++','-O2','-std=c++17','-fno-objc-arc',str(source),'-I'+str(ROOT/'src'),
     '-L'+str(library.parent),'-lKeplerProgramImport','-Wl,-rpath,'+str(library.parent),
     '-framework','Metal','-framework','Foundation','-o',str(probe)],'build-probe')
run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-DCARRIER_LOCAL_MAX=128','-c',
     str(carrier_source),'-o',str(OUT/'carrier.air')],'carrier-metal')
carrier=OUT/'carrier.metallib';run(['xcrun','metallib',str(OUT/'carrier.air'),'-o',str(carrier)],'carrier-metallib')
fixtures=[]
for local in locals_:
    for space in ['device','threadgroup']:
        for contended in [False,True]:
            name=f'{space}-{"contended" if contended else "unique"}-l{local}'
            directory=OUT/name;directory.mkdir()
            if space=='device':init='device atomic_uint *a=&global['+('group*p.local' if contended else 'i')+'];'
            else:
                init=f'threadgroup atomic_uint shared[{1 if contended else local}];threadgroup atomic_uint *a=&shared[{"0" if contended else "tid"}];'
                if contended:init+='if(tid==0)'
                init+='atomic_store_explicit(a,initial,memory_order_relaxed);threadgroup_barrier(mem_flags::mem_threadgroup);'
            flag='mem_device' if space=='device' else 'mem_threadgroup'
            text=('#include <metal_stdlib>\nusing namespace metal;\nstruct P {uint seed,n,local,groups,variant;};\n'
                  'kernel void test(constant P &p [[buffer(0)]],device uint4 *out [[buffer(1)]],'
                  'device atomic_uint *global [[buffer(3)]],uint i [[thread_position_in_grid]],'
                  'uint tid [[thread_index_in_threadgroup]],uint group [[threadgroup_position_in_grid]]){'
                  'uint initial=p.seed+group*0x10001u;uint replacement=p.seed^0x55667788u;'+init+
                  'uint compare=initial^(p.variant?1u:0u);bool success=atomic_compare_exchange_weak_explicit('
                  'a,&compare,replacement,memory_order_relaxed,memory_order_relaxed);'
                  'threadgroup_barrier(mem_flags::'+flag+');uint final=atomic_load_explicit(a,memory_order_relaxed);'
                  'out[i]=uint4(compare,uint(success),final,i);}\n')
            (directory/'test.metal').write_text(text)
            run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(directory/'test.metal'),
                 '-o',str(directory/'test.air')],name+'-metal')
            run(['xcrun','metallib',str(directory/'test.air'),'-o',str(directory/'test.metallib')],name+'-metallib')
            execution,process=signed(compiler,name+'-offline',[str(directory/'test.air'),str(directory),'test',str(local),'2'])
            info=json.loads((execution/'execution.stdout').read_text())
            assert info['sm']==30 and info['local_size']==[local,1,1]
            assert info['buffer_slots']==4 and info['grid_offset']==32 and info['push_bytes']==56
            assert not info['scratch_bytes'] and not info['crs_bytes'] and info['shared_bytes']<=512
            (directory/'info.json').write_text(json.dumps(info,indent=2)+'\n')
            fixtures.append({'space':space,'local':local,'contended':contended,'directory':str(directory),'info':info})
            (OUT/'fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n')

plans=[{'mode':'carrier_control','space':'device','local':local,'groups':args.groups,'contended':False,
        'variant':1,'carrier':str(carrier)} for local in locals_]
for fixture in fixtures:
    for mode in ['native','air_nak']:
        for variant in [0,1]:
            directory=Path(fixture['directory'])
            plans.append({k:fixture[k] for k in ['space','local','contended','info']} |
                         {'mode':mode,'variant':variant,'groups':args.groups,'carrier':str(carrier),
                          'library':str(directory/'test.metallib'),'code':str(directory/'program.sass')})
for plan in plans:
    name=f'{plan["space"]}-{"contended" if plan["contended"] else "unique"}-l{plan["local"]}-g{plan["groups"]}-{plan["mode"]}-v{plan["variant"]}'
    path=OUT/(name+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n')
    output=OUT/(name+'-outputs');output.mkdir()
    execution,process=signed(probe,name,[str(path),str(output)],(0,10))
    result=json.loads((execution/'execution.stdout').read_text())
    assert result.get('GPU_dispatch') and len(result['runs'])==3 and not result['guard_mismatches']
    records.append({'name':name,'plan':plan,'result':result,'process':process,'execution':str(execution)})
    (OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n')
    if plan['mode']=='air_nak':assert result['passed'] and result['import']['contract_verified'],result
    if plan['mode']=='carrier_control' or plan['space']=='device':assert result['passed'],result
after={str(p):sha(p) for p in files};assert after==before
manifest={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_before':before,
          'system_after':after,'system_unchanged':True,'cases':len(records),'locals':locals_,'groups':args.groups,
          'fixtures':len(fixtures),'compiler_reference':str(compiler_dir),'compiler_sha256':sha(compiler),
          'source_snapshot_sha256':{str(p):sha(p) for p in [source,carrier_source,OUT/Path(__file__).name]},
          'scope':'Single-call weak CAS with multiple groups/lanes, independent counters and contention; no general progress, performance or system-driver qualification.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'cases':len(records),'passed':sum(c['result']['passed'] for c in records),
                  'failed':[c['name'] for c in records if not c['result']['passed']]},indent=2))
