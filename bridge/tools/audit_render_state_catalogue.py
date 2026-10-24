#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute state selection and the complete preceding runtime reception."""
from pathlib import Path
import argparse
import hashlib
import struct
from public_large_scratch import read,sha,write
from verify_render_state_catalogue import MODES,verify
from audit_gpu_render_records import audit as audit_regression


def audit(root,regression,library,range_reference,texture_reference):
    root,regression,library,range_reference,texture_reference=map(Path,(root,regression,library,range_reference,texture_reference))
    assert {p.parent.parent.name for p in root.glob('*/execution/manifest.json')}==set(MODES)
    rows=[];intervals=[];archives=set();drivers=set();builds=set();pairs=[];choices=set()
    verification_code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_render_state_catalogue import verify;print(json.dumps(verify(sys.argv[2])))'
    for mode in MODES:
        path=root/mode;proof=verify(path);saved=read(path/'independent-verification.json')
        for key,value in proof.items():assert saved[key]==value,(mode,key)
        m,receipt,verified=read(path/'inputs.json'),read(path/'execution/manifest.json'),read(path/'verification-execution.json')
        assert verified['exit_code']==0 and verified['isolated_interpreter']is True
        assert verified['argv'][1:]==['-I','-c',verification_code,str(path/'oracles'),str(path)]
        assert verified['code_SHA256']==hashlib.sha256(verification_code.encode()).hexdigest()
        assert (path/'verification.stderr').read_text()==''and read(path/'verification.stdout')==proof
        intervals.append((receipt['started_at'],receipt['completed_at']))
        archives.add(m['static_library_SHA256']);drivers.add(m['driver_SHA256']);builds.add(m['source_build_inputs_SHA256'])
        rows.append(dict(case=mode,PID=receipt['pid'],**{k:v for k,v in proof.items()if k!='files_SHA256'}))
        if mode=='gpu':
            for trial,row in enumerate(read(path/'results.json')['runs']):
                raw=(path/'outputs'/f'trial-{trial}.records.bin').read_bytes();witness=(path/'outputs'/f'trial-{trial}.witness.bin').read_bytes()
                for slot in [0,1,3]:
                    identity=struct.unpack_from('<Q',raw,64+slot*64+32)[0]
                    if identity in row['identifiers']:
                        state=row['identifiers'].index(identity)
                        if struct.unpack_from('<I',witness,64+(slot*2+state)*16+4)[0]:choices.add(state)
    assert choices=={0,1}and len(archives)==len(drivers)==len(builds)==1
    for candidate,native in [('gpu','native'),('pipeline_only','pipeline_only_native'),('resources_only','resources_only_native'),('contracts','native'),('release','native')]:
        for trial in range(1 if candidate=='release'else 8):
            name=f'trial-{trial}.image.bin';a=root/candidate/'outputs'/name;b=root/native/'outputs'/name
            assert a.read_bytes()==b.read_bytes();pairs.append(dict(candidate=candidate,trial=trial,SHA256=sha(a)))
    differences={}
    for control in ['forced_0','forced_1','pipeline_only','resources_only']:
        count=0
        for trial in range(8):
            a=(root/'gpu'/'outputs'/f'trial-{trial}.image.bin').read_bytes()[256:-256]
            b=(root/control/'outputs'/f'trial-{trial}.image.bin').read_bytes()[256:-256]
            count+=sum(x!=y for x,y in zip(struct.unpack('<12288f',a),struct.unpack('<12288f',b)))
        assert count>0,control;differences[control]=count
    baseline=audit_regression(regression/'render',regression/'compute',library,range_reference,texture_reference,expected_runtime_sources=51)
    for p in regression.rglob('execution/manifest.json'):
        r=read(p);intervals.append((r['started_at'],r['completed_at']))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    current=read(library/'manifest.json');assert archives=={current['static_library_SHA256']}
    return dict(status='PASS',signed_terminal_nonoverlapping_processes=len(intervals),new_processes=len(rows),regression_processes=baseline['signed_terminal_nonoverlapping_processes'],
        new_checked_float_channels=sum(r['checked_float_channels']for r in rows),new_guard_bytes=sum(r['guard_bytes']for r in rows),
        maximum_error=max(r['maximum_error']for r in rows),native_reference_image_pairs=len(pairs),both_GPU_candidates_observed=True,
        changed_channels_against_controls=differences,GPU_selected_candidate_records=sum(r['GPU_selected_candidate_records']for r in rows),
        GPU_rejected_candidate_records=sum(r['GPU_rejected_candidate_records']for r in rows),API_refusals=28,
        runtime_source_count=51,static_library_SHA256=next(iter(archives)),driver_SHA256=next(iter(drivers)),
        native_Apple_ICB_ABI=False,execution='CPU encodes certified states; GPU predicates select their native indirect draws',
        application_integration_level=2,performance_benchmark=False,full_objective_complete=False,cases=rows,pairs=pairs,regression=baseline)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['regression','library','range-reference','texture-reference','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.regression,a.library,a.range_reference,a.texture_reference);write(a.out,r)
    print({k:v for k,v in r.items()if k not in ['cases','pairs','regression']})
