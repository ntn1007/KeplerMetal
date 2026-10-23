#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck an exact 39-process reception cohort without Metal/GPU execution."""
from pathlib import Path
from collections import Counter
import argparse
import json
import struct
from public_large_scratch import read, sha
from verify_generic_import import verify_tess, verify_vertex, verify_contract


def expected_cases():
    cases = {'contract':dict(kind='contract',mode='contract')}
    for factor in [0,1,2,4,8,16,32,64]:
        for mode in ['native','imported']: cases[f'tess-{mode}-{factor}'] = dict(kind='tess',mode=mode,factor=factor)
    for interpolation in ['smooth','linear','flat']:
        for mode in ['native','vertex','fragment','both']:
            cases[f'vertex-{interpolation}-direct-{mode}'] = dict(kind='vertex',mode=mode,interpolation=interpolation,draw='direct')
    for draw in ['vertex-start','indexed16','indexed32','base-vertex','negative-base-vertex','instanced','base-instance','indirect','indirect-indexed','indirect-control']:
        cases[f'vertex-smooth-{draw}-both'] = dict(kind='vertex',mode='both',interpolation='smooth',draw=draw)
    return cases


def audit(root):
    root = Path(root); expected = expected_cases()
    assert {p.name for p in root.iterdir() if p.is_dir()} == set(expected)
    records, intervals, libraries = [], [], set()
    for label, case in expected.items():
        path = root / label; result = read(path / 'results.json'); inputs = read(path / 'inputs.json')
        for key,value in case.items(): assert inputs[key] == value
        if case['kind'] == 'tess':
            assert result['factor'] == case['factor'] and result['NAK_imported'] == (case['mode'] == 'imported')
        elif case['kind'] == 'vertex':
            for key in ['mode','draw','interpolation']: assert result[key] == case[key]
            assert result['memory'] == 'private'
        m = read(path / 'execution/manifest.json')
        assert m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
        assert m['GPU_reservation']['state'] == 'terminal'
        assert sha(path / 'application') == m['original_binary_sha256'] == inputs['executables'][case['kind']]
        assert sha(path / 'execution/application') == m['signed_binary_sha256']
        for name,digest in inputs['frozen'].items(): assert sha(path / name) == digest
        prefix = path / 'outputs/capture'
        proof = verify_contract(result) if case['kind'] == 'contract' else (verify_tess if case['kind'] == 'tess' else verify_vertex)(result,prefix)
        saved = read(path / 'independent-verification.json')
        for key,value in proof.items(): assert saved[key] == value
        assert saved['raw_SHA256'] == {p.name:sha(p) for p in (path / 'outputs').iterdir()}
        libraries.add(inputs['static_library_SHA256']); intervals.append((m['started_at'],m['completed_at']))
        records.append(dict(label=label,**proof))
    assert len(libraries) == 1
    intervals.sort(); assert all(a[1] <= b[0] for a,b in zip(intervals,intervals[1:]))
    pairs = []
    for factor in [0,1,2,4,8,16,32,64]:
        a = root / f'tess-native-{factor}/outputs/capture.coords.bin'
        b = root / f'tess-imported-{factor}/outputs/capture.coords.bin'
        assert Counter(struct.iter_unpack('<4f',a.read_bytes())) == Counter(struct.iter_unpack('<4f',b.read_bytes()))
        assert a.stat().st_size == b.stat().st_size
        pairs.append(dict(factor=factor,vertices=a.stat().st_size//16,coordinate_multisets_equal=True))
    different = []
    for interpolation in ['smooth','linear','flat']:
        a = (root / f'vertex-{interpolation}-direct-native/outputs/capture.image.bin').read_bytes()
        for mode in ['vertex','fragment','both']:
            b = (root / f'vertex-{interpolation}-direct-{mode}/outputs/capture.image.bin').read_bytes()
            words = sum(x!=y for x,y in zip(struct.iter_unpack('<f',a),struct.iter_unpack('<f',b)))
            assert words > 0; different.append(dict(interpolation=interpolation,mode=mode,changed_channels=words))
    vertex = [r for r in records if r['label'].startswith('vertex-')]
    tess = [r for r in records if r['label'].startswith('tess-')]
    return dict(status='PASS',static_library_SHA256=next(iter(libraries)),signed_terminal_processes=len(records),
        nonoverlapping=True,vertex_trials=len(vertex),vertex_float32_channels=sum(r['float32_channels'] for r in vertex),
        tessellation_trials=len(tess),tessellation_invocations=sum(r['invocations'] for r in tess),
        tessellation_float32_channels=sum(r['float32_channels'] for r in tess),
        tessellation_guard_bytes=sum(r['guard_bytes'] for r in tess),
        tessellation_untouched_tail_bytes=sum(r['untouched_tail_bytes'] for r in tess),
        verified_constructor_imports=sum(r['imports'] for r in records),
        argument_words=sum(r.get('argument_words',0) for r in records),
        constructor_only_processes=1,nested_refusals=4,cached_pipeline_refusals=1,
        GPU_render_command_buffers=38,tessellation_pairs=pairs,distinct_native_controls=different,
        cases=records,performance_benchmark=False,transparent_application_integration=False,full_objective_complete=False)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();report=audit(a.root)
    if a.out:
        with a.out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['cases','tessellation_pairs','distinct_native_controls']},indent=2))
