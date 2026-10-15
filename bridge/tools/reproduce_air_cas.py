#!/usr/bin/env python3
"""Compare unchanged native Metal with corrected AIR→NIR→SM30 in own processes.
Known native result failures are retained, never counted as GPU success.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, struct, subprocess

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();INPUT=args.input.resolve();OUT=args.out.resolve()
INPUT.relative_to(ROOT/'results');OUT.relative_to(ROOT/'results');assert not OUT.exists();OUT.mkdir()
assert len(json.loads((INPUT/'manifest.json').read_text())['records'])==2
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
system_paths=[Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'),
              Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin'),
              Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')]
before={str(p):sha(p) for p in system_paths}
commands=[];cases=[];captures=[]
def run(cmd,label,allowed=(0,),timeout=55):
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    (OUT/(label+'.stdout')).write_text(p.stdout);(OUT/(label+'.stderr')).write_text(p.stderr)
    commands.append({'label':label,'argv':cmd,'exit_code':p.returncode})
    (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label,p.returncode,flush=True)
    if p.returncode not in allowed:raise SystemExit(p.stderr[-4000:] or f'{label}: {p.returncode}')
    return p
def signed(exe,name,argv,allowed=(0,)):
    execution=OUT/(name+'-execution')
    run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),
         '--timeout','20','--']+argv,name+'-launch',allowed,45)
    process=json.loads((execution/'manifest.json').read_text())
    if process['authoritative_ps_status']:raise SystemExit('HALT: child remains present; do not restart')
    return execution,process

source=OUT/'air_cas_probe.mm';shutil.copyfile(ROOT/'tools/air_cas_probe.mm',source)
carrier_source=OUT/'air_cas_carrier.metal';shutil.copyfile(ROOT/'src/air_cas_carrier.metal',carrier_source)
shutil.copyfile(Path(__file__),OUT/Path(__file__).name)
library=ROOT/'build/import-audit/libKeplerProgramImport.dylib'
assert sha(library)=='7719a27c9b659d6b4d87e1d6015c51b4d2cefb3238c47eae11073c3dd975dcd6'
probe=OUT/'air_cas_probe'
run(['clang++','-O2','-std=c++17','-fno-objc-arc',str(source),'-I'+str(ROOT/'src'),
     '-L'+str(library.parent),'-lKeplerProgramImport','-Wl,-rpath,'+str(library.parent),
     '-framework','Metal','-framework','Foundation','-o',str(probe)],'build-probe')
run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(carrier_source),
     '-o',str(OUT/'carrier.air')],'carrier-metal')
carrier=OUT/'carrier.metallib'
run(['xcrun','metallib',str(OUT/'carrier.air'),'-o',str(carrier)],'carrier-metallib')

configurations=[('carrier_control','device',1)]
configurations += [(mode,space,variant) for space in ['device','threadgroup']
                   for mode in ['native','air_nak'] for variant in [0,1]]
for mode,space,variant in configurations:
    name=f'{space}-{mode}-v{variant}';data=OUT/(name+'-outputs');data.mkdir()
    directory=INPUT/space
    plan={'mode':mode,'space':space,'variant':variant,'library':str(directory/'test.metallib'),
          'carrier':str(carrier),'code':str(directory/'program.sass'),
          'info':json.loads((directory/'info.json').read_text())}
    path=OUT/(name+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n')
    execution,process=signed(probe,name,[str(path),str(data)],(0,10))
    result=json.loads((execution/'execution.stdout').read_text())
    assert result.get('GPU_dispatch') and len(result['runs'])==3 and not result['guard_mismatches']
    if mode=='air_nak':
        assert result['import']['contract_verified']
        assert all(event['imported_code_identical'] and event['metadata_bytes_preserved_except_import_fields']
                   for event in result['import']['events'])
        assert not result['mismatches'],result
    if mode=='carrier_control' or space=='device':assert not result['mismatches'],result
    cases.append({'name':name,'plan':plan,'execution':str(execution),'process':process,'result':result})
    (OUT/'results.json').write_text(json.dumps(cases,indent=2)+'\n')

# Observe unchanged native programs after execution evidence, in separate
# processes that create pipelines but do not dispatch any GPU command.
for space in ['device','threadgroup']:
    native=OUT/(space+'-native-compiler');native.mkdir()
    execution,process=signed(ROOT/'build/compiler_output_trace',space+'-capture',
        [str(INPUT/space/'test.metallib'),str(native),'compute','test'])
    capture=json.loads((execution/'execution.stdout').read_text());assert not capture['gpu_dispatch']
    programs=[]
    for record in capture['captures']:
        data=Path(record['file']).read_bytes();version,total=struct.unpack_from('<II',data)
        assert version in (7,8,9) and total==len(data)
        offset=8;seen=set();code=None;metadata=None
        for _ in range(32):
            assert offset not in seen and offset+16<=len(data);seen.add(offset)
            nxt,kind,size=struct.unpack_from('<QII',data,offset);start=offset+16;assert start+size<=len(data)
            if kind==0x10005:code=data[start:start+size]
            if kind==0x10004:metadata=data[start:start+size]
            if not nxt:break
            assert nxt>=16+size;offset+=nxt
        assert code and metadata and len(metadata)==232
        path=native/'native.sass';path.write_bytes(code)
        programs.append({'path':str(path),'bytes':len(code),'sha256':sha(path),
                         'metadata_registers':struct.unpack_from('<I',metadata,28)[0]})
    assert len(programs)==1
    captures.append({'space':space,'execution':str(execution),'process':process,'programs':programs})
# Decode exactly these program bytes; partial native decoding is recorded,
# while execution correctness is established by the separate byte oracles.
decodings=[]
for space in ['device','threadgroup']:
    for mode in ['native','nak']:
        code=OUT/(space+'-native-compiler/native.sass') if mode=='native' else INPUT/space/'program.sass'
        execution,process=signed(ROOT/'build/envydis-only/envydis/envydis',space+'-'+mode+'-decode',
            ['-m','gf100','-V','gk104','-i','-n',str(code)])
        listing=(execution/'execution.stdout').read_text()
        decodings.append({'space':space,'mode':mode,'code_path':str(code),'code_sha256':sha(code),
                          'execution':str(execution),'process':process,
                          'unknown_instructions':listing.count('[unknown instruction]'),
                          'unknown_annotations':listing.count('[unknown')})
after={str(p):sha(p) for p in system_paths};assert before==after
manifest={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'system_before':before,'system_after':after,'system_unchanged':before==after,
          'input':str(INPUT),'cases':len(cases),'raw_captures':sum(len(c['result']['runs']) for c in cases),
          'source_hashes':{str(p):sha(p) for p in [source,carrier_source,ROOT/'src/KeplerProgramImport.h',
                          ROOT/'tools/run_signed_probe.py',library]},
          'native_captures':captures,'decodings':decodings,'performance_benchmark':False,
          'scope':'Native vs translated same AIR; application-local alternative, not installed-driver repair.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'cases':len(cases),'raw_captures':manifest['raw_captures'],
                  'failed_cases':[c['name'] for c in cases if not c['result']['passed']]},indent=2))
