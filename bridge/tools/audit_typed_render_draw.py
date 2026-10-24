#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute typed draw producer, raster references, operation order and repeats."""
from pathlib import Path
import argparse
import struct
from public_large_scratch import read,sha,write
from verify_air_render_draw import verify as verify_producer
from verify_typed_render_draw import verify as verify_render,MODES


def audit(root,render_build):
    root,render_build=Path(root).resolve(),Path(render_build).resolve();rows=[];intervals=[];producer={};render={}
    def check(path,fn,family):
        proof=fn(path);receipt=read(path/'execution/manifest.json');inp=read(path/'inputs.json')
        expected=dict(proof,PID=receipt['pid'])
        if family=='render':expected['static_library_SHA256']=inp['static_library_SHA256']
        assert read(path/'independent-verification.json')==expected
        execution=read(path/'verification-execution.json');assert execution['exit_code']==0 and execution['isolated_interpreter']is True
        assert read(path/'verification.stdout')==proof and not(path/'verification.stderr').read_text()
        intervals.append((receipt['started_at'],receipt['completed_at']))
        rows.append(dict(family=family,PID=receipt['pid'],path=str(path.relative_to(root)),**{k:v for k,v in proof.items()if isinstance(v,(str,int,float,bool))}))
        return proof
    for repeat in range(3):
        for variant in ['lowered','reference']:
            p=root/'qualified-producer-cohort'/str(repeat)/variant;producer[repeat,variant]=check(p,verify_producer,'producer')
            assert read(p/'inputs.json')['source_build_inputs_SHA256']==sha(root/'build-03/inputs.json')
    control=check(root/'qualified-producer-no-dispatch',verify_producer,'producer')
    producer_pairs=producer_repeat_pairs=0
    for repeat in range(3):
        assert producer[repeat,'lowered']['files_SHA256']==producer[repeat,'reference']['files_SHA256'];producer_pairs+=len(producer[repeat,'lowered']['files_SHA256'])
        for variant in ['lowered','reference']:
            if repeat:
                assert producer[repeat,variant]['files_SHA256']==producer[0,variant]['files_SHA256'];producer_repeat_pairs+=len(producer[repeat,variant]['files_SHA256'])
    inputs=read(render_build/'inputs.json')
    for repeat in range(3):
        for mode in MODES:
            p=root/'render-cohort'/str(repeat)/mode;render[repeat,mode]=check(p,verify_render,'render');m=read(p/'inputs.json')
            assert m==dict(inputs,mode=mode,driver_SHA256=m['driver_SHA256'],source_build_inputs_SHA256=sha(render_build/'inputs.json'))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    image_pairs=repeat_images=repeat_files=0;changed={};pairs=[('draw_gpu','draw_native'),('draw_gpu','draw_reference'),
        ('draw_no_dispatch','draw_no_dispatch_native'),('draw_after_reset','draw_after_reset_native'),
        ('draw_then_reset','draw_then_reset_native'),('draw_after_reset','draw_then_reset')]
    for repeat in range(3):
        for a,b in pairs:
            for trial in range(8):
                name=f'trial-{trial}.image.bin';assert render[repeat,a]['files_SHA256'][name]==render[repeat,b]['files_SHA256'][name];image_pairs+=1
        for mode,wanted in [('draw_no_dispatch',[0,2,3,4,5]),('draw_then_reset',[0,1,2,3]),('draw_after_reset',[0,1,2,3])]:
            counts=[]
            for trial in range(8):
                name=f'trial-{trial}.image.bin';a=(root/'render-cohort'/str(repeat)/'draw_gpu/outputs'/name).read_bytes()[256:-256];b=(root/'render-cohort'/str(repeat)/mode/'outputs'/name).read_bytes()[256:-256]
                counts.append(sum(x!=y for x,y in zip(struct.unpack('<12288f',a),struct.unpack('<12288f',b))))
            assert [i for i,n in enumerate(counts)if n]==wanted,(mode,counts)
            changed.setdefault(mode,[]).append(counts)
        if repeat:
            for mode in MODES:
                for name,h in render[repeat,mode]['files_SHA256'].items():
                    if name.endswith(('.reset-root.bin','.reset-context.bin')):continue
                    assert h==render[0,mode]['files_SHA256'][name],(mode,name);repeat_files+=1
                    if name.endswith('.image.bin'):repeat_images+=1
    return dict(status='PASS_TYPED_RENDER_DRAW',signed_terminal_nonoverlapping_reception_hosts=len(rows),
        producer_hosts=7,producer_dispatches=sum(r['compute_dispatches']for r in rows if r['family']=='producer'),
        producer_checked_bytes=sum(r['checked_bytes']for r in rows if r['family']=='producer'),
        producer_witness_words=sum(r['witness_words']for r in rows if r['family']=='producer'),
        producer_modified_records=sum(r['modified_records']for r in rows if r['family']=='producer'),
        producer_draw_records=sum(r['draw_records']for r in rows if r['family']=='producer'),
        producer_reset_records=sum(r['reset_records']for r in rows if r['family']=='producer'),
        producer_nonzero_state_identities_preserved=sum(r['nonzero_state_identities_preserved']for r in rows if r['family']=='producer'),
        producer_candidate_reference_file_pairs=producer_pairs,producer_repeat_file_pairs=producer_repeat_pairs,
        render_hosts=27,rendered_frames=216,checked_float_channels=sum(r['checked_float_channels']for r in rows if r['family']=='render'),
        maximum_error=max(r['maximum_error']for r in rows if r['family']=='render'),
        render_producer_dispatches=sum(r['typed_draw_dispatches']for r in rows if r['family']=='render'),
        render_witness_words=sum(r['arithmetic_witness_words']for r in rows if r['family']=='render'),
        ordinary_native_programs_checked=sum(r['ordinary_native_programs_checked']for r in rows if r['family']=='render'),
        raster_materializer_guard_bytes=sum(r['guard_bytes']for r in rows if r['family']=='render'),
        root_guard_bytes=sum(r['root_guard_bytes']for r in rows if r['family']=='render'),
        reference_control_image_pairs=image_pairs,repeat_image_pairs=repeat_images,repeat_readback_file_pairs=repeat_files,
        changed_float_channels_per_trial=changed,static_library_SHA256=inputs['static_library_SHA256'],
        native_Apple_ICB_ABI=False,performance_benchmark=False,full_objective_complete=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--render-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();d=audit(a.root,a.render_build);write(a.out,d);print({k:v for k,v in d.items()if k not in ['cases','changed_float_channels_per_trial']})
