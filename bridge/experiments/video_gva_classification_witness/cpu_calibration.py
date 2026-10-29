#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate classification hardware breakpoints on a controlled CPU fixture."""
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('cpu_dynamic_host.cpp','cpu_invoke.S','cpu_dylib.cpp','marker.S','lldb_witness.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
    if not v:raise ValueError(m)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required');out.mkdir()
    for n in NAMES:shutil.copyfile(HERE/n,out/n)
    ent=out/'entitlements.plist';ent.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow':True}))
    def run(label,args,env=None):
        r=subprocess.run(list(map(str,args)),capture_output=True,text=True,env=env,timeout=90)
        (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
        need(r.returncode==0,label+' failed');return r.stdout
    common=['xcrun','clang++','-arch','x86_64','-O0','-g','-Wall','-Wextra','-Werror']
    run('build-host',common+[out/'cpu_dynamic_host.cpp',out/'cpu_invoke.S','-o',out/'host'])
    run('build-library',common+['-dynamiclib',out/'cpu_dylib.cpp',out/'marker.S','-o',out/'marker.dylib'])
    run('sign-host',['codesign','--force','--sign','-','--entitlements',ent,out/'host'])
    run('sign-library',['codesign','--force','--sign','-',out/'marker.dylib'])
    for n in ('host','marker.dylib'):run('verify-'+n,['codesign','--verify','--strict',out/n])
    env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KP_'))};env['KP_HW_WITNESS_MODE']='cpu'
    cmd=['xcrun','lldb','--no-lldbinit','--batch','-o','command script import '+json.dumps(str(out/'lldb_witness.py')),
         '-o','breakpoint set -H -K false -n KPGVAReady','-o','breakpoint command add -F lldb_witness.arm 1',
         '-o','run','-o','breakpoint list','-o','quit','--',out/'host',out/'marker.dylib']
    logs={name:run(name,cmd+([name] if name!='excluded' else []),env) for name in ('excluded','accept','wrong')}
    for name,log in logs.items():need('cpu_value=22' in log and 'exited with status = 0' in log and 'KP_HW_HIT_FAIL' not in log,name+' target outcome')
    excluded=logs['excluded'];accept=logs['accept'];wrong=logs['wrong']
    need(excluded.count('KP_HW_ARM_PASS mode=cpu')==1 and re.search(r'KP_CLASS_HIT name=classify bytes_match=1 .*kind_valid=1 kind=17039368 flags_valid=1 flags=1,0,0,1',excluded) and re.search(r'KP_CLASS_HIT name=skip bytes_match=1 .*same_prior=1',excluded) and re.search(r'KP_CLASS_HIT name=after_enumeration bytes_match=1 .*field_valid=1 field=7',excluded),'excluded control')
    need(accept.count('KP_HW_ARM_PASS mode=cpu')==1 and re.search(r'KP_CLASS_HIT name=classify bytes_match=1 .*kind_valid=1 kind=17301505',accept) and 'KP_CLASS_HIT name=skip' not in accept,'accepted control')
    need(wrong.count('KP_HW_ARM_FAIL cpu_base')==1 and 'KP_CLASS_HIT name=' not in wrong,'wrong base control')
    receipt={'status':'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION','excluded_skip_same_node':True,'accepted_skip_absent':True,'bad_base_refused':True,'output_field':7,'GPU_execution':False,'vendor_execution':False,'system_modified':False,
       'source_sha256':{n:sha(out/n) for n in NAMES},'host_sha256':sha(out/'host'),'library_sha256':sha(out/'marker.dylib'),
       'logs':{n:sha(out/(n+'.stdout')) for n in logs}}
    (out/'calibration.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
