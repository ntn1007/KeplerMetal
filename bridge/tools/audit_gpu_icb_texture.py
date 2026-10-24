#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit GPU-generated texture commands plus the native/CPU-ICB regression."""
from pathlib import Path
import argparse
import json
from public_large_scratch import read,sha,write
from public_native_msl_commands import msl_abi
from verify_gpu_icb_texture import verify as gpu_verify
from verify_gpu_icb_texture_rows import MODES
from verify_icb_texture import verify as baseline_verify,MODES as BASELINE_MODES


def audit(root,reference):
    root,reference=Path(root),Path(reference)
    names=['baseline/'+m for m in BASELINE_MODES]+[f'gpu-{i}/{m}'for i in range(3)for m in MODES]
    assert{str(p.parent.parent.relative_to(root))for p in root.rglob('execution/manifest.json')}==set(names)
    rows=[];intervals=[];archives=set();drivers=set();builds={'gpu':set(),'baseline':set()}
    for name in names:
        p=root/name;m=read(p/'inputs.json');receipt=read(p/'execution/manifest.json');gpu=name.startswith('gpu-')
        proof=gpu_verify(p)if gpu else baseline_verify(p);saved=read(p/'independent-verification.json')
        for key,value in proof.items():assert saved[key]==value,(name,key)
        assert m['mode']==name.split('/')[1]and read(p/'results.json')['mode']==m['mode']
        assert receipt['arguments']==list(map(str,[p/'consumer.metallib',m['mode'],p/'outputs']))
        assert sha(p/'application')==receipt['original_binary_sha256']==m['executable_SHA256']
        assert receipt['GPU_reservation']['state']=='terminal'
        if gpu:
            assert(p/'include/KeplerCommandIR.h').read_text()==msl_abi((p/'src/KeplerCommandIR.h').read_text())
            assert(p/'include/metal_command_buffer').read_bytes()==(p/'src/KeplerNativeMSLCommands.h').read_bytes()
        builds['gpu'if gpu else'baseline'].add(m['source_build_inputs_SHA256'])
        archives.add(m['static_library_SHA256']);drivers.add(m['driver_SHA256']);intervals.append((receipt['started_at'],receipt['completed_at']))
        rows.append(dict(case=name,PID=receipt['pid'],**{k:v for k,v in proof.items()if k not in ['files_SHA256','device_identity']}))
    assert len(archives)==len(drivers)==1 and all(len(b)==1 for b in builds.values())
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    pairs=[]
    for mode in BASELINE_MODES:
        for trial in range(3):
            for suffix in ['output','parameters','input-0','input-1']:
                file=f'trial-{trial}.{suffix}.bin';a=root/'baseline'/mode/'outputs'/file;b=reference/'repeat-0'/mode/'outputs'/file
                assert a.read_bytes()==b.read_bytes();pairs.append(dict(group='baseline',mode=mode,file=file,SHA256=sha(a)))
    for repeat in [1,2]:
        for mode in MODES:
            for trial in range(3):
                for suffix in ['output','input-0','input-1']:
                    file=f'trial-{trial}.{suffix}.bin';a=root/f'gpu-{repeat}'/mode/'outputs'/file;b=root/'gpu-0'/mode/'outputs'/file
                    assert a.read_bytes()==b.read_bytes();pairs.append(dict(group='GPU_repeated',repeat=repeat,mode=mode,file=file,SHA256=sha(a)))
    new=rows[len(BASELINE_MODES):];base=rows[:len(BASELINE_MODES)]
    return dict(status='PASS',signed_terminal_nonoverlapping_processes=len(rows),GPU_command_processes=len(new),baseline_processes=len(base),
        GPU_texture_consumer_dispatches=sum(r['GPU_dispatches']for r in new),GPU_producer_dispatches=sum(r['producer_dispatches']for r in new),materializer_dispatches=sum(r['materializer_dispatches']for r in new),
        exact_GPU_command_consumer_uint32=sum(r['checked_uint32']for r in new if r['GPU_dispatches']),sentinel_GPU_command_control_uint32=sum(r['checked_uint32']for r in new if not r['GPU_dispatches']),
        new_guard_bytes=sum(r['guard_bytes']for r in new),GPU_records_checked=sum(r['GPU_records_checked']for r in new),zero_CTA_records=sum(r['zero_CTA_records']for r in new),
        baseline_consumer_dispatches=sum(r['GPU_dispatches']for r in base),baseline_computed_uint32=sum(r['checked_uint32']for r in base if r['GPU_dispatches']),baseline_sentinel_uint32=sum(r['checked_uint32']for r in base if not r['GPU_dispatches']),
        baseline_guard_bytes=sum(r['guard_bytes']for r in base),identical_raw_file_pairs=len(pairs),
        static_library_SHA256=next(iter(archives)),driver_SHA256=next(iter(drivers)),source_build_inputs_SHA256={k:next(iter(v))for k,v in builds.items()},
        new_runtime_resource_lifetime_API=False,runtime_modified=False,native_Apple_ICB_ABI=False,performance_benchmark=False,full_objective_complete=False,cases=rows,pairs=pairs)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.reference);write(a.out,r);print(json.dumps({k:v for k,v in r.items()if k not in ['cases','pairs']},indent=2))
