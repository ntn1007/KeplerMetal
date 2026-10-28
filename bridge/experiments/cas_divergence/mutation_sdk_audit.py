#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the conditional SDK auditor against mutated offline evidence."""
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
    p.add_argument('--runs',nargs=8,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    audit=Path(__file__).with_name('audit_sdk.py');records=[]
    with tempfile.TemporaryDirectory(prefix='kepler-conditional-sdk-mutation-') as tmp:
        root=Path(tmp);shutil.copytree(a.build,root/'build');runs=[]
        for index,path in enumerate(a.runs):
            target=root/('run-%d'%index);shutil.copytree(path,target);runs.append(target)
        def check(label,accepted):
            dest=root/(label+'.json')
            r=subprocess.run([sys.executable,str(audit),'--build',str(root/'build'),'--decoder',str(a.decoder),
                              '--reference',str(a.reference),'--runs',*[str(x) for x in runs],
                              '--out',str(dest)],capture_output=True,timeout=120)
            if (r.returncode==0)!=accepted:raise ValueError('audit outcome differs: '+label)
            records.append({'case':label,'accepted':r.returncode==0})
        check('unchanged',True)
        target=runs[6]/'outputs/l33-p2-v1-r0.bin';original=target.read_bytes()
        for label,offset in [('wrong-result',64),('guard',0)]:
            changed=bytearray(original);changed[offset]^=1;target.write_bytes(changed)
            check(label,False);target.write_bytes(original)
        target=runs[6]/'report.json';original=target.read_bytes();data=json.loads(original)
        data['import']['native_import']['events'][0]['native_metadata_identical_to_certificate']=False
        target.write_text(json.dumps(data));check('metadata-evidence',False);target.write_bytes(original)
        target=runs[4]/'report.json';original=target.read_bytes();data=json.loads(original)
        data['import']['constructor_entered']=True;target.write_text(json.dumps(data))
        check('negative-constructor-entered',False);target.write_bytes(original)
        target=runs[6]/'manifest.json';original=target.read_bytes();data=json.loads(original)
        data['GPU_reservation']['state']='unresolved';target.write_text(json.dumps(data))
        check('unresolved-process',False);target.write_bytes(original)
        check('restored',True)
    with out.open('x') as stream:json.dump({'status':'PASS','GPU_dispatches':0,'cases':records},stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'PASS','cases':records}))


if __name__=='__main__':main()
