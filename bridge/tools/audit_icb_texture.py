#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reaudit three fresh-process direct/CPU-ICB cohorts and their raw bytes."""
from pathlib import Path
import argparse
import json
from public_large_scratch import read,sha,write
from verify_icb_texture import MODES,verify


def audit(root):
    root=Path(root);names=['metadata']+[f'repeat-{i}/{mode}'for i in range(3)for mode in MODES]
    assert {str(p.parent.parent.relative_to(root))for p in root.rglob('execution/manifest.json')}==set(names)
    rows=[];intervals=[];library=set();drivers=set();builds=set();sources=set()
    for name in names:
        p=root/name;m=read(p/'inputs.json');receipt=read(p/'execution/manifest.json');proof=verify(p);saved=read(p/'independent-verification.json')
        assert m['mode']==('metadata'if name=='metadata'else name.split('/')[1])
        data=read(p/'results.json')
        assert sha(p/'application')==m['executable_SHA256']==receipt['original_binary_sha256']
        if name=='metadata':assert data['driver_SHA256']==m['driver_SHA256']
        else:assert data['mode']==m['mode']
        argument=m['assets_SHA256']['consumer.metallib']if name=='metadata'else m['mode']
        assert receipt['arguments']==list(map(str,[p/'consumer.metallib',argument,p/'outputs']))
        for key,value in proof.items():assert saved[key]==value,(name,key)
        intervals.append((receipt['started_at'],receipt['completed_at']));library.add(m['static_library_SHA256']);drivers.add(m['driver_SHA256']);builds.add(m['source_build_inputs_SHA256']);sources.add(tuple(sorted(m['source_SHA256'].items())))
        assert receipt['GPU_reservation']['state']=='terminal'
        rows.append(dict(case=name,PID=receipt['pid'],**{k:v for k,v in proof.items()if k not in ['files_SHA256','device_identity']}))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]));assert len(library)==len(drivers)==len(builds)==len(sources)==1
    pairs=[]
    for repeat in range(3):
        for suffix in ['', '_wrong_texture','_wrong_sampler','_wrong_buffer','_no_dispatch']:
            for trial in range(3):
                for kind in ['output','parameters','input-0','input-1']:
                    name=f'trial-{trial}.{kind}.bin';a=root/f'repeat-{repeat}'/('native'+suffix)/'outputs'/name;b=root/f'repeat-{repeat}'/('cpu'+suffix)/'outputs'/name
                    assert a.read_bytes()==b.read_bytes(),str(a)
                    pairs.append(dict(repeat=repeat,mode=suffix or 'baseline',file=name,SHA256=sha(a)))
    tests=rows[1:];active=[r for r in tests if r['GPU_dispatches']]
    return dict(status='PASS',scope='Existing CPU-encoded compute ICB transport with caller-owned native argument resources',
        signed_terminal_nonoverlapping_processes=len(rows),metadata_only_processes=1,
        direct_processes=15,CPU_ICB_processes=15,consumer_dispatches=sum(r['GPU_dispatches']for r in tests),
        exact_computed_uint32=sum(r['checked_uint32']for r in active),sentinel_control_uint32=sum(r['checked_uint32']for r in tests if not r['GPU_dispatches']),
        unchanged_guard_bytes=sum(r['guard_bytes']for r in tests),identical_direct_ICB_raw_file_pairs=len(pairs),
        static_library_SHA256=next(iter(library)),driver_SHA256=next(iter(drivers)),source_build_inputs_SHA256=next(iter(builds)),
        runtime_modified=False,new_indirect_resource_lifetime_API=False,GPU_generated_texture_commands_qualified=False,
        performance_benchmark=False,full_objective_complete=False,cases=rows,pairs=pairs)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=audit(a.root);write(a.out,r)
    print(json.dumps({k:v for k,v in r.items()if k not in ['cases','pairs']},indent=2))
