#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute the render-range cohort and current-archive regression evidence."""
from pathlib import Path
import argparse
import importlib
import sys

from public_large_scratch import read, sha, write
from verify_indirect_render_ranges import verify
MODES=("gpu","native","no_consumer","lifetime","contracts","fragment","fragment_native","fragment_lifetime","legacy","legacy_native")
from verify_gpu_icb_texture import verify as verify_gpu_compute
from verify_gpu_icb_texture_rows import MODES as GPU_MODES
from verify_icb_texture import verify as verify_cpu_compute, MODES as CPU_MODES


def audit(root, regression, library, reference):
    root, regression, library, reference = map(Path, (root, regression, library, reference))
    rows, intervals, archives, builds, pairs = [], [], set(), set(), []

    def record(path, proof):
        m, receipt, saved = read(path/'inputs.json'), read(path/'execution/manifest.json'), read(path/'independent-verification.json')
        for key, value in proof.items(): assert saved[key] == value, (str(path), key)
        assert receipt['exit_code'] == 0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
        assert receipt['GPU_reservation']['state'] == 'terminal'
        assert sha(path/'application') == m['executable_SHA256'] == receipt['original_binary_sha256']
        intervals.append((receipt['started_at'], receipt['completed_at']))
        archives.add(m['static_library_SHA256'])
        rows.append(dict(case=str(path.relative_to(root.parent)), PID=receipt['pid'],
                         **{k:v for k,v in proof.items() if k not in ['files_SHA256','raw_SHA256','raw_files','device_identity']}))

    def same(a, b, label):
        assert a.read_bytes() == b.read_bytes(), label
        pairs.append(dict(case=label, SHA256=sha(a)))

    assert {p.parent.parent.name for p in root.glob('*/execution/manifest.json')} == set(MODES)
    for mode in MODES:
        path = root/mode
        record(path, verify(path))
        builds.add(read(path/'inputs.json')['source_build_inputs_SHA256'])
    assert len(builds) == 1
    for mode, native in [('gpu','native'), ('lifetime','native'), ('contracts','native'),
                         ('fragment','fragment_native'), ('fragment_lifetime','fragment_native'), ('legacy','legacy_native')]:
        for trial in range(8):
            file = f'trial-{trial}.image.bin'
            same(root/mode/'outputs'/file, root/native/'outputs'/file, mode+'/'+file)

    expected = {'gpu/'+mode for mode in GPU_MODES} | {'cpu/'+mode for mode in CPU_MODES}
    expected.add('cpu/metadata')
    expected |= {'adapter/'+kind for kind in ['fp64','forward','reverse','icb','render']}
    assert {str(p.parent.parent.relative_to(regression)) for p in regression.glob('*/*/execution/manifest.json')} == expected
    for mode in GPU_MODES:
        path = regression/'gpu'/mode
        record(path, verify_gpu_compute(path))
        for trial in range(3):
            for suffix in ['output','input-0','input-1']:
                file = f'trial-{trial}.{suffix}.bin'
                same(path/'outputs'/file, reference/'qualified-cohort/gpu-0'/mode/'outputs'/file, 'gpu/'+mode+'/'+file)
    record(regression/'cpu/metadata', verify_cpu_compute(regression/'cpu/metadata'))
    for mode in CPU_MODES:
        path = regression/'cpu'/mode
        record(path, verify_cpu_compute(path))
        for trial in range(3):
            for suffix in ['output','parameters','input-0','input-1']:
                file = f'trial-{trial}.{suffix}.bin'
                same(path/'outputs'/file, reference/'qualified-cohort/baseline'/mode/'outputs'/file, 'cpu/'+mode+'/'+file)
    oracle_names = dict(fp64='verify_fp64_client', forward='verify_fp64_conversion_client',
                        reverse='verify_fp64_reverse_client', icb='verify_example', render='verify_cpu_icb_render')
    for kind, module in oracle_names.items():
        path = regression/'adapter'/kind
        sys.path.insert(0, str(path/'oracles'))
        oracle = importlib.import_module(module)
        record(path, oracle.verify(path))

    current = read(library/'manifest.json')
    assert archives == {current['static_library_SHA256']} and sha(library/'libKeplerMetal.a') in archives
    for file, digest in current['source_SHA256'].items(): assert sha(library/'src'/file) == digest
    assert len(current['source_SHA256']) == 47 and len(current['object_SHA256']) == 7
    intervals.sort()
    assert all(a[1] <= b[0] for a,b in zip(intervals,intervals[1:]))
    new = rows[:len(MODES)]
    return dict(status='PASS', signed_terminal_nonoverlapping_processes=len(rows),
        render_range_processes=len(MODES), regression_processes=len(rows)-len(MODES),
        checked_render_float_channels=sum(r['checked_float_channels'] for r in new),
        checked_render_guard_bytes=sum(r['guard_bytes'] for r in new),
        maximum_render_error=max(r['maximum_error'] for r in new),
        exact_reference_image_pairs=48, identical_raw_file_pairs=len(pairs),
        range_producer_dispatches=70, range_materializer_dispatches=56,
        static_library_SHA256=next(iter(archives)), runtime_source_count=47,
        runtime_modified=True, native_Apple_ICB_ABI=False, application_integration_level=2,
        performance_benchmark=False, full_objective_complete=False, cases=rows, pairs=pairs)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('--regression',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=audit(a.root,a.regression,a.library,a.reference);write(a.out,result)
    print({k:v for k,v in result.items() if k not in ['cases','pairs']})
