#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Confirm the offline auditor rejects corrupted results, guards and receipts."""
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
    args=parser.parse_args();work=args.work.resolve();out=args.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    audit=Path(__file__).with_name('audit.py');results=[]
    with tempfile.TemporaryDirectory(prefix='kepler-cas-mutations-') as temp:
        root=Path(temp)
        shutil.copytree(work,root/'work')
        copy=root/'work'
        def check(label,expected):
            report=root/(label+'.json')
            r=subprocess.run([sys.executable,str(audit),'--work',str(copy),'--out',str(report)],
                             capture_output=True,text=True,timeout=120)
            if (r.returncode==0)!=expected:raise ValueError(label+': unexpected auditor result')
            results.append({'case':label,'accepted':r.returncode==0})
        check('unchanged',True)
        target=copy/'repaired-v1-l33/outputs/output-0.bin';original=target.read_bytes()
        for label,offset in [('value',64),('guard',0)]:
            changed=bytearray(original);changed[offset]^=1;target.write_bytes(changed)
            check(label,False);target.write_bytes(original)
        receipt=copy/'repaired-v1-l33/manifest.json';original_json=receipt.read_bytes()
        record=json.loads(original_json);record['GPU_reservation']['state']='unresolved'
        receipt.write_text(json.dumps(record));check('unresolved',False);receipt.write_bytes(original_json)
        check('restored',True)
    with out.open('x') as stream:json.dump({'status':'PASS','cases':results,'GPU_dispatches':0},stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'PASS','cases':results}))


if __name__=='__main__':main()
