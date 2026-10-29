#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate the register observer on three bounded CPU-only cases."""
import argparse,hashlib,json,os,plistlib,re,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
NAMES=('cpu.cpp','cpu.S','lldb_witness.py','lldb_guard.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(argv,env=None):
    p=subprocess.run([str(x) for x in argv],capture_output=True,text=True,env=env,timeout=90)
    if p.returncode:raise ValueError('command failed: '+p.stderr[-1000:])
    return p.stdout
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    out.mkdir()
    for n in NAMES:shutil.copyfile(HERE/n,out/n)
    ent=out/'entitlements.plist';ent.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow':True}))
    host=out/'host';run(['xcrun','clang++','-arch','x86_64','-O0','-g','-Wall','-Wextra','-Werror',out/'cpu.cpp',out/'cpu.S','-o',host]);run(['codesign','--force','--sign','-','--entitlements',ent,host]);run(['codesign','--verify','--strict',host])
    env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};env['KM_TRACE_MODE']='cpu'
    cmd=['xcrun','lldb','--no-lldbinit','--batch','-o','command script import '+json.dumps(str(out/'lldb_witness.py')),
         '-o','command script import '+json.dumps(str(out/'lldb_guard.py')),
         '-o','breakpoint set -H -K false -n KMTraceReady','-o','breakpoint command add -F lldb_witness.arm 1',
         '-o','run','-o','script lldb_guard.await_terminal(lldb.debugger)','-o','quit','--',host]
    logs={}
    for name,args in [('one',['1']),('zero',['0']),('wrong',['1','wrong'])]:
        log=run(cmd+args,env);(out/(name+'.log')).write_text(log);logs[name]=log
        if 'KP_PROCESS_EXITED' not in log or 'KM_TRACE_HIT_FAIL' in log:raise ValueError('terminal or hit differs')
    for name,count in [('one',1),('zero',0)]:
        log=logs[name]
        lists=re.findall(r'^KM_TRACE_LIST thread=(\d+) nonnull=1 bytes_match=1$',log,re.M)
        batches=re.findall(r'^KM_TRACE_BATCH thread=(\d+) count='+str(count)+r' same_list=1 bytes_match=1$',log,re.M)
        if log.count('KM_TRACE_ARM_PASS mode=cpu')!=1 or len(lists)!=1 or batches!=lists or 'KM_TRACE_ARM_FAIL' in log:raise ValueError(name+' differs')
    if logs['wrong'].count('KM_TRACE_ARM_FAIL marker')!=1 or 'KM_TRACE_LIST' in logs['wrong'] or 'KM_TRACE_BATCH' in logs['wrong']:raise ValueError('wrong marker differs')
    record={'status':'PASS_CPU_ENUMERATION_WITNESS','cpu_only':True,'one_and_zero_verified':True,'wrong_marker_refused':True,
            'sources':{n:sha(out/n) for n in NAMES},'host_sha256':sha(host),'logs':{n:sha(out/(n+'.log')) for n in logs}}
    (out/'calibration.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
