#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit native source render commands against raw-record and direct references."""
from pathlib import Path
import argparse
import hashlib
from public_large_scratch import read,sha,write
from verify_render_state_catalogue import MODES,verify


def audit(root,build,reference):
    root,build,reference=(Path(p).resolve()for p in(root,build,reference))
    m=read(build/'inputs.json');assert m['source_commands']is True
    for key,folder in [('source_SHA256',''),('runtime_sources_SHA256','library-src'),
                       ('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','assets')]:
        for name,digest in m[key].items():assert sha(build/folder/name)==digest,(key,name)
    assert sha(build/'application')==m['executable_SHA256']
    header='src/KeplerNativeRenderCommands.h';producer='src/render_source_commands_test.metal'
    assert header in m['source_SHA256']and producer in m['source_SHA256']
    commands=read(build/'commands.json');compile_=[c for c in commands if c['label']=='producer-metal']
    assert len(compile_)==1 and all(c['exit_code']==0 for c in commands)
    args=compile_[0]['argv']
    assert args==list(map(str,['xcrun','metal','-std=macos-metal2.4','-fmodules=none',
        '-I',build/'src','-c',build/producer,'-o',build/'producer.air']))
    rows=[];intervals=[];pairs=[];reference_producers=set()
    frozen_code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_render_state_catalogue import verify;print(json.dumps(verify(sys.argv[2])))'
    for mode in MODES:
        path=root/mode;proof=verify(path);old_proof=verify(reference/mode)
        receipt=read(path/'execution/manifest.json');inputs=read(path/'inputs.json')
        assert inputs==dict(m,mode=mode,driver_SHA256=inputs['driver_SHA256'],source_build_inputs_SHA256=sha(build/'inputs.json'))
        saved=read(path/'independent-verification.json')
        for key,value in proof.items():assert saved[key]==value,(mode,key)
        assert saved['PID']==receipt['pid']and saved['static_library_SHA256']==m['static_library_SHA256']
        verified=read(path/'verification-execution.json')
        assert verified['exit_code']==0 and verified['isolated_interpreter']is True
        assert verified['argv'][1:]==['-I','-c',frozen_code,str(path/'oracles'),str(path)]
        assert verified['code_SHA256']==hashlib.sha256(frozen_code.encode()).hexdigest()
        assert read(path/'verification.stdout')==proof and not(path/'verification.stderr').read_text()
        old=read(reference/mode/'inputs.json')
        assert old['static_library_SHA256']==m['static_library_SHA256']
        assert old['driver_SHA256']==inputs['driver_SHA256']
        assert old['assets_SHA256']['state.metallib']==m['assets_SHA256']['state.metallib']
        reference_producers.add(old['assets_SHA256']['producer.metallib'])
        assert set(proof['files_SHA256'])==set(old_proof['files_SHA256'])
        for name,digest in proof['files_SHA256'].items():
            assert digest==old_proof['files_SHA256'][name],(mode,name)
            pairs.append(dict(mode=mode,file=name,SHA256=digest))
        rows.append(dict(PID=receipt['pid'],**{k:v for k,v in proof.items()if k!='files_SHA256'}))
        intervals.append((receipt['started_at'],receipt['completed_at']))
    assert len(reference_producers)==1 and m['assets_SHA256']['producer.metallib']not in reference_producers
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    native_pairs=0
    for candidate,native in [('gpu','native'),('pipeline_only','pipeline_only_native'),
                             ('resources_only','resources_only_native'),('contracts','native'),('release','native')]:
        for trial in range(1 if candidate=='release'else 8):
            name=f'trial-{trial}.image.bin'
            assert(root/candidate/'outputs'/name).read_bytes()==(root/native/'outputs'/name).read_bytes()
            native_pairs+=1
    return dict(status='PASS',new_signed_terminal_nonoverlapping_processes=len(rows),
        new_checked_float_channels=sum(r['checked_float_channels']for r in rows),
        new_guard_bytes=sum(r['guard_bytes']for r in rows),maximum_error=max(r['maximum_error']for r in rows),
        native_reference_image_pairs=native_pairs,raw_record_reference_file_pairs=len(pairs),
        static_library_SHA256=m['static_library_SHA256'],header_SHA256=m['source_SHA256'][header],
        producer_source_SHA256=m['source_SHA256'][producer],producer_metallib_SHA256=m['assets_SHA256']['producer.metallib'],
        raw_record_producer_metallib_SHA256=next(iter(reference_producers)),
        native_Apple_render_command=False,application_integration_level=2,
        performance_benchmark=False,full_objective_complete=False,cases=rows,raw_pairs=pairs)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['build','reference','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.build,a.reference);write(a.out,r)
    print({k:v for k,v in r.items()if k not in ['cases','raw_pairs']})
