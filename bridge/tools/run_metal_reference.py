#!/usr/bin/env python3
"""Fresh signed Metal reference process with the common cooperative reservation."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reservation-root',type=Path,required=True);p.add_argument('--mode',choices=['caps','prepare','native','native_icb','execute'],required=True);a=p.parse_args();build=a.build.resolve();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'outputs').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((build/'inputs.json').read_text());assert sha(build/'application')==inputs['executable_SHA256']
for n,h in inputs['runtime_SHA256'].items():assert sha(build/'runtime'/n)==h
sys.path.insert(0,str(build/'runtime'))
from run_sdk_host import run_host
for n in ['application','metal_reference_client.mm','KeplerCPUICB.h','cpu_icb_literal_lut.metal','inputs.json']:shutil.copyfile(build/n,out/n)
(out/'application').chmod(0o755);shutil.copytree(build/'assets',out/'assets')
for n,h in inputs['source_hashes'].items():assert sha(out/n)==h
for n,h in inputs['assets_SHA256'].items():assert sha(out/'assets'/n)==h
m=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),a.mode],a.reservation_root)
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'PID':m['pid'],'status':d.get('status','CAPABILITIES_ONLY')}))
