#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck saved variable-resource and same-runtime regression evidence."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from verify_partial_variable_resources import verify as verify_stencil
from verify_partial_variable_barrier import verify as verify_barrier
from verify_partial_general_api import verify as verify_fixed
from verify_uniform_icb_3d import verify as verify_uniform

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('stencil', 'barrier', 'fixed', 'uniform'):
        p.add_argument('--' + name, type=Path, nargs='+', required=True)
    a = p.parse_args()
    paths = a.stencil + a.barrier + a.fixed + a.uniform
    if len({p.resolve() for p in paths}) != len(paths):
        raise ValueError('Evidence directories must be distinct')
    checks = []
    for group, dirs, fn in [('stencil', a.stencil, verify_stencil),
                            ('barrier', a.barrier, verify_barrier),
                            ('fixed', a.fixed, verify_fixed),
                            ('uniform', a.uniform, verify_uniform)]:
        for directory in dirs:
            inp = json.loads((directory / 'inputs.json').read_text())
            for name in ('KeplerCPUICB.mm', 'KeplerPartialGridPlan.h'):
                if inp['frozen']['src/' + name] != sha(ROOT / 'src' / name):
                    raise ValueError('Runtime source differs from tested snapshot: ' + name)
            verifier = {'stencil': 'verify_partial_variable_resources.py',
                        'barrier': 'verify_partial_variable_barrier.py',
                        'fixed': 'verify_partial_general_api.py',
                        'uniform': 'verify_uniform_icb_3d.py'}[group]
            if inp['frozen']['src/' + verifier] != sha(ROOT / 'tools' / verifier):
                raise ValueError('Verifier differs from tested snapshot: ' + verifier)
            checks.append((group, directory, inp, fn(directory)))
    archives = {row[2]['runtime_archive_SHA256'] for row in checks}
    if len(archives) != 1:
        raise ValueError('Cohorts used different runtime archives')
    intervals = []
    for _, directory, _, _ in checks:
        manifest = json.loads((directory / 'execution/manifest.json').read_text())
        intervals.append((datetime.fromisoformat(manifest['started_at']),
                          datetime.fromisoformat(manifest['completed_at'])))
    intervals.sort()
    if any(start > end for start, end in intervals) or any(
            previous[1] > current[0] for previous, current in zip(intervals, intervals[1:])):
        raise ValueError('Host intervals overlap or have invalid timestamps')
    for group, wanted in [('stencil', Counter({0: 1, 1: 2, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2, 7: 1})),
                          ('barrier', Counter({0: 2, 1: 1, 6: 1, 7: 1})),
                          ('fixed', Counter({0: 1, 6: 1}))]:
        rows = [r[3] for r in checks if r[0] == group]
        if Counter(r['case'] for r in rows if r['mode'] == 'execute') != wanted:
            raise ValueError(group + ' case coverage differs')
        if sum(r['mode'] == 'prepare' for r in rows) != (0 if group == 'fixed' else 1):
            raise ValueError(group + ' prepare count differs')
    if {r[3]['form'] for r in checks if r[0] == 'uniform'} != {'groups', 'threads'}:
        raise ValueError('Both uniform execution forms required')
    if len([r for r in checks if r[0] == 'uniform']) != 2:
        raise ValueError('Exactly two uniform controls required')
    summary = {'status': 'PASS', 'runtime_archive_SHA256': next(iter(archives)),
               'host_processes': len(checks), 'cohort_host_intervals_overlap': False,
               'stencil_threads': sum(r[3]['threads'] for r in checks if r[0] == 'stencil'),
               'barrier_threads': sum(r[3]['threads'] for r in checks if r[0] == 'barrier'),
               'fixed_barrier_threads': sum(r[3]['threads'] for r in checks if r[0] == 'fixed'),
               'uniform_threads': sum(r[3]['GPU_invocations_counted'] for r in checks if r[0] == 'uniform'),
               'negative_control_observations': sum(r[3].get('negative_cases', 0) for r in checks),
               'source_SHA256': {n: sha(ROOT / 'src' / n) for n in ('KeplerCPUICB.mm', 'KeplerPartialGridPlan.h')},
               'scope': 'Bounded opt-in project ICB, not native Apple ICB or system-wide support'}
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
