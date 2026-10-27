#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit retained shared-client refusals without replaying a driver call."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from verify_video_shared_current import verify


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(paths):
    paths = [Path(p).resolve() for p in paths]
    if len(paths) != 4 or len(set(paths)) != 4:
        raise ValueError('Four distinct paths required')
    modes = ['inventory', 'wrong-target', 'shared', 'shared']
    rows = []
    for path, mode in zip(paths, modes):
        proof = verify(path, allow_refusal=True)
        i = read(path/'inputs.json'); m = read(path/'execution/manifest.json'); r = read(path/'results.json')
        if proof['mode'] != mode:
            raise ValueError('Unexpected mode or order')
        if mode == 'shared':
            if proof['status'] != 'OBSERVED_REFUSAL' or r['open_status'] & 0xffffffff != 0xe00002c7:
                raise ValueError('Unexpected shared-client outcome')
            old = read(path/'verification-execution.json')
            if old != {'exit_code':1, 'isolated_interpreter':True} or 'AssertionError' not in (path/'verification.stderr').read_text():
                raise ValueError('Original strict oracle failure must be retained')
        elif proof['status'] != 'PASS':
            raise ValueError('Control did not pass')
        signature = subprocess.run(['codesign','--verify','--strict',str(path/'execution/application')],capture_output=True,text=True,timeout=15)
        imports = subprocess.run(['nm','-u',str(path/'execution/application')],capture_output=True,text=True,timeout=15)
        if signature.returncode or imports.returncode or '_IOServiceOpen' not in imports.stdout or '_IOServiceClose' not in imports.stdout or '_IOConnect' in imports.stdout:
            raise ValueError('Signature or imported call surface differs')
        rows.append({'mode':mode, 'pid':m['pid'], 'start':m['started_at'], 'end':m['completed_at'],
                     'signed_SHA256':m['signed_binary_sha256'], 'build_inputs_SHA256':i['build_inputs_SHA256'],
                     'registry_id':proof['gpu_registry_id'], 'host_manifest_SHA256':sha(path/'execution/manifest.json'),
                     'results_SHA256':sha(path/'results.json'), 'strict_verifier_SHA256':i['frozen']['src/verify_video_shared_current.py'],
                     'strict_verifier_exit':read(path/'verification-execution.json')['exit_code'],
                     'outcome':proof['status'], 'open_status_hex':hex(r['open_status'] & 0xffffffff) if mode == 'shared' else None})
    for key in ('signed_SHA256','build_inputs_SHA256','registry_id','strict_verifier_SHA256'):
        if len({r[key] for r in rows}) != 1:
            raise ValueError('Cohort identity mismatch: ' + key)
    if len({r['pid'] for r in rows}) != 4 or not all(a['end'] < b['start'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Process lifetimes overlap or PID reused')
    return {'audit_status':'PASS', 'capability_status':'REFUSED', 'refusal_code':'0xe00002c7',
            'interpretation':'kIOReturnUnsupported; source of refusal not observed', 'hosts':rows,
            'open_attempts':2, 'connections_returned':0, 'close_attempts':0, 'external_IOConnect_calls':0,
            'explicit_GPU_commands':0, 'hardware_video_execution_proved':False,
            'driver_internal_effects_traced':False, 'privileged_or_system_changes':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('inventory','wrong','first','repeat','out'):
        p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():
        raise ValueError('Fresh output file required')
    result=audit([a.inventory,a.wrong,a.first,a.repeat])
    with a.out.open('x') as f:
        json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('audit_status','capability_status','refusal_code','open_attempts','hardware_video_execution_proved')}))

if __name__=='__main__':
    main()
