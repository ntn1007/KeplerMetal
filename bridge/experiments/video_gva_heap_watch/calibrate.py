#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate public deallocator interposition on an original CPU-only caller."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('heap_watch.cpp','foreign_caller.cpp','cpu_control.cpp')
GATE=HERE.parent/'video_gva_repeat_sessions/repeat_gate.h'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(label,argv,out,env=None):
    r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=60,env=env)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    if r.returncode:raise ValueError(label+' failed; inspect retained output')
    return r.stdout.strip()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    out.mkdir()
    for n in NAMES:shutil.copyfile(HERE/n,out/n)
    shutil.copyfile(GATE,out/'repeat_gate.h')
    lib=out/'heap-watch.dylib';foreign=out/'foreign.dylib';host=out/'cpu-control'
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-Wall','-Wextra','-Werror']
    for label,source,dest in [('watch','heap_watch.cpp',lib),('foreign','foreign_caller.cpp',foreign)]:
        run('build-'+label,common+['-dynamiclib',out/source,'-install_name',dest,'-o',dest],out)
        run('sign-'+label,['codesign','--force','--sign','-',dest],out)
    run('build-host',common+[out/'cpu_control.cpp',lib,foreign,'-o',host],out)
    run('sign-host',['codesign','--force','--sign','-',host],out)
    for name,binary in [('watch',lib),('foreign',foreign),('host',host)]:run('verify-'+name,['codesign','--verify','--strict',binary],out)
    env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KP_','KM_'))}
    env['DYLD_INSERT_LIBRARIES']=str(lib)
    for i in range(2):
        if run('control-'+str(i),[host],out,env)!='PASS cross-image free and zone-free watched-pointer controls':raise ValueError('control differs')
    receipt={'status':'PASS_TWO_CPU_CROSS_IMAGE_CONTROLS','processes':2,'positive_free_and_zone_free_per_process':True,
             'unrelated_pointer_excluded':True,'duplicate_arm_refused':True,'null_arm_refused':True,
             'sources_sha256':{n:sha(out/n) for n in (*NAMES,'repeat_gate.h')},'qualifier_sha256':sha(Path(__file__)),
             'observer_sha256':sha(lib),'foreign_sha256':sha(foreign),'host_sha256':sha(host),
             'logs_sha256':{str(i):sha(out/('control-'+str(i)+'.stdout')) for i in range(2)},
             'applegva_interposition_proved':False,'all_deallocation_paths_covered':False,
             'GPU_execution':False,'vendor_execution':False,'system_modified':False}
    (out/'calibration.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':receipt['status'],'processes':2,'GPU_execution':False}))


if __name__=='__main__':main()
