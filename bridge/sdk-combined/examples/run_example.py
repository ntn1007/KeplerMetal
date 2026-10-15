#!/usr/bin/env python3
"""Run an adapted CAS client through the shared lab reservation."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
SDK=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SDK/'runtime'))
from run_sdk_host import run_host
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reservation-root',type=Path,required=True);p.add_argument('--mode',choices=['register','prepare','execute','native'],default='prepare');a=p.parse_args();build=a.build.resolve();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'outputs').mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((build/'inputs.json').read_text());assert sha(build/'application')==inputs['executable_SHA256']
for n in ['application','client.mm','KeplerCPUICB.h','inputs.json']:shutil.copyfile(build/n,out/n)
(out/'application').chmod(0o755);shutil.copytree(build/'assets',out/'assets')
for n,h in inputs['assets_SHA256'].items():assert sha(out/'assets'/n)==h
abi=out/'assets/cpu_icb_native_cas_manifest.json';m=run_host(out/'application',out/'execution',[str(out/'assets'),str(abi),str(out/'outputs'),sha(abi),a.mode],a.reservation_root)
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'pid':m['pid'],'exit_code':m['exit_code'],'output':str(out)},indent=2))
