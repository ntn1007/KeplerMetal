#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a serialized, same-build video-context cohort without native execution."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from verify_video_context_current import verify

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(paths):
    if len(paths)!=4 or len(set(map(str,paths)))!=4:raise ValueError('Four distinct cohort paths required')
    modes=['inventory','wrong-target','video','video'];rows=[]
    for path,mode in zip(paths,modes):
        path=Path(path).resolve();proof=verify(path);i=read(path/'inputs.json');m=read(path/'execution/manifest.json')
        if proof['mode']!=mode:raise ValueError('Unexpected mode or order')
        if sha(path/'src/verify_video_context_current.py')!=sha(Path(__file__).with_name('verify_video_context_current.py')):
            raise ValueError('Auditor and frozen oracle differ')
        checked=subprocess.run(['codesign','--verify','--strict',str(path/'execution/application')],capture_output=True,text=True,timeout=15)
        symbols=subprocess.run(['nm','-u',str(path/'execution/application')],capture_output=True,text=True,timeout=15)
        if checked.returncode or symbols.returncode or '_IOServiceOpen' not in symbols.stdout or '_IOServiceClose' not in symbols.stdout or '_IOConnectCall' in symbols.stdout:
            raise ValueError('Signature or imported call surface differs')
        rows.append({'mode':mode,'pid':m['pid'],'start':m['started_at'],'end':m['completed_at'],
          'signed_SHA256':m['signed_binary_sha256'],'build_inputs_SHA256':i['build_inputs_SHA256'],
          'registry_id':proof['gpu_registry_id'],'host_manifest_SHA256':sha(path/'execution/manifest.json'),
          'results_SHA256':sha(path/'results.json'),'verification_SHA256':sha(path/'verification.stdout'),
          'proof':proof})
    if len({r['pid'] for r in rows})!=4 or len({r['signed_SHA256'] for r in rows})!=1 or len({r['build_inputs_SHA256'] for r in rows})!=1 or len({r['registry_id'] for r in rows})!=1:
        raise ValueError('Cohort identity mismatch')
    if not all(a['end']<b['start'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Cohort host lifetimes overlap')
    return {'status':'PASS','hosts':rows,'same_signed_executable':True,'serialized':True,
      'successful_video_context_opens':2,'successful_video_context_closes':2,
      'external_IOConnect_calls':0,'GPU_commands_submitted':0,'hardware_video_execution_proved':False,
      'driver_internal_effects_traced':False,'current_video_profile_qualified_for_RM':False,
      'limits':['Only type-3 open/close on the pinned profile.',
                'A context opening is not a video decode, command ABI qualification or privilege grant.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--wrong',type=Path,required=True);p.add_argument('--video',type=Path,required=True);p.add_argument('--repeat',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():raise ValueError('Fresh output path required')
    r=audit([a.inventory,a.wrong,a.video,a.repeat]);
    with a.out.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps({k:r[k] for k in ('status','same_signed_executable','serialized','successful_video_context_opens','successful_video_context_closes','hardware_video_execution_proved')}))

if __name__=='__main__':main()
