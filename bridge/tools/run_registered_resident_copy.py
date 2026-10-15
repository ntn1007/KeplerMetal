#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reservation-root',type=Path,default=ROOT);p.add_argument('--mode',choices=['prepare','chain','range','chain_completed','range_completed','no_second','prepare_short','copy_short'],required=True);a=p.parse_args();build=a.build.resolve();out=a.out.resolve();reservation=a.reservation_root.resolve();out.relative_to(reservation/'results');out.mkdir(exist_ok=False);(out/'outputs').mkdir();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();inp=json.loads((build/'inputs.json').read_text())
assert sha(build/'application')==inp['executable_SHA256']
for n,h in inp['source_hashes'].items():assert sha(build/n)==h;shutil.copyfile(build/n,out/n)
for n,h in inp['runtime_SHA256'].items():assert sha(build/'runtime'/n)==h
shutil.copytree(build/'assets',out/'assets')
for n,h in inp['assets_SHA256'].items():assert sha(out/'assets'/n)==h
for n in ['application','inputs.json']:shutil.copyfile(build/n,out/n)
(out/'application').chmod(0o755);sys.path.insert(0,str(build/'runtime'));from run_sdk_host import run_host
m=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),a.mode],reservation);d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'PID':m['pid'],'exit_code':m['exit_code']}))
