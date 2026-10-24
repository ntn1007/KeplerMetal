#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute public render argument roots, native PSOs and raster reception."""
from pathlib import Path
import argparse
import hashlib
import struct
from public_large_scratch import read,sha,write
from verify_render_record_arguments import verify,MODES


def audit(root,build,reference):
    root,build,reference=(Path(p).resolve()for p in(root,build,reference));m=read(build/'inputs.json')
    rows=[];intervals=[];proofs={}
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_render_record_arguments import verify;print(json.dumps(verify(sys.argv[2])))'
    for repeat in range(3):
        for mode in MODES:
            path=root/'cohort'/str(repeat)/mode;proof=verify(path);receipt=read(path/'execution/manifest.json');inputs=read(path/'inputs.json')
            assert inputs==dict(m,mode=mode,driver_SHA256=inputs['driver_SHA256'],source_build_inputs_SHA256=sha(build/'inputs.json'))
            assert read(path/'independent-verification.json')==dict(proof,PID=receipt['pid'],static_library_SHA256=m['static_library_SHA256'])
            v=read(path/'verification-execution.json');assert v['exit_code']==0 and v['isolated_interpreter']is True
            assert v['argv'][1:]==['-I','-c',code,str(path/'oracles'),str(path)]and v['code_SHA256']==hashlib.sha256(code.encode()).hexdigest()
            assert read(path/'verification.stdout')==proof and not(path/'verification.stderr').read_text()
            rows.append(dict(repeat=repeat,PID=receipt['pid'],**{k:v for k,v in proof.items()if k not in ['files_SHA256','root_getters']}));proofs[repeat,mode]=proof
            intervals.append((receipt['started_at'],receipt['completed_at']))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    positive=[m for m in MODES if not m.startswith('arguments_no_reset')]
    image_pairs=old_pairs=repeat_images=repeat_files=changes=0;changed_trials=[]
    for repeat in range(3):
        for mode in positive:
            if mode=='arguments_gpu':continue
            for trial in range(8):
                name=f'trial-{trial}.image.bin';assert proofs[repeat,'arguments_gpu']['files_SHA256'][name]==proofs[repeat,mode]['files_SHA256'][name];image_pairs+=1
        for trial in range(8):
            name=f'trial-{trial}.image.bin';assert proofs[repeat,'arguments_no_reset']['files_SHA256'][name]==proofs[repeat,'arguments_no_reset_native']['files_SHA256'][name];image_pairs+=1
        different=[]
        for trial in range(8):
            name=f'trial-{trial}.image.bin';a=(root/'cohort'/str(repeat)/'arguments_gpu/outputs'/name).read_bytes()[256:-256];b=(root/'cohort'/str(repeat)/'arguments_no_reset/outputs'/name).read_bytes()[256:-256]
            count=sum(x!=y for x,y in zip(struct.unpack('<12288f',a),struct.unpack('<12288f',b)))
            if count:different.append(trial);changes+=count
        assert different==[0,1,3,4,6];changed_trials.append(different)
        for mode in MODES:
            old_mode='air_no_reset'if mode.startswith('arguments_no_reset')else'air_gpu'
            for trial in range(8):
                name=f'trial-{trial}.image.bin';assert proofs[repeat,mode]['files_SHA256'][name]==sha(reference/old_mode/'outputs'/name);old_pairs+=1
            if repeat:
                for name,h in proofs[repeat,mode]['files_SHA256'].items():
                    if name.endswith(('.reset-root.bin','.reset-context.bin','.reset-spare-root.bin')):continue
                    assert h==proofs[0,mode]['files_SHA256'][name],(mode,name);repeat_files+=1
                    if name.endswith('.image.bin'):repeat_images+=1
    return dict(status='PASS_RENDER_RECORD_ARGUMENTS',signed_terminal_nonoverlapping_processes=len(rows),
        rendered_frames=len(rows)*8,checked_float_channels=sum(r['checked_float_channels']for r in rows),maximum_error=max(r['maximum_error']for r in rows),
        raster_materializer_guard_bytes=sum(r['guard_bytes']for r in rows),root_guard_bytes=sum(r['reset_guard_bytes']for r in rows),
        reset_dispatches=sum(r['reset_dispatches']for r in rows),reset_witness_words=sum(r['reset_witness_words']for r in rows),
        ordinary_native_programs_checked=sum(r['ordinary_native_programs_checked']for r in rows),API_refusals=sum(r['API_refusals']for r in rows),
        reference_control_image_pairs=image_pairs,previous_manual_root_image_pairs=old_pairs,repeat_image_pairs=repeat_images,repeat_readback_file_pairs=repeat_files,
        changed_float_channels_against_no_reset=changes,changed_trials=changed_trials,
        client_GPU_address_construction=False,scope_and_ICBs_released_before_commit=True,argument_encoders_released_before_commit=True,
        root_contexts_alive_before_commit=True,native_function_getters_restored=True,native_Apple_ICB_ABI=False,
        performance_benchmark=False,full_objective_complete=False,runtime_SHA256=m['static_library_SHA256'],cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['build','reference','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();d=audit(a.root,a.build,a.reference);write(a.out,d);print({k:v for k,v in d.items()if k not in ['cases','changed_trials']})
