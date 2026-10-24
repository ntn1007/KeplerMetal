#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute typed-reset raster reception, causal controls and repeat images."""
from pathlib import Path
import argparse
import hashlib
import struct
from public_large_scratch import read,sha,write
from verify_air_reset_render import verify,MODES


def audit(root,build):
    root,build=Path(root).resolve(),Path(build).resolve();m=read(build/'inputs.json')
    assert m['air_reset']is True;rows=[];intervals=[];proofs={}
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_air_reset_render import verify;print(json.dumps(verify(sys.argv[2])))'
    for repeat in range(3):
        for mode in MODES:
            path=root/'cohort'/str(repeat)/mode;proof=verify(path);receipt=read(path/'execution/manifest.json');inputs=read(path/'inputs.json')
            assert inputs==dict(m,mode=mode,driver_SHA256=inputs['driver_SHA256'],source_build_inputs_SHA256=sha(build/'inputs.json'))
            assert read(path/'independent-verification.json')==dict(proof,PID=receipt['pid'],static_library_SHA256=m['static_library_SHA256'])
            checked=read(path/'verification-execution.json');assert checked['exit_code']==0 and checked['isolated_interpreter']is True
            assert checked['argv'][1:]==['-I','-c',code,str(path/'oracles'),str(path)]and checked['code_SHA256']==hashlib.sha256(code.encode()).hexdigest()
            assert read(path/'verification.stdout')==proof and not(path/'verification.stderr').read_text()
            proofs[repeat,mode]=proof;rows.append(dict(repeat=repeat,PID=receipt['pid'],**{k:v for k,v in proof.items()if k!='files_SHA256'}))
            intervals.append((receipt['started_at'],receipt['completed_at']))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    image_pairs=repeat_images=repeat_files=changed_channels=0;changed=[]
    pairs=[('air_gpu','air_native'),('air_gpu','air_reference'),('air_no_reset','air_no_reset_native'),
           ('air_bad_context','air_bad_context_native'),('air_bad_context','air_no_reset')]
    for repeat in range(3):
        for a,b in pairs:
            for trial in range(8):
                name=f'trial-{trial}.image.bin';assert proofs[repeat,a]['files_SHA256'][name]==proofs[repeat,b]['files_SHA256'][name];image_pairs+=1
        different=[]
        for trial in range(8):
            prefix=f'trial-{trial}.';a=root/'cohort'/str(repeat)/'air_gpu/outputs';b=root/'cohort'/str(repeat)/'air_no_reset/outputs'
            x=(a/(prefix+'image.bin')).read_bytes()[256:-256];y=(b/(prefix+'image.bin')).read_bytes()[256:-256]
            count=sum(v!=w for v,w in zip(struct.unpack('<12288f',x),struct.unpack('<12288f',y)))
            if count:different.append(trial);changed_channels+=count
            # Same numerical witness, records and render inputs apart from the
            # single context-header bit plus owned address fields.
            c=root/'cohort'/str(repeat)/'air_bad_context/outputs'
            ctx=bytearray((a/(prefix+'reset-context.bin')).read_bytes());bad=bytearray((c/(prefix+'reset-context.bin')).read_bytes())
            ctx[80:88]=bad[80:88]=bytes(8);ctx[64]^=1;assert ctx==bad
            assert (a/(prefix+'reset-output.bin')).read_bytes()==(c/(prefix+'reset-output.bin')).read_bytes()
            effects={'records','arguments','witness','image','reset-root','reset-context'}
            for name,h in proofs[repeat,'air_gpu']['files_SHA256'].items():
                if name.startswith(prefix)and name[len(prefix):-4]not in effects:
                    assert h==proofs[repeat,'air_bad_context']['files_SHA256'][name],name
        assert different==[0,1,3,4,6];changed.append(dict(repeat=repeat,trials=different))
        if repeat:
            for mode in MODES:
                for name,h in proofs[repeat,mode]['files_SHA256'].items():
                    if name.endswith(('.reset-context.bin','.reset-root.bin')):continue
                    assert h==proofs[0,mode]['files_SHA256'][name],(mode,name);repeat_files+=1
                    if name.endswith('.image.bin'):repeat_images+=1
    return dict(status='PASS_AIR_RESET_RENDER',signed_terminal_nonoverlapping_processes=len(rows),
        rendered_frames=len(rows)*8,checked_float_channels=sum(r['checked_float_channels']for r in rows),
        raster_materializer_guard_bytes=sum(r['guard_bytes']for r in rows),reset_guard_bytes=sum(r['reset_guard_bytes']for r in rows),
        maximum_error=max(r['maximum_error']for r in rows),reset_dispatches=sum(r['reset_dispatches']for r in rows),
        reset_witness_words=sum(r['reset_witness_words']for r in rows),reference_control_image_pairs=image_pairs,
        repeat_image_pairs=repeat_images,repeat_readback_file_pairs=repeat_files,changed_float_channels_against_no_reset=changed_channels,
        changed_trials=changed,scope_and_ICBs_released_before_commit=True,observer_restored_before_scope=True,
        default_runtime_SHA256=m['static_library_SHA256'],native_Apple_ICB_ABI=False,performance_benchmark=False,
        full_objective_complete=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.build);write(a.out,r);print({k:v for k,v in r.items()if k not in ['cases','changed_trials']})
