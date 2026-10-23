#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the native resource-identity matrix offline; never load Metal."""
from pathlib import Path
import argparse
import json
from public_large_scratch import read,sha
from verify_native_resource_identity import MODES,execute,inspect,icb_compile


def audit(root):
    root=Path(root);cases=[]
    for version,standard in [('23','macos-metal2.3'),('30','metal3.0'),('40','metal4.0')]:
        expected={f'{mode}-{repeat}' for repeat in range(2) for mode in MODES}
        if version=='23':expected|={'inspect','prepare'}
        assert {p.name for p in (root/('accepted-'+version)).iterdir()if p.is_dir()}==expected
        for label in sorted(expected):cases.append((root/('accepted-'+version)/label,standard,label.rsplit('-',1)[0] if label not in ['inspect','prepare'] else label))
    cases.extend([(root/'prepare-metal30','metal3.0','prepare'),(root/'prepare-metal40','metal4.0','prepare'),
                  (root/'icb-compile-qualified','macos-metal2.3','icb_compile')])
    records=[];intervals=[];standards={}
    for path,standard,mode in cases:
        inputs=read(path/'inputs.json');result=read(path/'results.json');manifest=read(path/'execution/manifest.json')
        assert inputs['standard']==standard and inputs['mode']==mode
        assert manifest['exit_code']==0 and not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status']
        assert manifest['GPU_reservation']['state']=='terminal'
        assert sha(path/'application')==inputs['executable_SHA256']==manifest['original_binary_sha256']
        assert sha(path/'execution/application')==manifest['signed_binary_sha256']
        for name,digest in inputs['frozen'].items():assert sha(path/name)==digest
        proof=inspect(result)if mode=='inspect'else icb_compile(result)if mode=='icb_compile'else execute(result,path/'outputs')
        saved=read(path/'independent-verification.json')
        for key,value in proof.items():assert saved[key]==value,(path.name,key)
        intervals.append((manifest['started_at'],manifest['completed_at']))
        records.append(dict(case=str(path.relative_to(root)),standard=standard,**proof))
        if mode not in ['inspect','icb_compile']:standards.setdefault(standard,set()).add(inputs['frozen']['shader.metallib'])
    assert all(len(x)==1 for x in standards.values())
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    comparisons=0
    for version in ['23','30','40']:
        for repeat in range(2):
            for trial in range(3):
                a=root/f'accepted-{version}/native-{repeat}/outputs/trial-{trial}.output.bin'
                b=root/f'accepted-{version}/direct-{repeat}/outputs/trial-{trial}.output.bin'
                assert a.read_bytes()==b.read_bytes();comparisons+=1
    executed=[r for r in records if r.get('command_buffers')]
    return dict(status='PASS',signed_terminal_nonoverlapping_processes=len(records),
        user_dispatches=sum(r['GPU_dispatches'] for r in records),
        command_buffers=sum(r['command_buffers'] for r in executed),checked_uint32=sum(r['checked_uint32']for r in executed),
        guard_bytes=sum(r['guard_bytes']for r in executed),
        expected_differences_from_baseline=sum(r['expected_differences_from_baseline']for r in executed),
        direct_native_identical_raw_output_pairs=comparisons,
        libraries_by_requested_standard={key:next(iter(value))for key,value in standards.items()},
        native_property_getters_and_shader_execution=True,interposition=False,core_runtime_linked=False,
        native_ICB_pipeline_created=False,ICB_first_compiler_refusal='air.command_buffer argument metadata',
        Metal_3_or_4_feature_conformance=False,performance_benchmark=False,full_objective_complete=False,cases=records)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();report=audit(a.root)
    if a.out:
        with a.out.open('x')as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items()if k!='cases'},indent=2))
