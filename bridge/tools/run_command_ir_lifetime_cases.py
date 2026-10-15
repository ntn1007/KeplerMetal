#!/usr/bin/env python3
"""Run the remaining lifetime cohorts sequentially under the common GPU lease."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);p.add_argument('--full',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[];modes=['keep','drop','restore','split_restore','copy_restore','no_producer_restore','no_consumer_restore','cancel_legacy','cancel_leases']if a.full else['keep','drop','split_restore','copy_restore','no_consumer_restore']
for mode in modes:
 target=ROOT/'results'/(a.prefix+'-'+mode)
 for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',target,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_lifetime.py',target])]:
  cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);(out/(mode+'-'+phase+'.stdout')).write_text(r.stdout);(out/(mode+'-'+phase+'.stderr')).write_text(r.stderr);history.append({'mode':mode,'phase':phase,'argv':cmd,'exit_code':r.returncode,'directory':str(target)});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n');assert not r.returncode,(mode,phase,r.stderr[-2500:])
 print(mode,'GPU+CPU PASS',flush=True)
(out/'completion.json').write_text(json.dumps({'status':'PASS','cohorts':len(modes),'trials':4*len(modes),'runtime_unchanged':True,'full_objective_complete':False},indent=2)+'\n')
