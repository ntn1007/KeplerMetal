#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Confirm SDK audit rejects changed numerical and gate evidence, offline."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    audit=Path(__file__).with_name('audit_sdk.py');results=[]
    with tempfile.TemporaryDirectory(prefix='kepler-cas-sdk-mutation-') as tmp:
        root=Path(tmp);shutil.copytree(args.work,root/'work');copy=root/'work'
        def check(label,accepted):
            report=root/(label+'.json')
            result=subprocess.run([sys.executable,str(audit),'--work',str(copy),'--out',str(report)],
                                  capture_output=True,timeout=120)
            if (result.returncode==0)!=accepted:raise ValueError('audit outcome differs: '+label)
            results.append({'case':label,'accepted':result.returncode==0})
        check('unchanged',True)
        output=copy/'repaired-v1-l33-2/outputs/output-0.bin';original=output.read_bytes()
        for label,offset in [('bad-value',64),('bad-guard',0)]:
            changed=bytearray(original);changed[offset]^=1;output.write_bytes(changed)
            check(label,False);output.write_bytes(original)
        path=copy/'negative-metadata/execution.stdout';original=path.read_bytes()
        data=json.loads(original);data['import']['constructor_entered']=True
        path.write_text(json.dumps(data));check('constructor-entered',False);path.write_bytes(original)
        path=copy/'bad-profile.json';original=path.read_bytes()
        data=json.loads(original);data['repair_profile']='different-control'
        path.write_text(json.dumps(data));check('profile-control',False);path.write_bytes(original)
        check('restored',True)
    with out.open('x') as stream:json.dump({'status':'PASS','GPU_dispatches':0,'cases':results},stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'PASS','cases':results}))


if __name__=='__main__':main()
