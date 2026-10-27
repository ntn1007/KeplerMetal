#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a serialized type-3/type-6 connection cohort without replaying it."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from verify_video_context_association import verify
from video_context_association import PINS,LOADED,KERNEL_UUID

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(paths):
    paths=[Path(p).resolve() for p in paths]
    if len(paths)!=6 or len(set(paths))!=6:raise ValueError('Six distinct paths required')
    modes=['inventory','wrong-target','pair','attach','pair','attach'];rows=[]
    for path,mode in zip(paths,modes):
        proof=verify(path);i=read(path/'inputs.json');m=read(path/'execution/manifest.json');r=read(path/'results.json')
        if proof['mode']!=mode:raise ValueError('Unexpected mode or order')
        if i['profile']!={'system_files_SHA256':PINS,'kernel_UUID':KERNEL_UUID,'loaded_kext_UUID':LOADED,'loaded_code_bytes_compared':False}:
            raise ValueError('Pinned profile differs')
        if sha(path/'src/verify_video_context_association.py')!=sha(Path(__file__).with_name('verify_video_context_association.py')):
            raise ValueError('Frozen oracle differs')
        if read(path/'verification-execution.json')!={'exit_code':0,'isolated_interpreter':True} or read(path/'verification.stdout')!=proof:
            raise ValueError('Original verification differs')
        if mode=='pair' and proof['outcome']!='PAIR_OPEN_CLOSED':raise ValueError('Pair control differs')
        if mode=='attach' and (proof['outcome'],proof['association_status_hex'])!=('ASSOCIATION_ACCEPTED','0x0'):
            raise ValueError('Association observation differs')
        signed=path/'execution/application';sign=subprocess.run(['codesign','--verify','--strict',str(signed)],capture_output=True,text=True,timeout=15)
        nm=subprocess.run(['nm','-u',str(signed)],capture_output=True,text=True,timeout=15)
        if sign.returncode or nm.returncode or any(x not in nm.stdout for x in ('_IOServiceOpen','_IOServiceClose','_MTLCopyAllDevices','_IOConnectAddClient')) or '_IOConnectCall' in nm.stdout:
            raise ValueError('Signature or imports differ')
        rows.append({'mode':mode,'pid':m['pid'],'start':m['started_at'],'end':m['completed_at'],
          'signed_SHA256':m['signed_binary_sha256'],'build_inputs_SHA256':i['build_inputs_SHA256'],
          'registry_id':proof['gpu_registry_id'],'pci_registry_id':proof['pci_registry_ID'],
          'metal_registry_id':proof['metal_registry_ID'],'outcome':proof['outcome'],
          'association_status_hex':proof['association_status_hex'],
          'host_manifest_SHA256':sha(path/'execution/manifest.json'),'results_SHA256':sha(path/'results.json'),
          'verification_SHA256':sha(path/'verification.stdout')})
    for key in ('signed_SHA256','build_inputs_SHA256','registry_id','pci_registry_id'):
        if len({r[key] for r in rows})!=1:raise ValueError('Cohort identity differs: '+key)
    if len({r['pid'] for r in rows})!=6 or not all(x['end']<y['start'] for x,y in zip(rows,rows[1:])):
        raise ValueError('Process lifetimes overlap or PID reused')
    return {'audit_status':'PASS','unassociated_pairs_open_closed':2,'association_accepted_and_closed':2,
            'same_executable':True,'serialized':True,'same_gpu_pci_ancestor':True,
            'close_order':'context then shared','explicit_selector_calls':0,'explicit_GPU_commands':0,
            'driver_internal_activity_traced':False,'hardware_video_execution_proved':False,'hosts':rows}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():raise ValueError('Fresh output file required')
    r=audit(a.run)
    with a.out.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps({k:r[k] for k in ('audit_status','unassociated_pairs_open_closed','association_accepted_and_closed','hardware_video_execution_proved')}))

if __name__=='__main__':main()
