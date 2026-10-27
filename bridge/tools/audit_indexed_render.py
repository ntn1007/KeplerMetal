#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck indexed raster/record controls, repeats and the unchanged v1 routes."""
from pathlib import Path
import argparse
import json
import struct
import subprocess
import sys
from public_large_scratch import read,sha,write
from verify_indexed_render import verify,MODES


def audit(root,build,previous):
    root,build,previous=(Path(x).resolve()for x in(root,build,previous));inputs=read(build/'inputs.json');rows=[];proofs={};intervals=[]
    for repeat in range(2):
        for mode in MODES:
            p=root/'cohort'/str(repeat)/mode;proof=verify(p);m=read(p/'execution/manifest.json');inp=read(p/'inputs.json')
            assert inp==dict(inputs,mode=mode,driver_SHA256=inp['driver_SHA256'],source_build_inputs_SHA256=sha(build/'inputs.json'))
            assert read(p/'independent-verification.json')==dict(proof,PID=m['pid'],static_library_SHA256=inputs['static_library_SHA256'])
            v=read(p/'verification-execution.json');assert v['exit_code']==0 and v['isolated_interpreter']is True
            assert read(p/'verification.stdout')==proof and not(p/'verification.stderr').read_text()
            proofs[repeat,mode]=proof;intervals.append((m['started_at'],m['completed_at']))
            rows.append(dict(repeat=repeat,PID=m['pid'],**{k:v for k,v in proof.items()if isinstance(v,(str,int,float,bool))}))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    pairs=[('indexed_gpu','indexed_native'),('indexed_gpu','indexed_reference'),('indexed_gpu','indexed_contracts')]
    for prefix in ['no_dispatch','foreign','wrong_kind','last','missing_table','after_reset','then_reset']:pairs.append(('indexed_'+prefix,'indexed_'+prefix+'_native'))
    pairs +=[('indexed_foreign','indexed_'+suffix)for suffix in ['wrong_kind','missing_table','after_reset','then_reset']]
    image_pairs=repeat_images=repeat_files=previous_images=0;changed={}
    for repeat in range(2):
        for a,b in pairs:
            for trial in range(8):
                name=f'trial-{trial}.image.bin';assert proofs[repeat,a]['files_SHA256'][name]==proofs[repeat,b]['files_SHA256'][name];image_pairs+=1
        for trial in range(8):
            name=f'trial-{trial}.image.bin';assert proofs[repeat,'indexed_no_dispatch']['files_SHA256'][name]==sha(previous/'outputs'/name);previous_images+=1
        for mode,want in [('indexed_no_dispatch',[0,1,2,3,4,5]),('indexed_foreign',[0,1,2,6]),('indexed_last',list(range(7)))]:
            counts=[]
            for trial in range(8):
                name=f'trial-{trial}.image.bin';a=(root/'cohort'/str(repeat)/'indexed_gpu/outputs'/name).read_bytes()[256:-256];b=(root/'cohort'/str(repeat)/mode/'outputs'/name).read_bytes()[256:-256]
                counts.append(sum(x!=y for x,y in zip(struct.unpack('<12288f',a),struct.unpack('<12288f',b))))
            assert [i for i,v in enumerate(counts)if v]==want,(mode,counts);changed.setdefault(mode,[]).append(counts)
        if repeat:
            for mode in MODES:
                for name,h in proofs[repeat,mode]['files_SHA256'].items():
                    if name.endswith(('.reset-context.bin','.reset-root.bin')):continue
                    assert h==proofs[0,mode]['files_SHA256'][name],(mode,name);repeat_files+=1
                    if name.endswith('.image.bin'):repeat_images+=1
    return dict(status='PASS_INDEXED_RENDER',signed_terminal_nonoverlapping_hosts=len(rows),rendered_frames=len(rows)*8,
        checked_float_channels=sum(r['checked_float_channels']for r in rows),maximum_error=max(r['maximum_error']for r in rows),
        indexed_dispatches=sum(r['indexed_dispatches']for r in rows),arithmetic_witness_words=sum(r['arithmetic_witness_words']for r in rows),
        ordinary_native_programs_checked=sum(r['ordinary_native_programs_checked']for r in rows),
        owned_binding_rows_checked=sum(r['owned_binding_rows_checked']for r in rows),API_refusals=sum(r['API_refusals']for r in rows),
        raster_materializer_guard_bytes=sum(r['guard_bytes']for r in rows),root_guard_bytes=sum(r['root_guard_bytes']for r in rows),
        reference_control_image_pairs=image_pairs,repeat_image_pairs=repeat_images,repeat_readback_file_pairs=repeat_files,
        preceding_v1_image_pairs=previous_images,changed_float_channels_per_trial=changed,static_library_SHA256=inputs['static_library_SHA256'],
        native_Apple_ICB_ABI=False,performance_benchmark=False,full_objective_complete=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['build','previous','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();d=audit(a.root,a.build,a.previous);write(a.out,d);print({k:v for k,v in d.items()if k not in ['cases','changed_float_channels_per_trial']})
