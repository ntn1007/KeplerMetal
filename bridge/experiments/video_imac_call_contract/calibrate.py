#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate the frozen IOKit observer on null-port CPU controls only."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from experiment import SOURCE

HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok: raise ValueError(why)
def run(label,args,out,env=None):
    p=subprocess.run(list(map(str,args)),capture_output=True,env=env,timeout=60)
    (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode==0,label+' failed; inspect retained stderr'); return p.stdout
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    b=json.loads((a.build/'build.json').read_text())
    need(b['status']=='PREPARED' and b['source_sha256']=={n:sha(v) for n,v in SOURCE.items()} and
         b['build_sha256']['observer.dylib']==sha(a.build/'observer.dylib'),'frozen observer differs')
    a.out.mkdir(); shutil.copyfile(a.build/'observer.dylib',a.out/'observer.dylib')
    shutil.copyfile(SOURCE['observer.h'],a.out/'observer.h'); shutil.copyfile(HERE/'calibration.c',a.out/'calibration.c')
    run('build',['xcrun','clang','-arch','x86_64','-std=c11','-Wall','-Wextra','-Werror','-O1',
        a.out/'calibration.c','-I',a.out,'-framework','IOKit','-o',a.out/'calibration'],a.out)
    run('sign',['codesign','--force','--sign','-',a.out/'calibration'],a.out)
    for name in ('calibration','observer.dylib'): run('verify-'+name,['codesign','--verify','--strict',a.out/name],a.out)
    env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))}
    env['DYLD_INSERT_LIBRARIES']=str((a.out/'observer.dylib').resolve())
    raw=json.loads(run('test',[a.out/'calibration'],a.out,env)); need(raw['status']=='PASS' and raw['cases']==3 and raw['null_port_only'],'calibration differs')
    need(sha(a.out/'observer.dylib')==b['build_sha256']['observer.dylib'],'observer changed')
    record={'status':'PASS_NULL_PORT_CALIBRATION','cases':3,'null_port_only':True,
        'returned_statuses':raw['returned_statuses'],'build_sha256':sha(a.build/'build.json'),
        'observer_sha256':sha(a.out/'observer.dylib'),'host_sha256':sha(a.out/'calibration'),
        'calibration_source_sha256':sha(HERE/'calibration.c'),'runner_sha256':sha(Path(__file__)),
        'gpu_connection_opened':False,'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':record['status'],'cases':record['cases']}))
if __name__=='__main__':main()
