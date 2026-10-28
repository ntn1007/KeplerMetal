#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the same local video host and choices without the board observer."""
import argparse,json,os,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));from experiment import current_id,need,DRIVER,sha
p=argparse.ArgumentParser(description=__doc__)
for n in ('build','out','reservation-root'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--policy',choices=('current-board','wrong-board'),required=True);a=p.parse_args();b=a.build.resolve();out=a.out.resolve();i=json.loads((b/'inputs.json').read_text());need(not out.exists() and current_id()==i['new_registry_ID'] and sha(DRIVER)==i['driver_SHA256'],'output or current profile differs')
for n,h in i['frozen'].items():need(sha(b/n)==h,'Frozen input differs: '+n)
out.mkdir();shutil.copytree(b/'assets',out/'assets');(out/'outputs').mkdir()
for name,mode in [('owned-choice.json','owned'),('dependency-choice.json','present-key'),('factory-policy-choice.json',a.policy)]: (out/'assets'/name).write_text(json.dumps({'route' if name=='owned-choice.json' else 'mode':mode})+'\n')
shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755);sys.path.insert(0,str(b/'runtime'));from observer_run_host import run_host
env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_BOARD_'))};m=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),'hardware'],a.reservation_root.resolve(),child_env=env);r=json.loads((out/'execution/execution.stdout').read_text());f=json.loads((out/'outputs/factory-resolver.json').read_text());d=json.loads((out/'outputs/dependency.json').read_text());need(f['status']=='COMPLETE' and d['status']=='COMPLETE' and r['public_decode']['output_frames']==0,'Unexpected result')
x={'status':'PASS','policy':a.policy,'injected':False,'exit_code':m['exit_code'],'create_status':r['public_decode']['decode']['create_status'],'output_frames':r['public_decode']['output_frames'],'dependency_substitutions':d['substitutions'],'policy_substitutions':f['policy_substitutions'],'pool_calls':f['pool_calls'],'GVA_stage_code_pins_valid':f['GVA_stage_code_pins_valid']};(out/'summary.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x))
