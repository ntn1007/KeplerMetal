#!/usr/bin/env python3
"""Serialize native/imported local-memory cases and missing-dispatch controls."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);p.add_argument('--control-reference',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
build=a.build.resolve();control=a.control_reference.resolve();inp=json.loads((build/'inputs.json').read_text());ci=json.loads((control/'inputs.json').read_text());assert ci['executable_SHA256']==inp['executable_SHA256']and ci['static_library_SHA256']==inp['static_library_SHA256']
history=[{'mode':'nak:local_control','phase':'CPU','result':str(control),'exit_code':0,'reused_current_control':True}]
functions=['local_control','local32','local256','local1024','pressure32','pressure64','pressure96'];modes=functions+['nak:'+x for x in functions if x!='local_control']+['nak:pressure32_forced_spill']+['no_dispatch:local1024','no_dispatch:pressure96','nak:no_dispatch:local1024','nak:no_dispatch:pressure96']
for mode in modes:
 target=ROOT/'results'/(a.prefix+'-'+mode.replace(':','-'))
 for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',build,'--out',target,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools/verify_local_memory.py',target])]:
  cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True);label=mode.replace(':','-')+'-'+phase;(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);history.append({'mode':mode,'phase':phase,'result':str(target),'argv':cmd,'exit_code':r.returncode});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
  if r.returncode:
   (out/'status.json').write_text(json.dumps({'status':'FAIL','mode':mode,'phase':phase,'retry':False})+'\n');print(mode,phase,r.stdout,r.stderr,flush=True);raise SystemExit(r.returncode)
 print(mode,'GPU+CPU PASS',flush=True)
(out/'status.json').write_text(json.dumps({'status':'PASS','cohorts':len(modes)+1,'positive_trials':180,'negative_trials':48,'full_objective_complete':False},indent=2)+'\n')
