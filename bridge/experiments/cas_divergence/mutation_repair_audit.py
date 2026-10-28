#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the repair auditor with corrupted copies; no GPU execution."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','decoder','reference','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=7,required=True)
    a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    audit=Path(__file__).with_name('audit_repair.py');results=[]
    with tempfile.TemporaryDirectory(prefix='kepler-divergence-repair-mutation-') as tmp:
        root=Path(tmp);shutil.copytree(a.build,root/'build');runs=[]
        for index,path in enumerate(a.runs):
            target=root/('run-%d'%index);shutil.copytree(path,target);runs.append(target)
        def check(label,accepted):
            dest=root/(label+'.json')
            cmd=[sys.executable,str(audit),'--build',str(root/'build'),'--decoder',str(a.decoder),
                 '--reference',str(a.reference),'--runs',*[str(x) for x in runs],'--out',str(dest)]
            r=subprocess.run(cmd,capture_output=True,timeout=120)
            if (r.returncode==0)!=accepted:raise ValueError('audit result differs: '+label)
            results.append({'case':label,'accepted':r.returncode==0})
        check('unchanged',True)
        target=runs[5]/'outputs/l33-p2-v1-r0.bin';original=target.read_bytes()
        for label,offset in [('wrong-result',64),('guard',0)]:
            mutated=bytearray(original);mutated[offset]^=1;target.write_bytes(mutated)
            check(label,False);target.write_bytes(original)
        target=runs[5]/'report.json';original=target.read_bytes();data=json.loads(original)
        data['import']['events'][0]['expected_original_code_identical']=False
        target.write_text(json.dumps(data));check('native-input-evidence',False);target.write_bytes(original)
        target=runs[5]/'manifest.json';original=target.read_bytes();data=json.loads(original)
        data['GPU_reservation']['state']='unresolved';target.write_text(json.dumps(data))
        check('unresolved-process',False);target.write_bytes(original)
        target=root/'build/repaired.sass';original=target.read_bytes();mutated=bytearray(original);mutated[0x550]^=1
        target.write_bytes(mutated);check('changed-repair',False);target.write_bytes(original)
        check('restored',True)
    with out.open('x') as stream:json.dump({'status':'PASS','GPU_dispatches':0,'cases':results},stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'PASS','cases':results}))


if __name__=='__main__':main()
