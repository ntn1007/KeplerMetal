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
    for name,args in [('one',['1']),('zero',['0']),('wrong',['1','wrong']),('wrongid',['1','wrongid']),('null',['1','null'])]:
        log=run(cmd+args,env);(out/(name+'.log')).write_text(log);logs[name]=log
        if 'KP_PROCESS_EXITED' not in log or 'KM_TRACE_HIT_FAIL' in log:raise ValueError('terminal or hit differs')
    for name,count,match in [('one',1,1),('zero',0,1),('wrongid',1,0),('null',1,1)]:
        log=logs[name]
        devices=re.findall(r'^KM_TRACE_DEVICE thread=(\d+) target_match='+str(match)+r' bytes_match=1$',log,re.M)
        lists=re.findall(r'^KM_TRACE_LIST thread=(\d+) nonnull=1 bytes_match=1$',log,re.M)
        items=str(match) if count else '-1'
        batches=re.findall(r'^KM_TRACE_BATCH thread=(\d+) count='+str(count)+r' same_list=1 item_match='+items+r' bytes_match=1$',log,re.M)
        input_hits=re.findall(r'^KM_TRACE_FILTER_INPUT thread=(\d+) device_match='+str(match)+r' bytes_match=1$',log,re.M)
        alloc_hits=re.findall(r'^KM_TRACE_DICT_ALLOC thread=(\d+) nonnull='+str(0 if name=='null' else 1)+r' bytes_match=1$',log,re.M)
        output_hits=re.findall(r'^KM_TRACE_FILTER_OUTPUT thread=(\d+) input_match='+str(match)+r' nonnull='+str(0 if name=='null' else 1)+r' same_alloc=1 bytes_match=1$',log,re.M)
        if count and (input_hits!=lists or alloc_hits!=lists or output_hits!=lists):raise ValueError(name+' filter differs')
        if not count and (input_hits or alloc_hits or output_hits):raise ValueError(name+' unexpected filter')
        if log.count('KM_TRACE_ARM_PASS mode=cpu')!=1 or len(devices)!=1 or devices!=lists or batches!=lists or 'KM_TRACE_ARM_FAIL' in log:raise ValueError(name+' differs')
    if logs['wrong'].count('KM_TRACE_ARM_FAIL marker')!=1 or 'KM_TRACE_DEVICE' in logs['wrong'] or 'KM_TRACE_LIST' in logs['wrong']:raise ValueError('wrong marker differs')
    record={'status':'PASS_CPU_ENUMERATION_WITNESS','cpu_only':True,'one_and_zero_verified':True,'wrong_marker_refused':True,'wrong_target_rejected':True,'null_result_verified':True,'allocation_identity_verified':True,
            'sources':{n:sha(out/n) for n in NAMES},'host_sha256':sha(host),'logs':{n:sha(out/(n+'.log')) for n in logs}}
    (out/'calibration.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
