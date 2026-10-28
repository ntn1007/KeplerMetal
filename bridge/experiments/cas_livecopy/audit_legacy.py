#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-audit four previous-SDK regressions against the rebuilt module."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--runs',nargs=4,type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build=args.build.resolve();out=args.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    inputs=json.loads((build/'inputs.json').read_text())
    for name,digest in inputs['frozen'].items():need(sha(build/name)==digest,'frozen input differs: '+name)
    current=Path(__file__).resolve().parents[2]/'src/KeplerNativeCASAdapter.inc'
    need(sha(build/'sdk/src/KeplerNativeCASAdapter.inc')==sha(current),'tested adapter differs')
    sys.path.insert(0,str(build/'support'))
    from verify_native_cas_sdk import verify
    modes=('negative','prepare','native','execute');summaries=[];intervals=[]
    for mode,path in zip(modes,args.runs):
        path=path.resolve();m=json.loads((path/'execution/manifest.json').read_text())
        need(m['GPU_reservation']['state']=='terminal' and not m['SIGKILL_requested'] and
             not m['authoritative_ps_status'] and m['exit_code']==0, 'nonterminal host: '+mode)
        intervals.append((m['started_at'],m['completed_at']))
        summary=verify(path);need(summary['status']=='PASS' and summary['mode']==mode,'oracle failed: '+mode)
        summaries.append({k:v for k,v in summary.items() if k!='records'})
    intervals.sort();need(all(start<=end for start,end in intervals) and
        all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)), 'overlapping hosts')
    report={'status':'PASS','adapter_SHA256':sha(current),'client_SHA256':inputs['executable_SHA256'],
            'asset_library_SHA256':sha(build/'sdk/assets/cas_client.metallib'),
            'terminal_nonoverlapping_processes':len(intervals),'modes':summaries,
            'GPU_general_support':False,'performance_benchmark':False}
    with out.open('x') as stream:json.dump(report,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
