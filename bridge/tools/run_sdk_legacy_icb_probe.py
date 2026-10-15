#!/usr/bin/env python3
"""Run old bounded manifest/XYZ clients linked to the current public SDK."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--variant',choices=['manifest','grid3d'],required=True);p.add_argument('--mode',choices=['prepare','execute'],required=True);a=p.parse_args()
build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'outputs').mkdir()
inp=json.loads((build/'inputs.json').read_text());prefix='cpu_icb_'+a.variant
for n,h in inp['source_hashes'].items():assert sha(build/n)==h;shutil.copyfile(build/n,out/n)
for n in [prefix+'.metallib']+(['foreign.metallib']if a.variant=='manifest'else[]):shutil.copyfile(build/n,out/n)
for n in ['inputs.json','commands.json',prefix+'_probe']:shutil.copyfile(build/n,out/n)
exe=out/(prefix+'_probe');exe.chmod(0o755);assert sha(exe)==inp['executable_SHA256']
sys.path.insert(0,str(build/'runtime'));from run_sdk_host import run_host
args=[str(out/(prefix+'.metallib')),str(out/(prefix+'.json'))]+([str(out/'foreign.metallib')]if a.variant=='manifest'else[])+[str(out/'outputs'),a.mode]
m=run_host(exe,out/'execution',args,ROOT)
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');assert d['passed']
c=json.loads((out/'commands.json').read_text());c.append({'label':'observe','argv':args,'exit_code':m['exit_code']});(out/'commands.json').write_text(json.dumps(c,indent=2)+'\n')
print(json.dumps({'status':'PASS','PID':m['pid'],'mode':a.mode,'variant':a.variant,'core_source_compilations':0}))
