#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the CPU oracle on copied reference outputs; no GPU execution."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    verify=Path(__file__).with_name('verify.py');records=[]
    with tempfile.TemporaryDirectory(prefix='kepler-divergence-mutation-') as tmp:
        root=Path(tmp);shutil.copytree(a.reference/'outputs',root/'outputs');shutil.copyfile(a.reference/'report.json',root/'report.json')
        target=root/'outputs/l33-p2-v1-r0.bin';original=target.read_bytes()
        def check(label,expected):
            dest=root/(label+'.json')
            r=subprocess.run([sys.executable,str(verify),'--report',str(root/'report.json'),'--outputs',str(root/'outputs'),
                              '--out',str(dest)],capture_output=True,timeout=60)
            if expected is None:
                if r.returncode==0:raise ValueError('truncated output accepted')
                records.append({'case':label,'input_refused':True});return
            if r.returncode:raise ValueError('oracle execution failed: '+label)
            result=json.loads(dest.read_text());nonzero={k:v for k,v in result['totals'].items() if v}
            if nonzero!=expected:raise ValueError('wrong mismatch category: '+label)
            records.append({'case':label,'nonzero_totals':nonzero})
        check('unchanged',{})
        for label,offset,expected in [('active-value',64,{'active_expected':1}),
                                      ('inactive-value',80,{'inactive_expected':1}),
                                      ('witness',76,{'witness':1}),
                                      ('guard',0,{'guard_bytes':1}),
                                      ('success',68,{'success':1,'final':1})]:
            changed=bytearray(original);changed[offset]^=1;target.write_bytes(changed)
            check(label,expected);target.write_bytes(original)
        target.write_bytes(original[:-1]);check('truncated',None);target.write_bytes(original)
        check('restored',{})
    with out.open('x') as stream:json.dump({'status':'PASS','GPU_dispatches':0,'cases':records},stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'PASS','cases':records}))


if __name__=='__main__':main()
