#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,shutil,sys
SDK=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SDK/'runtime'))
from run_sdk_host import run_host
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reservation-root',type=Path,required=True);p.add_argument('--mode',choices=['prepare','execute','no_producer'],default='prepare');p.add_argument('--client',choices=['arithmetic','conversions','reverse'],default='arithmetic');p.add_argument('--trials',type=int,choices=[1,9],default=9);a=p.parse_args();build=a.build.resolve();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'outputs').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inp=json.loads((build/'inputs.json').read_text());assert sha(build/'application')==inp['executable_SHA256']
for n,h in inp['source_hashes'].items():assert sha(build/n)==h
client={'arithmetic':'fp64_client.mm','conversions':'fp64_conversion_client.mm','reverse':'fp64_reverse_client.mm'}[a.client]
assert client in inp['source_hashes']
for n in ['application',client,'KeplerFP64.h','inputs.json']:shutil.copyfile(build/n,out/n)
(out/'application').chmod(0o755);shutil.copytree(build/'assets',out/'assets')
for n,h in inp['assets_SHA256'].items():assert sha(out/'assets'/n)==h
m=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),a.mode,str(a.trials)],a.reservation_root)
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'pid':m['pid'],'exit_code':m['exit_code']}))
