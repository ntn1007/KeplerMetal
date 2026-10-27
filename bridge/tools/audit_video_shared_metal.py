#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a serialized same-process Metal/shared-client comparison offline."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from verify_video_shared_metal import verify
from video_shared_metal import PINS, LOADED, KERNEL_UUID

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(paths):
    paths=[Path(p).resolve() for p in paths]
    if len(paths)!=8 or len(set(paths))!=8:raise ValueError('Eight distinct paths required')
    expected=['inventory','wrong-target','direct','device','queue','queue','direct','device']
    rows=[]
    for path,mode in zip(paths,expected):
        proof=verify(path);i=read(path/'inputs.json');m=read(path/'execution/manifest.json')
        if proof['mode']!=mode:raise ValueError('Cohort order differs')
        profile=i['profile']
        if profile!={'system_files_SHA256':PINS,'kernel_UUID':KERNEL_UUID,'loaded_kext_UUID':LOADED,'loaded_code_bytes_compared':False}:
            raise ValueError('Pinned profile differs')
        raw=read(path/'results.json')
        if mode in ('inventory','wrong-target') and (raw['connection_returned'] or raw['queue_attempted'] or raw['queue_created'] or raw['metal_candidates'] or raw['metal_registry_ID'] or raw['metal_pci_registry_ID']):
            raise ValueError('Control performed an unexpected operation')
        if sha(path/'src/verify_video_shared_metal.py')!=sha(Path(__file__).with_name('verify_video_shared_metal.py')):
            raise ValueError('Cohort oracle differs')
        v=read(path/'verification-execution.json')
        if v!={'exit_code':0,'isolated_interpreter':True} or read(path/'verification.stdout')!=proof:
            raise ValueError('Original verification differs')
        signed=path/'execution/application'
        sign=subprocess.run(['codesign','--verify','--strict',str(signed)],capture_output=True,text=True,timeout=15)
        nm=subprocess.run(['nm','-u',str(signed)],capture_output=True,text=True,timeout=15)
        if sign.returncode or nm.returncode or any(x not in nm.stdout for x in ('_IOServiceOpen','_IOServiceClose','_MTLCopyAllDevices')) or '_IOConnect' in nm.stdout:
            raise ValueError('Signature or imports differ')
        if mode=='direct' and (proof['outcome'],proof['open_status_hex'])!=('OPEN_REFUSED','0xe00002c7'):
            raise ValueError('Direct observation differs')
        if mode in ('device','queue') and (proof['outcome'],proof['open_status_hex'])!=('OPEN_CLOSED','0x0'):
            raise ValueError('Metal observation differs')
        rows.append({'mode':mode,'pid':m['pid'],'start':m['started_at'],'end':m['completed_at'],
           'signed_SHA256':m['signed_binary_sha256'],'build_inputs_SHA256':i['build_inputs_SHA256'],
           'registry_id':proof['gpu_registry_id'],'pci_registry_id':proof['pci_registry_ID'],
           'metal_registry_id':proof['metal_registry_ID'],'outcome':proof['outcome'],
           'open_status_hex':proof['open_status_hex'],'host_manifest_SHA256':sha(path/'execution/manifest.json'),
           'results_SHA256':sha(path/'results.json'),'verification_SHA256':sha(path/'verification.stdout')})
    for key in ('signed_SHA256','build_inputs_SHA256','registry_id','pci_registry_id'):
        if len({r[key] for r in rows})!=1:raise ValueError('Cohort identity differs: '+key)
    if len({r['pid'] for r in rows})!=8 or not all(x['end']<y['start'] for x,y in zip(rows,rows[1:])):
        raise ValueError('Process lifetimes overlap or PID reused')
    return {'audit_status':'PASS','direct_refused':2,'metal_device_open_closed':2,'metal_queue_open_closed':2,
            'same_executable':True,'serialized':True,'same_gpu_pci_ancestor':True,
            'explicit_IOConnect_calls':0,'explicit_GPU_commands':0,'Metal_internal_activity_traced':False,
            'hardware_video_execution_proved':False,'hosts':rows}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():raise ValueError('Fresh output file required')
    result=audit(a.run)
    with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('audit_status','direct_refused','metal_device_open_closed','metal_queue_open_closed','hardware_video_execution_proved')}))

if __name__=='__main__':main()
