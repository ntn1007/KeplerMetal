#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check that the retained auditor rejects altered hardware observations."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True); p.add_argument('--runs',type=Path,nargs=12,required=True)
    p.add_argument('--m1-audit',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir(): raise ValueError('fresh output required')
    candidates=[i for i,x in enumerate(a.runs) if json.loads((x/'manifest.json').read_text())['mode']=='hardware-observed']
    if len(candidates)!=2: raise ValueError('hardware cohort differs')
    index=candidates[0]; original=a.runs[index]
    names=('client','observer.dylib','stderr.log','manifest.json','stdout.json')
    before={name:sha(original/name) for name in names}
    a.out.mkdir(); checks=[]
    for case in ('shared-link','device-type','config-called','create-status','caller-image','caller-offset','enum-unexpected'):
        d=a.out/case; d.mkdir()
        for n in ('client','observer.dylib','stderr.log'): (d/n).symlink_to((original/n).resolve())
        for n in ('manifest.json','stdout.json'): shutil.copyfile(original/n,d/n)
        data=json.loads((d/'stdout.json').read_text())
        if case=='shared-link':
            data['observation']['shared_stored_device_matches']=0; expected='device/shared object observation differs'
        elif case=='device-type':
            data['observation']['matching_type']=0; expected='device/shared object observation differs'
        elif case=='config-called':
            data['observation']['config_calls']=1; expected='object observer safety differs'
        elif case=='caller-image':
            data['observation']['device_caller']['image']='unexpected.dylib'; expected='caller not resolved'
        elif case=='caller-offset':
            data['observation']['shared_caller']['image_offset']+=1; expected='caller profile differs'
        elif case=='enum-unexpected':
            data['observation']['all_calls']=1; expected='enumeration interception differs'
        else:
            data['create_status']=-12913; expected='hardware result differs'
        (d/'stdout.json').write_text(json.dumps(data,sort_keys=True)+'\n')
        manifest=json.loads((d/'manifest.json').read_text()); manifest['stdout_sha256']=sha(d/'stdout.json')
        (d/'manifest.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')
        paths=list(a.runs); paths[index]=d
        cmd=['python3',str(HERE/'audit.py'),'--build',str(a.build),'--runs',*(str(x) for x in paths),
             '--m1-audit',str(a.m1_audit),'--out',str(d/'should-not-exist.json')]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        (d/'stderr.log').unlink(); (d/'audit.stderr').write_text(result.stderr)
        if result.returncode==0 or expected not in result.stderr or (d/'should-not-exist.json').exists():
            raise ValueError(case+' mutation not rejected for its intended reason')
        checks.append({'case':case,'rejected':True,'reason':expected})
    if {name:sha(original/name) for name in names}!=before: raise ValueError('original inputs changed')
    record={'status':'PASS_MUTATIONS_REJECTED','checks':checks,'source_sha256':sha(Path(__file__)),
            'auditor_sha256':sha(HERE/'audit.py'),'originals_modified':False,'gpu_execution':False}
    (a.out/'validation.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':record['status'],'checks':len(checks)}))
if __name__=='__main__': main()
