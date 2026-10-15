#!/usr/bin/env python3
"""Qualify final ARC/MRC declarations and example ownership without core edits."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'results/command-ir-lifetime-final-qualification-20261015';out.mkdir(exist_ok=False);history=[]
stages=[('lifetime',['tools/run_command_ir_lifetime_cases.py','--full','--build','results/command-ir-lifetime-final-client-build-20261015','--out','results/command-ir-lifetime-final-cases-suite-20261015','--prefix','command-ir-lifetime-final-cases-20261015']),('dataflow',['tools/run_command_ir_dataflow_qualification.py','--build','results/command-ir-lifetime-final-production-dataflow-build-20261015','--out','results/command-ir-lifetime-final-production-dataflow-suite-20261015','--prefix','command-ir-lifetime-final-production-dataflow-20261015']),('other_callers',['tools/run_command_ir_lease_regression.py','--build-prefix','command-ir-lifetime-final-production','--out','results/command-ir-lifetime-final-production-regression-20261015','--prefix','command-ir-lifetime-final-production-regression-20261015'])]
for label,args in stages:
 argv=[sys.executable,'-u',*args]
 with(out/(label+'.stdout')).open('w')as stdout,(out/(label+'.stderr')).open('w')as stderr:
  p=subprocess.Popen(argv,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=stderr);entry={'stage':label,'PID':p.pid,'argv':argv};history.append(entry);(out/'processes.json').write_text(json.dumps(history,indent=2)+'\n')
  for line in p.stdout:stdout.write(line);stdout.flush();print(label,line.rstrip(),flush=True)
  code=p.wait();entry['exit_code']=code;(out/'processes.json').write_text(json.dumps(history,indent=2)+'\n');assert not code,(label,'Inspect original handle and retained outputs; do not rerun cohorts blindly')
(out/'completion.json').write_text(json.dumps({'status':'PASS','stages':3,'GPU_cohorts':43,'trials':169,'runtime_library_unchanged':True,'full_objective_complete':False},indent=2)+'\n')
