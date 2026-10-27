#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck dependent partial/uniform ranges and same-runtime regressions."""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from verify_partial_range_chain import verify as verify_chain
from verify_partial_chain_barrier import verify as verify_barrier
from verify_uniform_icb_3d import verify as verify_uniform

ROOT = Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('chain', 'barrier', 'uniform'):
        p.add_argument('--' + name, type=Path, nargs='+', required=True)
    p.add_argument('--current-source-build', type=Path, required=True)
    a = p.parse_args();paths = a.chain + a.barrier + a.uniform
    if len({x.resolve() for x in paths}) != len(paths):raise ValueError('Evidence directories must be distinct')
    rows = []
    for group, dirs, fn, script in [('chain', a.chain, verify_chain, 'verify_partial_range_chain.py'),
                                    ('barrier', a.barrier, verify_barrier, 'verify_partial_chain_barrier.py'),
                                    ('uniform', a.uniform, verify_uniform, 'verify_uniform_icb_3d.py')]:
        for directory in dirs:
            inp = json.loads((directory / 'inputs.json').read_text())
            for name in ('KeplerCPUICB.mm', 'KeplerPartialGridPlan.h'):
                if inp['frozen']['src/' + name] != sha(ROOT / 'src' / name):raise ValueError('Tested runtime source differs: ' + name)
            if inp['frozen']['src/' + script] != sha(ROOT / 'tools' / script):raise ValueError('Tested verifier differs: ' + script)
            rows.append((group, directory, inp, fn(directory)))
    archives = {r[2]['runtime_archive_SHA256'] for r in rows}
    if len(archives) != 1:raise ValueError('Cohorts used different runtime archives')
    # The public header was clarified after this cohort. Require a fresh build
    # from the final source and compare every archived object byte-for-byte;
    # archive container hashes themselves can differ.
    tested = json.loads((a.chain[0]/'archive-manifest.json').read_text())
    fresh = json.loads((a.current_source_build/'manifest.json').read_text())
    if fresh['status']!='PASS' or len(tested['object_SHA256'])!=7 or tested['object_SHA256']!=fresh['object_SHA256'] or set(tested['source_SHA256'])!=set(fresh['source_SHA256']):raise ValueError('Fresh object hashes or source inventory differ from tested archive')
    source_changes=[k for k in fresh['source_SHA256'] if fresh['source_SHA256'][k]!=tested['source_SHA256'].get(k)]
    if source_changes not in ([],['KeplerCPUICB.h']):raise ValueError('Unexpected source changes after qualification')
    old_header=(a.chain[0]/'src/KeplerCPUICB.h').read_text();new_header=(a.current_source_build/'src/KeplerCPUICB.h').read_text()
    old_comment='// Explicit experimental fixed-profile partial-grid adapter. Only the exact\n// registered partial_builtin_barrier shader, grid volume <=1024, local volume\n// <=128 and at most 16 bounded regions are accepted. Unsupported shaders,\n// layouts, mixed ranges and copies are refused.\n'
    new_comment='// Explicit experimental partial-grid adapter: only two exact registered shaders,\n// grid volume <=1024, local volume <=128 and <=16 resident launches per serial\n// range. Eligible uniform and partial slots may be mixed; unsupported shaders,\n// layouts, GPU-selected commands and copies are refused.\n'
    if source_changes and (old_header.count(old_comment)!=1 or old_header.replace(old_comment,new_comment)!=new_header):raise ValueError('Header change is not the expected comment-only edit')
    if not source_changes and old_header!=new_header:raise ValueError('Header differs without a source hash change')
    for name,digest in fresh['source_SHA256'].items():
        if sha(ROOT/'src'/name)!=digest or sha(a.current_source_build/'src'/name)!=digest:raise ValueError('Fresh source snapshot differs: '+name)
    tested_archive=a.chain[0]/'runtime_archive.a';fresh_archive=a.current_source_build/'libKeplerMetal.a'
    if sha(tested_archive)!=tested['static_library_SHA256'] or sha(fresh_archive)!=fresh['static_library_SHA256']:raise ValueError('Archive hash differs')
    for name,digest in tested['object_SHA256'].items():
        for archive in (tested_archive,fresh_archive):
            obj=subprocess.run(['xcrun','ar','-p',str(archive),name],capture_output=True,check=True).stdout
            if hashlib.sha256(obj).hexdigest()!=digest:raise ValueError('Archive member differs: '+name)
    chain = [r[3] for r in rows if r[0]=='chain']
    scenarios={'partial_partial':1,'partial_uniform':1,'uniform_partial':1,'partial_partial_3d_limit':1}
    if Counter(r['scenario'] for r in chain if r['mode']=='prepare') != Counter(scenarios):raise ValueError('Preparation coverage differs')
    if Counter(r['scenario'] for r in chain if r['mode']=='execute') != Counter({key:2 for key in scenarios}):raise ValueError('Execution/repeat coverage differs')
    barrier = [r[3] for r in rows if r[0]=='barrier']
    if Counter(r['case'] for r in barrier if r['mode']=='execute') != Counter({0:1,6:1}):raise ValueError('Barrier regression differs')
    uniform = [r[3] for r in rows if r[0]=='uniform']
    if len(uniform)!=2 or {r['form'] for r in uniform}!={'groups','threads'}:raise ValueError('Uniform regression differs')
    intervals=[]
    for _,directory,_,_ in rows:
        m=json.loads((directory/'execution/manifest.json').read_text());intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
    intervals.sort()
    if any(a>b for a,b in intervals) or any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):raise ValueError('Host intervals overlap or are invalid')
    print(json.dumps({'status':'PASS','host_processes':len(rows),'cohort_host_intervals_overlap':False,
      'runtime_archive_SHA256':next(iter(archives)), 'fresh_archive_SHA256':fresh['static_library_SHA256'],
      'all_seven_archive_members_identical':True, 'post_test_source_change':'KeplerCPUICB.h comments only' if source_changes else 'none',
      'chain_logical_dispatches':sum(r['logical_dispatches'] for r in chain),
      'chain_invocations':sum(r['invocations'] for r in chain),
      'chain_checked_output_words':sum(r['checked_output_words'] for r in chain),
      'order_control_observations':sum(r['order_controls'] for r in chain),
      'chain_preflight_refusal_observations':sum(r['negative_preflight_controls'] for r in chain),
      'barrier_regression_invocations':sum(r['threads'] for r in barrier),
      'uniform_regression_invocations':sum(r['GPU_invocations_counted'] for r in uniform),
      'source_SHA256':{n:sha(ROOT/'src'/n) for n in ('KeplerCPUICB.mm','KeplerPartialGridPlan.h')},
      'scope':'Bounded adapted-process project ICB, not native Apple ICB or system-wide support'},indent=2,sort_keys=True))


if __name__ == '__main__':main()
