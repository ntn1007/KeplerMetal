#!/usr/bin/env python3
"""Fresh signed process for one offline-approved FP64 shader and its fixtures."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['prepare','execute','native'],default='prepare');a=p.parse_args();host=a.host.resolve();host.relative_to(ROOT/'results');planPath=a.plan.resolve();planPath.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();(out/'outputs').mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
hostData=json.loads((host/'inputs.json').read_text());assert sha(host/'fp64_math_probe')==hostData['executable_SHA256']
for n,h in hostData['source_SHA256'].items():assert sha(host/n)==h;shutil.copyfile(host/n,out/n)
exe=out/'fp64_math_probe';shutil.copyfile(host/'fp64_math_probe',exe);exe.chmod(0o755)
plan=json.loads(planPath.read_text());sourceCode=Path(plan['code']);sourceCarrier=Path(plan['carrier']);assert sha(sourceCode)==plan['code_SHA256'] and sha(sourceCarrier)==plan['carrier_SHA256'];shutil.copyfile(sourceCode,out/'program.sass');shutil.copyfile(sourceCarrier,out/'carrier.metallib');plan['code']=str(out/'program.sass');plan['carrier']=str(out/'carrier.metallib')
for f in plan['fixtures']:
 for name in ['A','B','C']:
  source=Path(f[name]);assert sha(source)==f[name+'_SHA256'];target=out/f"trial-{f['trial']}-{name}.input.bin";shutil.copyfile(source,target);f[name]=str(target)
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(out/'inputs.json').write_text(json.dumps(hostData,indent=2)+'\n')
argv=['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30','--',str(out/'plan.json'),str(out/'outputs'),a.mode];r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'observe.stdout').write_text(r.stdout);(out/'observe.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-2500:]
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'operation':d['operation'],'local':d['local'],'PID':m['pid']}))
