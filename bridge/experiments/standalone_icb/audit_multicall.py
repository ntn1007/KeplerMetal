#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit serialized standalone concurrent-device captures, without GPU work."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def require(test, message):
    if not test: raise ValueError(message)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--multicall', nargs='+', required=True, type=Path)
    p.add_argument('--original', required=True, type=Path)
    p.add_argument('--library', required=True, type=Path)
    a = p.parse_args(); paths = [x.resolve() for x in a.multicall] + [a.original.resolve()]
    require(len(set(paths)) == len(paths), 'Evidence directories repeat')
    manifest = read(a.library/'manifest.json')
    require(manifest['status'] == 'PASS' and sha(a.library/'libKeplerMetal.a') == manifest['static_library_SHA256'], 'Runtime differs')
    for name, digest in manifest['source_SHA256'].items():
        require(sha(a.library/'src'/name)==sha(ROOT/'src'/name)==digest, 'Runtime source differs: '+name)
    rows = []; intervals = []; images = []
    for i,path in enumerate(paths):
        inputs = read(path/'inputs.json'); host = read(path/'execution/manifest.json')
        require(inputs['static_library_SHA256'] == manifest['static_library_SHA256'], 'Runtime archive differs')
        require(inputs['frozen']['src/bootstrap.mm'] == sha(HERE/'bootstrap.mm'), 'Bootstrap source differs')
        require(inputs['frozen']['src/verify.py'] == sha(HERE/'verify.py'), 'Standalone oracle differs')
        client = 'multicall_client.mm' if i < len(a.multicall) else 'client.mm'
        require(inputs['frozen']['src/'+client] == sha(HERE/client), 'Client source differs')
        script = HERE/('verify_multicall.py' if i < len(a.multicall) else 'verify.py')
        require(inputs['frozen']['src/'+script.name] == sha(script), 'Verifier differs')
        result = subprocess.run([sys.executable, '-I', str(script), str(path)], capture_output=True, text=True, timeout=60)
        require(result.returncode == 0, 'Oracle failed: '+result.stderr)
        row = json.loads(result.stdout); rows.append(row)
        intervals.append((datetime.fromisoformat(host['started_at']), datetime.fromisoformat(host['completed_at'])))
        if row['mode'] in ('direct','auto'): images.append(sha(path/'outputs/frame-0.bin'))
    intervals.sort()
    require(all(a<=b for a,b in intervals) and all(a[1]<=b[0] for a,b in zip(intervals, intervals[1:])), 'Process intervals overlap')
    require(Counter(r['mode'] for r in rows[:-1]) == Counter({'direct':1,'auto':3,'auto-native':1,'wrong-library':1,'wrong-client':1}), 'Mode coverage differs')
    require(all(r['total_device_calls']==(8 if r['mode']=='wrong-client' else 9) for r in rows[:-1]), 'Device call counts differ')
    require(rows[-1]['mode'] == 'auto', 'Original-client regression differs')
    require(len(images)==5 and len(set(images))==1, 'Images differ')
    print(json.dumps({'status':'PASS','hosts':len(rows),'concurrent_calls_per_multicall_host':8,
        'subsequent_call_on_approved_client':1,'wrong_client_calls_before_refusal':8,'successful_multicall_render_hosts':4,
        'original_client_regression_hosts':1,'matching_RGBA32F_channels':5*64*48*4,
        'negative_controls':['native-ICB-missing','unapproved-library','unapproved-client'],
        'bootstrap_source_SHA256':sha(HERE/'bootstrap.mm'),'runtime_archive_SHA256':manifest['static_library_SHA256'],
        'nonoverlapping':True,'scope':'one pinned client per build and one qualified library; no transparent system integration'},indent=2,sort_keys=True))

if __name__ == '__main__': main()
