#!/usr/bin/env python3
"""Serialize public queue/compute factory dataflow cases on the shared GPU lease."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[]
# Plain queue/plain encoder is already covered by the six-factory matrix.
cases=[(q,e,m)for q in range(2)for e in range(5)if(q,e)!=(0,0)for m in ['basic','barrier','copy']]
for q,e,mode in cases:
 target=ROOT/'results'/(a.prefix+f'-q{q}-e{e}-'+mode)
 for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',target,'--mode',f'5:{q}:{e}:{mode}']),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_dataflow.py',target])]:
  cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);(out/(f'q{q}-e{e}-{mode}-{phase}.stdout')).write_text(r.stdout);(out/(f'q{q}-e{e}-{mode}-{phase}.stderr')).write_text(r.stderr);history.append({'queue_factory':q,'encoder_factory':e,'mode':mode,'phase':phase,'argv':cmd,'result':str(target),'exit_code':r.returncode});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
  if r.returncode:
   (out/'status.json').write_text(json.dumps({'status':'FAIL','queue_factory':q,'encoder_factory':e,'mode':mode,'phase':phase,'rerun':False},indent=2)+'\n');print(r.stdout,r.stderr,flush=True);sys.exit(r.returncode)
 print(q,e,mode,'GPU+CPU PASS',flush=True)
(out/'status.json').write_text(json.dumps({'status':'PASS','cohorts':len(cases),'trials':4*len(cases),'full_objective_complete':False},indent=2)+'\n')
