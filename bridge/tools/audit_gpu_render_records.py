#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit generated draw arguments, nonempty lifetimes and current-runtime regression."""
from pathlib import Path
import argparse
import importlib
import struct
import sys

from public_large_scratch import read, sha, write
from verify_indirect_render_ranges import MODES, verify
from verify_gpu_icb_texture import verify as verify_gpu_compute
from verify_gpu_icb_texture_rows import MODES as GPU_MODES
from verify_icb_texture import verify as verify_cpu_compute, MODES as CPU_MODES
from audit_indirect_render_ranges import MODES as RANGE_MODES


def audit(root, regression, library, range_reference, texture_reference, expected_runtime_sources=48):
    root, regression, library, range_reference, texture_reference = map(
        Path, (root, regression, library, range_reference, texture_reference))
    rows, intervals, archives, pairs, render_builds, drivers = [], [], set(), [], set(), set()
    producer_dispatches = materializer_dispatches = record_dispatches = 0
    rejected_records = empty_slots = 0

    def record(path, proof):
        m, receipt, saved = read(path/'inputs.json'), read(path/'execution/manifest.json'), read(path/'independent-verification.json')
        for key,value in proof.items(): assert saved[key] == value, (str(path),key)
        assert receipt['exit_code'] == 0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
        assert receipt['GPU_reservation']['state'] == 'terminal' and not receipt['GPU_reservation']['known_signed_processes_live']
        assert sha(path/'application') == m['executable_SHA256'] == receipt['original_binary_sha256']
        assert sha(path/'execution/application') == receipt['signed_binary_sha256']
        for key,folder in [('source_SHA256',''),('source_hashes',''),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
            for name,digest in m.get(key,{}).items(): assert sha(path/folder/name) == digest,(str(path),name)
        archives.add(m['static_library_SHA256'])
        if 'driver_SHA256' in m: drivers.add(m['driver_SHA256'])
        intervals.append((receipt['started_at'],receipt['completed_at']))
        rows.append(dict(case=str(path.relative_to(root.parent)),PID=receipt['pid'],
            **{k:v for k,v in proof.items() if k not in ['files_SHA256','raw_SHA256','raw_files','device_identity']}))

    def same(a,b,label):
        assert a.read_bytes() == b.read_bytes(),label
        pairs.append(dict(case=label,SHA256=sha(a)))

    assert {p.parent.parent.name for p in root.glob('*/execution/manifest.json')} == set(MODES)
    for mode in MODES:
        path = root/mode
        record(path,verify(path))
        m,d = read(path/'inputs.json'),read(path/'results.json')
        render_builds.add(m['source_build_inputs_SHA256'])
        producer_dispatches += sum(r['producer_dispatches'] for r in d['runs'])
        preparations = [e for e in d['scope_events'] if e['operation']=='prepare_GPU_indirect_render_range']
        materializer_dispatches += len(preparations)
        record_dispatches += sum(e['GPU_generated_draw_records'] for e in preparations)
        if 'records' in mode and not mode.endswith('_native'):
            for trial in range(len(d['runs'])):
                raw=(path/'outputs'/f'trial-{trial}.witness.bin').read_bytes()
                for slot in range(4):
                    reason=struct.unpack_from('<I',raw,64+slot*16+12)[0]&0xffff
                    rejected_records += reason in (1,2,3)
                    empty_slots += reason==4
    assert len(render_builds)==1

    references = [('gpu','native'),('lifetime','native'),('contracts','native'),
        ('fragment','fragment_native'),('fragment_lifetime','fragment_native'),('legacy','legacy_native'),
        ('records','records_native'),('fragment_records','fragment_records_native'),
        ('release','native'),('fragment_release','fragment_native'),
        ('records_release','records_native'),('fragment_records_release','fragment_records_native')]
    image_pairs=0
    for mode,native in references:
        trials=1 if mode.endswith('release') else 8
        for trial in range(trials):
            name=f'trial-{trial}.image.bin'
            same(root/mode/'outputs'/name,root/native/'outputs'/name,mode+'/'+name)
            image_pairs+=1
    for mode in RANGE_MODES:
        for p in (root/mode/'outputs').iterdir():
            same(p,range_reference/'qualified-cohort-02'/mode/'outputs'/p.name,'range-regression/'+mode+'/'+p.name)

    expected={'gpu/'+m for m in GPU_MODES}|{'cpu/'+m for m in CPU_MODES}|{'cpu/metadata'}
    expected|={'adapter/'+k for k in ['fp64','forward','reverse','icb','render']}
    assert {str(p.parent.parent.relative_to(regression)) for p in regression.glob('*/*/execution/manifest.json')} == expected
    for group,modes,verifier,reference in [('gpu',GPU_MODES,verify_gpu_compute,'gpu-0'),('cpu',CPU_MODES,verify_cpu_compute,'baseline')]:
        for mode in modes:
            path=regression/group/mode
            record(path,verifier(path))
            for trial in range(3):
                for suffix in (['output','input-0','input-1'] if group=='gpu' else ['output','parameters','input-0','input-1']):
                    name=f'trial-{trial}.{suffix}.bin'
                    same(path/'outputs'/name,texture_reference/'qualified-cohort'/reference/mode/'outputs'/name,group+'/'+mode+'/'+name)
    record(regression/'cpu/metadata',verify_cpu_compute(regression/'cpu/metadata'))
    for kind,module in dict(fp64='verify_fp64_client',forward='verify_fp64_conversion_client',reverse='verify_fp64_reverse_client',icb='verify_example',render='verify_cpu_icb_render').items():
        path=regression/'adapter'/kind
        sys.path.insert(0,str(path/'oracles'))
        record(path,importlib.import_module(module).verify(path))
    current=read(library/'manifest.json')
    assert archives=={current['static_library_SHA256']} and sha(library/'libKeplerMetal.a') in archives
    for name,digest in current['source_SHA256'].items(): assert sha(library/'src'/name)==digest
    assert len(current['source_SHA256'])==expected_runtime_sources and len(current['object_SHA256'])==7
    assert len(drivers)==1
    intervals.sort();assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:]))
    new=[r for r in rows[:len(MODES)] if r['mode'] not in RANGE_MODES]
    return dict(status='PASS',signed_terminal_nonoverlapping_processes=len(rows),render_processes=len(MODES),
        new_render_processes=len(new),regression_processes=len(rows)-len(new),
        new_checked_float_channels=sum(r['checked_float_channels'] for r in new),
        all_checked_render_float_channels=sum(r['checked_float_channels'] for r in rows[:len(MODES)]),
        new_guard_bytes=sum(r['guard_bytes'] for r in new),maximum_error=max(r['maximum_error'] for r in new),
        exact_reference_image_pairs=image_pairs,identical_raw_file_pairs=len(pairs),
        render_range_producer_dispatches=producer_dispatches,all_render_materializer_dispatches=materializer_dispatches,
        GPU_record_materializer_dispatches=record_dispatches,rejected_occupied_records=rejected_records,empty_record_slots=empty_slots,
        static_library_SHA256=next(iter(archives)),driver_SHA256=next(iter(drivers)),runtime_source_count=expected_runtime_sources,
        application_integration_level=2,native_Apple_ICB_ABI=False,GPU_selected_pipeline_or_resources=False,
        performance_benchmark=False,full_objective_complete=False,cases=rows,pairs=pairs)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['regression','library','range-reference','texture-reference','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.regression,a.library,a.range_reference,a.texture_reference);write(a.out,r)
    print({k:v for k,v in r.items() if k not in ['cases','pairs']})
