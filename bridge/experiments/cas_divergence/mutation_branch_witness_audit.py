#!/usr/bin/env python3
"""Mutate temporary branch-witness evidence; no GPU execution."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--builds',nargs=2,type=Path,required=True);p.add_argument('--runs',nargs=16,type=Path,required=True)
    for key in ('original-listing','decoder','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    audit=Path(__file__).with_name('audit_branch_witness.py');results=[]
    with tempfile.TemporaryDirectory(prefix='kepler-branch-audit-') as tmp:
        root=Path(tmp);builds=[];runs=[]
        for i,path in enumerate(a.builds):
            target=root/('build%d'%i);shutil.copytree(path,target);builds.append(target)
        for i,path in enumerate(a.runs):
            target=root/('run%d'%i);shutil.copytree(path,target);runs.append(target)
        def check(label,accepted,reason=None):
            r=subprocess.run([sys.executable,str(audit),'--builds',*[str(x) for x in builds],
                 '--runs',*[str(x) for x in runs],'--original-listing',str(a.original_listing),
                 '--decoder',str(a.decoder),'--out',str(root/(label+'.json'))],capture_output=True,text=True,timeout=120)
            if (r.returncode==0)!=accepted or (reason and reason not in r.stderr):raise ValueError('unexpected audit result: '+label)
            results.append({'case':label,'accepted':r.returncode==0,'expected_reason':reason})
        check('unchanged',True)
        path=runs[3]/'output.bin';original=path.read_bytes()
        for name,offset,reason in [('guard',0,'trace guard differs'),('marker',68,'unexpected marker'),('data',64,'trace changed non-witness output')]:
            data=bytearray(original);data[offset]^=1;path.write_bytes(data);check(name,False,reason);path.write_bytes(original)
        path=runs[3]/'report.json';original=path.read_bytes();data=json.loads(original)
        data['import']['events'][0]['conditional_auxiliary_section_pinned']=False
        path.write_text(json.dumps(data));check('aux-receipt',False,'constructor evidence differs');path.write_bytes(original)
        path=runs[3]/'manifest.json';original=path.read_bytes();data=json.loads(original)
        data['GPU_reservation']['state']='unresolved';path.write_text(json.dumps(data));check('process',False,'process differs');path.write_bytes(original)
        path=builds[0]/'trace.sass';original=path.read_bytes();data=bytearray(original);data[0]^=1
        path.write_bytes(data);check('code',False,'build differs');path.write_bytes(original)
        check('restored',True)
    with out.open('x') as f:json.dump({'status':'PASS','GPU_dispatches':0,'cases':results},f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','cases':results}))

if __name__=='__main__':main()
