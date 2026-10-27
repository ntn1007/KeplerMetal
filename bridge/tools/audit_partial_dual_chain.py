#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the bounded two-pipeline cohort and regressions from raw evidence."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from verify_partial_dual_chain import verify as dual_verify, MANIFEST
from verify_partial_range_chain import verify as chain_verify
from verify_partial_chain_barrier import verify as barrier_verify
from verify_uniform_icb_3d import verify as uniform_verify

ROOT = Path(__file__).resolve().parents[1]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def require(condition, why):
    if not condition: raise ValueError(why)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for group in ('dual', 'chain', 'barrier', 'uniform'):
        p.add_argument('--' + group, type=Path, nargs='+', required=True)
    p.add_argument('--current-source-build', type=Path, required=True)
    args = p.parse_args()
    groups = [('dual', args.dual, dual_verify, 'verify_partial_dual_chain.py'),
              ('chain', args.chain, chain_verify, 'verify_partial_range_chain.py'),
              ('barrier', args.barrier, barrier_verify, 'verify_partial_chain_barrier.py'),
              ('uniform', args.uniform, uniform_verify, 'verify_uniform_icb_3d.py')]
    paths = [path.resolve() for _, paths, _, _ in groups for path in paths]
    require(len(paths) == len(set(paths)), 'Evidence directories repeat')
    fresh = read(args.current_source_build / 'manifest.json')
    require(fresh['status'] == 'PASS', 'Source build failed')
    for name, digest in fresh['source_SHA256'].items():
        require(sha(ROOT/'src'/name) == sha(args.current_source_build/'src'/name) == digest, 'Runtime source differs: ' + name)
    require(sha(args.current_source_build/'libKeplerMetal.a') == fresh['static_library_SHA256'], 'Runtime archive differs')
    rows = []; intervals = []
    for group, paths, verify, script in groups:
        for path in paths:
            inp = read(path/'inputs.json'); captured = read(path/'archive-manifest.json')
            require(inp['runtime_archive_SHA256'] == captured['static_library_SHA256'] == fresh['static_library_SHA256'], 'Runtime differs')
            require(captured['source_SHA256'] == fresh['source_SHA256'], 'Tested source differs')
            require(inp['frozen']['src/'+script] == sha(ROOT/'tools'/script), 'Oracle differs')
            row = verify(path); rows.append((group, row))
            m = read(path/'execution/manifest.json')
            intervals.append((datetime.fromisoformat(m['started_at']), datetime.fromisoformat(m['completed_at'])))
            if group == 'dual':
                for trial in read(path/'results.json')['runs']:
                    e = trial['event']
                    if e.get('operation') == 'execute_bounded_partial_range':
                        owners = e['evidence']['owner_original_profiles']
                        require(len({o['registration_id'] for o in owners}) == 1 and all(o['registration_id'] and o['manifest_SHA256'] == MANIFEST for o in owners), 'Pipelines do not share exact registration')
    intervals.sort()
    require(all(a <= b for a,b in intervals) and all(a[1] <= b[0] for a,b in zip(intervals, intervals[1:])), 'GPU host intervals overlap')
    dual = [r for g,r in rows if g == 'dual']; scenarios = ['partial_partial','partial_uniform','uniform_partial','partial_partial_3d_limit']
    require(Counter(r['scenario'] for r in dual if r['mode']=='prepare') == Counter({x:1 for x in scenarios}), 'Preparation coverage differs')
    require(Counter(r['scenario'] for r in dual if r['mode']=='execute') == Counter({x:2 for x in scenarios}), 'Execution coverage differs')
    chain = [r for g,r in rows if g=='chain']
    require(Counter(r['scenario'] for r in chain if r['mode']=='execute') == Counter({'partial_partial':1,'partial_partial_3d_limit':1}), 'Prior chain regression differs')
    barrier = [r for g,r in rows if g=='barrier']
    require(Counter(r['case'] for r in barrier if r['mode']=='execute') == Counter({0:1,6:1}), 'Barrier regression differs')
    uniform = [r for g,r in rows if g=='uniform']
    require(len(uniform)==2 and {r['form'] for r in uniform} == {'groups','threads'}, 'Uniform regression differs')
    print(json.dumps({'status':'PASS','host_processes':len(rows),'cohort_host_intervals_overlap':False,
        'runtime_archive_SHA256':fresh['static_library_SHA256'], 'runtime_source_SHA256':fresh['source_SHA256']['KeplerCPUICB.mm'],
        'dual_logical_dispatches':sum(r['logical_dispatches'] for r in dual),'dual_invocations':sum(r['invocations'] for r in dual),
        'dual_order_controls':sum(r['order_controls'] for r in dual),'dual_preflight_refusals':sum(r['negative_preflight_controls'] for r in dual),
        'old_chain_invocations':sum(r['invocations'] for r in chain),'barrier_regression_invocations':sum(r['threads'] for r in barrier),
        'uniform_regression_invocations':sum(r['GPU_invocations_counted'] for r in uniform),
        'scope':'Adapted process only; no native Apple ICB or system-wide integration'}, indent=2, sort_keys=True))

if __name__ == '__main__': main()
