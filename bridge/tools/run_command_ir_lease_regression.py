#!/usr/bin/env python3
"""Check changed example callers against the unchanged qualified runtime."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);p.add_argument('--build-prefix',default='command-ir-lifetime-production');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[]
cases={'grid3d':['no_producer','basic','barrier','copy','split'],'v1':['basic','copy','split','reset','no_producer'],'v2-three':['basic','copy','split','reset','no_producer'],'v2-combined':['basic','split','copy']}
for kind,modes in cases.items():
 build=ROOT/'results'/(a.build_prefix+'-'+kind+'-build-20261015')
 for mode in modes:
  target=ROOT/'results'/(a.prefix+'-'+kind+'-'+mode)
  for phase,args in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',build,'--out',target,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools'/('verify_command_ir_grid3d.py'if kind=='grid3d'else'verify_command_ir_runtime.py'),target])]:
   args=[str(x)for x in args];r=subprocess.run(args,capture_output=True,text=True,timeout=75);label=kind+'-'+mode+'-'+phase;(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);history.append({'kind':kind,'mode':mode,'phase':phase,'argv':args,'exit_code':r.returncode,'directory':str(target)});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n');assert not r.returncode,(label,r.stderr[-2500:])
  print(kind,mode,'GPU+CPU PASS',flush=True)
(out/'completion.json').write_text(json.dumps({'status':'PASS','cohorts':sum(map(len,cases.values())),'runtime_unchanged':True,'full_objective_complete':False},indent=2)+'\n')
