#!/usr/bin/env python3
"""Replay fixed CPU-only byte/profile controls against one exact runtime."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();library=a.library.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);commands=[]
assert sha(library/'libKeplerMetal.a')==json.loads((library/'manifest.json').read_text())['static_library_SHA256']
def run(argv,label):
 argv=[str(x)for x in argv];r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2000:];return r.stdout
for n in ['resident_primer_compare_probe','resident_profile_policy_probe']:
 shutil.copyfile(ROOT/'tools'/(n+'.mm'),out/(n+'.mm'))
shutil.copyfile(library/'src/KeplerNativeCommands.h',out/'KeplerNativeCommands.h')
for n in ['resident_primer_compare_probe','resident_profile_policy_probe']:
 run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/(n+'.mm'),'-L',library,'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/n],n+'-build')
streams=json.loads((ROOT/'results/command-ir-v2-final-primer-controls-20261015/receipt.json').read_text())['streams']
for i,row in enumerate(streams):
 assert sha(ROOT/row['path'])==row['SHA256'];d=json.loads(run([out/'resident_primer_compare_probe',ROOT/row['path']],f'compare-{i}'));assert len(d['checks'])==12 and all(x['accepted']==x['expected_accepted']for x in d['checks']);(out/f'compare-{i}.json').write_text(json.dumps(d,indent=2)+'\n')
d=json.loads(run([out/'resident_profile_policy_probe'],'policy'));assert len(d['checks'])==9 and all(x['accepted']==x['expected']for x in d['checks']);(out/'policy.json').write_text(json.dumps(d,indent=2)+'\n')
receipt={'status':'PASS','primer_checks':60,'policy_checks':9,'streams':streams,'library_SHA256':sha(library/'libKeplerMetal.a'),'GPU_executed':False};(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='streams'}))
