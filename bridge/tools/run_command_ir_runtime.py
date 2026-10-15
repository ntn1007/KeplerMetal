#!/usr/bin/env python3
"""Run one public-MSL→GPU IR→native command cohort on the shared lab lease."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',required=True);a=p.parse_args();build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');inp=json.loads((build/'inputs.json').read_text());assert sha(build/'application')==inp['executable_SHA256']
for n,h in inp['source_hashes'].items():assert sha(build/n)==h
for n,h in inp['assets_SHA256'].items():assert sha(build/'assets'/n)==h
for n,h in inp['runtime_SHA256'].items():assert sha(build/'runtime'/n)==h
out.mkdir(exist_ok=False);(out/'outputs').mkdir();shutil.copytree(build/'assets',out/'assets')
for n in [*inp['source_hashes'],'application','inputs.json']:shutil.copyfile(build/n,out/n)
(out/'application').chmod(0o755);sys.path.insert(0,str(build/'runtime'));from run_sdk_host import run_host
m=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),a.mode],ROOT)
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'PID':m['pid'],'exit_code':m['exit_code'],'runs':len(d['runs'])}))
