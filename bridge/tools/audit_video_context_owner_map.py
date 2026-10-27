#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck same-process video owner/VM observations; no IOKit calls."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from verify_video_context_owner_map import verify

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def validate_observation(r):
    assert r['status'] == 'OWNER_MAP_COVERAGE_RECORDED' and r['owner_qualified']
    owner = r['owner_registry_ID']
    assert owner and r['mapping_ranges_disjoint']
    for phase in ('before', 'after_open', 'after_associate', 'after_context_close', 'after_shared_close'):
        snap = r['registry_' + phase]
        assert snap['status'] == 0 and snap['iterator_valid'] and not snap['truncated']
        entries = [x for x in snap['contexts'] if x['id'] == owner]
        if phase in ('after_open', 'after_associate'):
            assert len(entries) == 1 and entries[0]['creator_matches_self_pid']
        else:
            assert not entries
    for typ in (1, 2):
        assert r['map%d_attempts' % typ] == 1 and r['map%d_status' % typ] == 0
        assert r['map%d_returned' % typ] and r['map%d_bytes' % typ] == 4096
        assert [r['type%d_%s' % (typ, phase)] for phase in
                ('before_close', 'after_context_close', 'after_shared_close')] == [1, 0, 0]
    assert not r['mapping_contents_read_or_written'] and not r['explicit_unmap_calls']
    return owner


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'wrong', 'attach', 'first', 'second', 'vm-control', 'vm-source', 'vm-binary'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    directories = [a.inventory, a.wrong, a.attach, a.first, a.second]
    assert len({x.resolve() for x in directories}) == len(directories)
    rows = []
    for directory in directories:
        result = verify(directory)
        inp = json.loads((directory / 'inputs.json').read_text())
        raw = json.loads((directory / 'results.json').read_text())
        manifest = json.loads((directory / 'execution/manifest.json').read_text())
        for name in ('video_context_owner_map_probe.mm', 'video_context_owner_map.py', 'verify_video_context_owner_map.py'):
            assert inp['frozen']['src/' + name] == sha(ROOT / 'tools' / name)
        rows.append((result, inp, raw, manifest, directory))
    assert [r[0]['outcome'] for r in rows] == ['CONTROL_PASS', 'CONTROL_PASS', 'ASSOCIATION_ACCEPTED', 'COVERAGE_RECORDED', 'COVERAGE_RECORDED']
    assert len({r[3]['original_binary_sha256'] for r in rows}) == 1
    assert len({r[3]['pid'] for r in rows}) == len(rows)
    intervals = sorted((datetime.fromisoformat(r[3]['started_at']), datetime.fromisoformat(r[3]['completed_at'])) for r in rows)
    assert all(start <= end for start, end in intervals)
    assert all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:]))
    assert all(r[1]['profile'] == rows[0][1]['profile'] for r in rows)
    owners = [validate_observation(r[2]) for r in rows[-2:]]
    assert owners[0] != owners[1]
    symbols = subprocess.run(['nm', '-u', str(a.first / 'application')], check=True, capture_output=True, text=True).stdout
    assert '_IOConnectMapMemory' in symbols and '_IOConnectAddClient' in symbols
    assert not any(x in symbols for x in ('_IOConnectUnmapMemory', '_IOConnectCallMethod', '_IOConnectCallScalarMethod', '_IOConnectCallStructMethod', '_mach_vm_deallocate'))
    control = json.loads(a.vm_control.read_text())
    assert control['status'] == 'PASS' and not control['iokit_mapping_cleanup_proved']
    assert sha(a.vm_source) == control['source_sha256'] and sha(a.vm_binary) == control['binary_sha256']
    subprocess.run(['codesign', '--verify', '--strict', str(a.vm_binary)], check=True, capture_output=True)
    assert [x['mode'] for x in control['runs']] == ['positive', 'positive', 'reject', 'invalid']
    assert len({x['pid'] for x in control['runs']}) == 4
    for x in control['runs'][:3]:
        z = x['result'];assert x['exit_code'] == 0 and z['target_present_before'] and z['adjacent_guards_preserved'] and not z['gpu_or_iokit_called'] and z['cleanup_status'] == 0
        assert z['target_present_after'] == (x['mode'] == 'reject')
        assert z['target_deallocate_calls'] == (0 if x['mode'] == 'reject' else 1)
    assert control['runs'][3]['exit_code'] == 2 and control['runs'][3]['result'] is None
    print(json.dumps({'status': 'PASS', 'cohort_processes': len(rows), 'owner_map_observations': len(owners),
                      'mapped_regions_per_observation': 2, 'region_bytes': 4096,
                      'coverage_after_context_close': False, 'cohort_processes_overlap': False,
                      'vm_anonymous_controls': 4, 'kernel_mapping_destruction_proved': False,
                      'port_registry_identity_proved': False, 'hardware_video_execution_proved': False,
                      'explicit_unmap_calls': 0, 'explicit_video_selector_calls': 0,
                      'executable_SHA256': rows[0][3]['original_binary_sha256'],
                      'scope': 'process-local VM coverage and registry correlation only; driver-internal work not traced'}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
