#!/usr/bin/env python3
"""Run one immutable application copy and retain its actual terminal handle."""
from pathlib import Path
import argparse,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--sdk',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['negative','prepare','native','execute'],required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();(out/'outputs').mkdir();sdk=a.sdk.resolve();build=a.build.resolve();shutil.copyfile(build/'inputs.json',out/'inputs.json')
r=subprocess.run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(build/'cas_example'),'--out',str(out/'execution'),'--timeout','25','--',str(sdk/'assets'),str(sdk/'assets/client-manifest.json'),str(out/'outputs'),a.mode],capture_output=True,text=True,timeout=40)
(out/'runner.stdout').write_text(r.stdout);(out/'runner.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'pid':m['pid'],'exit_code':m['exit_code'],'output':str(out)}))
