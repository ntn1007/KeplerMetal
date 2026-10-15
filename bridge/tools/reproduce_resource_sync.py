#!/usr/bin/env python3
"""Bounded native tests of heaps/fences/events/ICBs; no system modification."""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, subprocess
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--only',choices=['initial','heap_alias'],default='initial')
args=parser.parse_args();OUT=args.out.resolve();OUT.relative_to(ROOT/'results');assert not OUT.exists();OUT.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
system=[Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'),
        Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin'),
        Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')]
before={str(p):sha(p) for p in system};commands=[];records=[]
sources=[ROOT/'tools/resource_sync_probe.mm',ROOT/'src/resource_sync_probe.metal',Path(__file__),ROOT/'tools/verify_resource_sync.py']
for source in sources:shutil.copyfile(source,OUT/source.name)
def run(cmd,label,allowed=(0,),timeout=55):
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    (OUT/(label+'.stdout')).write_text(p.stdout);(OUT/(label+'.stderr')).write_text(p.stderr)
    commands.append({'label':label,'argv':cmd,'exit_code':p.returncode});(OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label,p.returncode,flush=True)
    assert p.returncode in allowed,p.stderr[-4000:]
    return p
air=OUT/'resource_sync_probe.air';library=OUT/'resource_sync_probe.metallib';probe=OUT/'resource_sync_probe'
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.0','-c',str(OUT/'resource_sync_probe.metal'),'-o',str(air)],'metal-compile')
run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(library)],'metallib-link')
run(['xcrun','clang++','-O2','-std=c++17','-fobjc-arc',str(OUT/'resource_sync_probe.mm'),
     '-framework','Foundation','-framework','Metal','-o',str(probe)],'probe-build')
selection=['heap_alias'] if args.only=='heap_alias' else ['direct','control_missing_producer','heap','fence','event','shared_event','icb_compute','icb_render']
for kind in selection:
    plan={'kind':kind,'library':str(library),'own_resource_cap_bytes':20*1024*1024}
    path=OUT/(kind+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n');outputs=OUT/(kind+'-outputs');outputs.mkdir()
    execution=OUT/(kind+'-execution')
    run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(probe),'--out',str(execution),
         '--timeout','20','--',str(path),str(outputs)],kind+'-launch',tuple(range(12)))
    process=json.loads((execution/'manifest.json').read_text())
    assert not process['authoritative_ps_status'] and not process['SIGKILL_requested'],'STOP: child still alive or termination requested'
    result=json.loads((execution/'execution.stdout').read_text())
    record={'kind':kind,'plan':plan,'process':process,'result':result};records.append(record)
    (OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n')
    print(kind,result.get('failure_stage','PASS'),flush=True)
    if kind=='direct':assert result.get('passed'),'Reference failed'
    elif kind=='control_missing_producer':assert result.get('negative_control_detected') and not result.get('passed')
    elif result.get('GPU_dispatch') and not result.get('passed'):raise SystemExit('STOP: optional GPU path failed; inspect before any more dispatch')
after={str(p):sha(p) for p in system};assert before==after
manifest={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_before':before,'system_after':after,
          'source_hashes':{p.name:sha(OUT/p.name) for p in sources},'library_sha256':sha(library),'probe_sha256':sha(probe),
          'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),
          'scope':'Native API samples with exact numerical GPU readback; factories and allocation alone never counted as functional; no benchmark or system change.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Completed bounded native API cases',len(records))
