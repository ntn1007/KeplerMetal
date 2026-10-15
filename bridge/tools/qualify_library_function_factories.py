#!/usr/bin/env python3
"""Serialize three library forms and five public function factory selectors."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[]
# Constants: use an unused value (source has no function constants). Descriptor:
# use a native alias. The default data/plain path is covered by the six-PSO suite.
cases=[(l,f,m)for l in range(3)for f in [0,3,6,7,8]if(l,f)!=(0,0)for m in ['basic','barrier','copy']]
for library,function,mode in cases:
 target=ROOT/'results'/(a.prefix+f'-l{library}-f{function}-'+mode)
 for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',target,'--mode',f'5:1:4:{library}:{function}:{mode}']),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_dataflow.py',target])]:
  cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);(out/(f'l{library}-f{function}-{mode}-{phase}.stdout')).write_text(r.stdout);(out/(f'l{library}-f{function}-{mode}-{phase}.stderr')).write_text(r.stderr);history.append({'library_factory':library,'function_factory':function,'mode':mode,'phase':phase,'argv':cmd,'result':str(target),'exit_code':r.returncode});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
  if r.returncode:
   (out/'status.json').write_text(json.dumps({'status':'FAIL','library_factory':library,'function_factory':function,'mode':mode,'phase':phase,'rerun':False},indent=2)+'\n');print(r.stdout,r.stderr,flush=True);sys.exit(r.returncode)
 print(library,function,mode,'GPU+CPU PASS',flush=True)
(out/'status.json').write_text(json.dumps({'status':'PASS','cohorts':len(cases),'trials':4*len(cases),'full_objective_complete':False},indent=2)+'\n')
