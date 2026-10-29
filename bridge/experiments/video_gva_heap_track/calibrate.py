#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate debugger-to-watcher address handoff using an original CPU target."""
import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('heap_watch.cpp','foreign_caller.cpp','cpu_control.cpp','cpu_marker.S','lldb_target.py','lldb_calibrate.py')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(label,argv,out,env=None):
    r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=90,env=env)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    if r.returncode:raise ValueError(label+' failed; inspect retained output')
    return r.stdout


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    out.mkdir()
    for n in NAMES:shutil.copyfile(HERE/n,out/n)
    shutil.copyfile(HERE.parent/'video_gva_repeat_sessions/repeat_gate.h',out/'repeat_gate.h')
    lib=out/'heap-watch.dylib';foreign=out/'foreign.dylib';host=out/'cpu-control'
    common=['xcrun','clang++','-arch','x86_64','-O0','-g','-std=c++17','-Wall','-Wextra','-Werror']
    for label,source,dest in [('watch','heap_watch.cpp',lib),('foreign','foreign_caller.cpp',foreign)]:
        run('build-'+label,common+['-dynamiclib',out/source,'-install_name',dest,'-o',dest],out)
        run('sign-'+label,['codesign','--force','--sign','-',dest],out)
    run('build-host',common+[out/'cpu_control.cpp',out/'cpu_marker.S',lib,foreign,'-o',host],out)
    ent=out/'entitlements.plist';ent.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow':True}))
    run('sign-host',['codesign','--force','--sign','-','--entitlements',ent,host],out)
    for name,item in [('watch',lib),('foreign',foreign),('host',host)]:run('verify-'+name,['codesign','--verify','--strict',item],out)
    env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KP_','KM_'))}
    for mode in ('match','different'):
        cmds=['settings set target.env-vars '+json.dumps('DYLD_INSERT_LIBRARIES='+str(lib)),
              'command script import '+json.dumps(str(out/'lldb_target.py')),
              'command script import '+json.dumps(str(out/'lldb_calibrate.py')),
              'breakpoint set -H -K false -n KPTraceHeapTarget',
              'breakpoint command add -F lldb_calibrate.hit 1','run','breakpoint list','quit']
        argv=['xcrun','lldb','--no-lldbinit','--batch']
        for line in cmds:argv.extend(('-o',line))
        log=run(mode,argv+['--',host,mode],out,env)
        want='PASS matched free then unrelated free' if mode=='match' else 'PASS unrelated free then matched free'
        if (log.count('KP_HEAP_TARGET_WRITE success=1')!=1 or want not in log or
            'exited with status = 0' not in log or 'resolved, hardware, hit count = 1' not in log):
            raise ValueError(mode+' calibration differs')
    result={'status':'PASS_LLDB_WATCHED_TARGET_CPU_CALIBRATION','match_and_nonmatch_order_tested':True,
            'two_distinct_targets':True,'hardware_breakpoint_hits':2,'sources_sha256':{n:sha(out/n) for n in (*NAMES,'repeat_gate.h')},
            'qualifier_sha256':sha(Path(__file__)),'observer_sha256':sha(lib),'foreign_sha256':sha(foreign),'host_sha256':sha(host),
            'logs_sha256':{n:sha(out/(n+'.stdout')) for n in ('match','different')},
            'system_modified':False,'GPU_execution':False,'hardware_video_execution_proved':False}
    (out/'calibration.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'modes':2,'GPU_execution':False}))


if __name__=='__main__':main()
