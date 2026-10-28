#!/usr/bin/env python3
"""Mutate temporary CB0 evidence and confirm audit refusals; no GPU work."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--builds',nargs=2,type=Path,required=True);p.add_argument('--runs',nargs=4,type=Path,required=True)
    for key in ('container','decoder','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    audit=Path(__file__).with_name('audit_cb0_readback.py');results=[]
    with tempfile.TemporaryDirectory(prefix='kepler-cb0-audit-') as tmp:
        root=Path(tmp);builds=[];runs=[]
        for i,path in enumerate(a.builds):
            target=root/('build%d'%i);shutil.copytree(path,target);builds.append(target)
        for i,path in enumerate(a.runs):
            target=root/('run%d'%i);shutil.copytree(path,target);runs.append(target)
        def check(label,accepted,reason=None):
            dest=root/(label+'.json')
            r=subprocess.run([sys.executable,str(audit),'--builds',*[str(x) for x in builds],
                '--runs',*[str(x) for x in runs],'--container',str(a.container),'--decoder',str(a.decoder),
                '--out',str(dest)],capture_output=True,text=True,timeout=120)
            if (r.returncode==0)!=accepted or (reason and reason not in r.stderr):raise ValueError('unexpected audit result: '+label)
            results.append({'case':label,'accepted':r.returncode==0,'expected_reason':reason})
        check('unchanged',True)
        path=runs[1]/'output.bin';original=path.read_bytes()
        for name,offset,reason in [('guard',0,'output guard differs'),('value',64,'CPU oracle mismatch'),('witness',76,'CPU oracle mismatch')]:
            data=bytearray(original);data[offset]^=1;path.write_bytes(data);check(name,False,reason);path.write_bytes(original)
        path=runs[1]/'report.json';original=path.read_bytes();data=json.loads(original)
        data['import']['events'][0]['conditional_auxiliary_section_pinned']=False
        path.write_text(json.dumps(data));check('aux-receipt',False,'constructor receipt differs');path.write_bytes(original)
        path=runs[1]/'manifest.json';original=path.read_bytes();data=json.loads(original)
        data['GPU_reservation']['state']='unresolved';path.write_text(json.dumps(data));check('process',False,'process evidence differs');path.write_bytes(original)
        path=builds[0]/'cb0.sass';original=path.read_bytes();data=bytearray(original);data[0]^=1
        path.write_bytes(data);check('code',False,'build differs');path.write_bytes(original)
        check('restored',True)
    with out.open('x') as f:json.dump({'status':'PASS','GPU_dispatches':0,'cases':results},f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','cases':results}))

if __name__=='__main__':main()
