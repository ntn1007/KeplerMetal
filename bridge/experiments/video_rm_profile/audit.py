#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck a signed no-open RM profile cohort; never issue an RM request."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

SOURCE = '7fe7d79e565e3d0feebdeea8768afe24629fe6e46744b66c136f1f71b076aff2'
BINARY = '79333dc780a27e0a21433041701552d6aa2db57d9c9c2c472535ae0b2fbbdd28'
RUNNER = '9dfb0f8ff0361d8adddf73382520e801cca7c5ab308a25e21e7b4d84c9260cc9'
LEASE = 'ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(ok, reason):
    if not ok: raise ValueError(reason)

def audit(source, original, rebuild, runs):
    need(digest(source) == SOURCE and digest(rebuild / 'profile_probe.mm') == SOURCE, 'source pin')
    need(digest(original / 'profile-probe') == BINARY and
         digest(rebuild / 'profile-probe') == BINARY, 'two independently built binaries')
    names = [('wrong-code-hash', '4294968425', 'PROFILE_REFUSED'),
             ('observe', '1', 'PROFILE_REFUSED'),
             ('observe', '4294968425', 'PROFILE_OBSERVED_NO_OPEN'),
             ('observe', '4294968425', 'PROFILE_OBSERVED_NO_OPEN')]
    need(len(runs) == len(names), 'four ordered hosts')
    receipts = []
    for folder, (mode, rid, status) in zip(runs, names):
        m = json.loads((folder / 'manifest.json').read_text())
        raw = (folder / 'execution.stdout').read_bytes(); result = json.loads(raw)
        exe = folder / 'application'
        need(not (folder / 'execution.stderr').read_bytes(), 'empty stderr')
        need(m['arguments'] == [mode, rid] and m['original_binary_sha256'] == BINARY and
             Path(m['signed_executable']).resolve() == exe.resolve() and
             digest(exe) == m['signed_binary_sha256'], 'signed host identity')
        subprocess.run(['codesign', '--verify', '--strict', str(exe)], check=True,
                       capture_output=True, timeout=15)
        lease = m['GPU_reservation']
        need(m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and
             lease['state'] == 'terminal' and lease['lock_inherited_by_child'] and
             lease['bootstrap_process_table_checked'] and not lease['known_signed_processes_live'] and
             m['launcher_SHA256'] == RUNNER and m['reservation_module_SHA256'] == LEASE,
             'terminal cooperative reservation')
        need(result['status'] == status and result['mode'] == mode and result['pid'] == m['pid'] and
             result['uid'] == result['euid'] == 501 and result['files_checked'] == 5 and
             result['open_attempts'] == result['RM_calls'] == result['GPU_dispatches'] == 0,
             'result scope')
        if mode == 'wrong-code-hash':
            need(not result['registry_enumerated'] and result['resident_regions_checked'] == 0,
                 'bad hash refused before enumeration')
        else:
            need(result['registry_enumerated'] and result['resident_regions_checked'] == 3 and
                 result['matching_NVDA_services'] == 4 and not result['truncated'], 'registry path')
            need(result['selected_NVDA_services'] == (rid != '1'), 'unique selected service')
            if rid != '1':
                need(result['registry_id'] == int(rid) and result['parent_name'] == 'NVDA,Display-A',
                     'selected service identity')
        receipts.append({'mode': mode, 'status': status, 'pid': m['pid'],
                         'started_at': m['started_at'], 'completed_at': m['completed_at'],
                         'signed_sha256': m['signed_binary_sha256'],
                         'stdout_sha256': hashlib.sha256(raw).hexdigest(),
                         'manifest_sha256': digest(folder / 'manifest.json')})
    need(all(a['completed_at'] < b['started_at'] for a, b in zip(receipts, receipts[1:])),
         'nonoverlapping hosts')
    return {'status': 'PASS_CURRENT_PROFILE_NO_OPEN', 'source_sha256': SOURCE,
            'binary_sha256': BINARY, 'runner_sha256': RUNNER, 'lease_sha256': LEASE,
            'host_count': len(receipts), 'hosts': receipts, 'matching_services': 4,
            'selected_parent': 'NVDA,Display-A', 'private_RM_calls': 0, 'GPU_dispatches': 0,
            'scope': 'Own-process IOKit code and on-disk hashes only. This does not repin or qualify the privileged RM witness or prove loaded kernel code.'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--original-build', type=Path, required=True)
    p.add_argument('--rebuild', type=Path, required=True)
    p.add_argument('--runs', nargs=4, type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output')
    result = audit(a.source, a.original_build, a.rebuild, a.runs)
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__': main()
