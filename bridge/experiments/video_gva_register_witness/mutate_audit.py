#!/usr/bin/env python3
"""Exercise audit failure controls on temporary copies; no GPU execution."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
def need(ok,why):
    if not ok:raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('base','build','calibration','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=9,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');results=[]
    with tempfile.TemporaryDirectory(prefix='gva-audit-mutation-',dir=a.out.parent) as name:
        tmp=Path(name);runs=[]
        for i,source in enumerate(a.runs):
            target=tmp/('host-%d'%i);shutil.copytree(source,target);runs.append(target)
        def check(label,expected):
            output=tmp/(label+'.json');command=[sys.executable,str(HERE/'audit.py'),'--base',str(a.base),'--build',str(a.build),
                '--calibration',str(a.calibration),'--runs',*(str(x) for x in runs),'--out',str(output)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=120)
            if expected is None:need(result.returncode==0 and json.loads(output.read_text())['status']=='PASS_BOUNDED_REGISTER_OBSERVATION',label+' baseline failed')
            else:need(result.returncode!=0 and expected in result.stderr,label+' mutation not detected')
            results.append({'case':label,'expected':expected or 'PASS','result':'PASS'})
        check('untouched',None)
        def edit(label,path,fn,expected):
            original=path.read_bytes()
            try:path.write_bytes(fn(original));check(label,expected)
            finally:path.write_bytes(original)
        edit('selector',runs[2]/'stderr.log',lambda b:b.replace(b'selector=2 allocation_size=1536',b'selector=9 allocation_size=1536'), 'actual selector witness differs')
        edit('profile',runs[2]/'stderr.log',lambda b:b.replace(b'KM_GVA_REGISTER profile=1',b'KM_GVA_REGISTER profile=0'), 'actual selector witness differs')
        edit('software-pixel',runs[0]/'outputs/vt-frame-000.nv12',lambda b:bytes([b[0]^1])+b[1:], 'software image differs')
        edit('reference-asset',runs[0]/'assets/fixtures/H264/cpu-frame-000.nv12',lambda b:bytes([b[0]^1])+b[1:], 'run asset differs')
        def kill_flag(raw):
            value=json.loads(raw);value['SIGKILL_requested']=True;return (json.dumps(value)+'\n').encode()
        edit('kill-request',runs[2]/'manifest.json',kill_flag,'process provenance differs')
        check('restored',None)
    report={'status':'PASS','controls':results,'GPU_execution':False,'original_files_modified':False}
    with a.out.open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
