#!/usr/bin/env python3
"""Qualify the alias-corrected runtime once, preserving all earlier attempts."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/command-ir-dataflow-full-nonregression-20261015';OUT.mkdir(exist_ok=False);history=[]
lib='d88158307ed566d1a048f7f729c2896419c6836b3f44899ab6711a59850456fc'
api=ROOT/'results/command-ir-dataflow-API-refusals-20261015';assert json.loads((api/'results.json').read_text())['API_refusals']==11;assert json.loads((api/'independent-verification.json').read_text())['status']=='PASS'
def execute(label,args):
 r=subprocess.run([str(x)for x in args],capture_output=True,text=True,timeout=55);(OUT/(label+'.stdout')).write_text(r.stdout);(OUT/(label+'.stderr')).write_text(r.stderr);history.append({'label':label,'argv':[str(x)for x in args],'exit_code':r.returncode});(OUT/'commands.json').write_text(json.dumps(history,indent=2)+'\n');assert not r.returncode,(label,r.stderr[-3000:])
def cohort(kind,build,mode,oracle):
 target=ROOT/'results'/('command-ir-dataflow-'+kind+'-'+mode.replace('_','-')+'-20261015');execute(kind+'-'+mode+'-run',['python3',ROOT/'tools/run_command_ir_runtime.py','--build',ROOT/'results'/build,'--out',target,'--mode',mode]);execute(kind+'-'+mode+'-verify',['python3',ROOT/'tools'/oracle,target]);assert json.loads((target/'inputs.json').read_text())['static_library_SHA256']==lib;print(kind,mode,'PASS',flush=True)
grid=['no_producer','basic','threads','barrier','copy','reset','split','bad_flags','bad_pipeline','bad_address0','bad_address1','bad_address2','bad_parameters','bad_groups_x','bad_groups_y','bad_groups_z','bad_local_z','bad_kind','bad_stage','bad_reserved','bad_shared','bad_threads']
for mode in grid:cohort('grid3d','command-ir-dataflow-grid3d-client-20261015',mode,'verify_command_ir_grid3d.py')
(OUT/'grid3d-complete.json').write_text(json.dumps({'status':'PASS','modes':22,'trials':132,'static_library_SHA256':lib},indent=2)+'\n')
modes=['basic','barrier','clear','copy','reset','no_producer','split','bad_flags','bad_tag','bad_pipeline','bad_address','bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_stage','bad_error','bad_reserved']
for kind,items in [('v1',modes),('v2-three',modes),('v2-combined',modes[:7]+['bad_shared'])]:
 for mode in items:cohort(kind,'command-ir-dataflow-'+kind+'-client-20261015',mode,'verify_command_ir_runtime.py')
(OUT/'public-complete.json').write_text(json.dumps({'status':'PASS','v1_trials':60,'v2_three_trials':60,'v2_combined_trials':24,'static_library_SHA256':lib},indent=2)+'\n')
build=ROOT/'results/command-ir-dataflow-regression-clients-20261015';assert json.loads((build/'client-builds.json').read_text())['static_library_SHA256']==lib
args=['python3','-u',str(ROOT/'tools/run_command_ir_v2_legacy_regression.py'),'--clients',str(build),'--out',str(ROOT/'results/command-ir-dataflow-legacy-suite-20261015'),'--result-prefix','command-ir-dataflow-legacy-regression']
with(OUT/'legacy.stdout').open('w')as stdout,(OUT/'legacy.stderr').open('w')as stderr:
 p=subprocess.Popen(args,stdout=stdout,stderr=stderr);(OUT/'legacy-process.json').write_text(json.dumps({'PID':p.pid,'argv':args},indent=2)+'\n');code=p.wait()
assert code==0,'Inspect final legacy suite/process; do not restart blindly'
(OUT/'completion.json').write_text(json.dumps({'status':'PASS','grid3d_trials':132,'v1_regression_trials':60,'v2_three_trials':60,'v2_combined_trials':24,'API_refusals':11,'API_positive_trials':6,'legacy_GPU_cohorts':129,'static_library_SHA256':lib},indent=2)+'\n');print('FINAL ALL COHORTS PASS',flush=True)
