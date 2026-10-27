#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck CPU readbacks from a negative and three native/post-purge pairs."""
import argparse, datetime, json, subprocess
from pathlib import Path
from verify_video_metal_purge_gpu import read, sha, verify

def audit(paths):
    paths=[Path(x).resolve() for x in paths];modes=['negative','native','purge','native','purge','native','purge']
    if len(paths)!=len(modes) or len(set(paths))!=len(modes):raise ValueError('Seven distinct result directories required')
    items=[]
    for p,mode in zip(paths,modes):
        v=verify(p);i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json')
        if v['mode']!=mode or read(p/'verification-execution.json')['exit_code']!=0 or v!=read(p/'verification.stdout'):raise ValueError('Wrong mode or independent oracle differs')
        subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
        items.append((p,v,i,r,m))
    if len({x[2]['build_inputs_SHA256'] for x in items})!=1 or len({x[2]['metallib_SHA256'] for x in items})!=1:raise ValueError('Different builds')
    if len({x[4]['pid'] for x in items})!=len(items):raise ValueError('Processes must be distinct')
    if len({(x[1]['gpu_registry_id'],x[1]['pci_registry_id']) for x in items})!=1:raise ValueError('Different target GPU')
    if any(datetime.datetime.fromisoformat(a[4]['completed_at']) >= datetime.datetime.fromisoformat(b[4]['started_at']) for a,b in zip(items,items[1:])):raise ValueError('Runs overlapped or out of order')
    positive=items[1:]
    if len({(x[1]['target_SHA256'],x[1]['output_SHA256']) for x in positive})!=1:raise ValueError('GPU captures disagree')
    rows=[{'mode':v['mode'],'outcome':v['outcome'],'cpu_words_compared':v['cpu_words_compared'],'guard_bytes_compared':v['guard_bytes_compared'],
           'negative_gpu_read_mismatches':v['negative_gpu_read_mismatches'],'negative_gpu_write_mismatches':v['negative_gpu_write_mismatches'],
           'target_SHA256':v['target_SHA256'],'output_SHA256':v['output_SHA256'],'result_SHA256':sha(p/'results.json'),'manifest_SHA256':sha(p/'execution/manifest.json')}
          for p,v,i,r,m in items]
    return {'audit':'PASS','separate_processes':len(items),'native_GPU_trials':sum(x[1]['mode']=='native' for x in items),
            'post_purge_GPU_trials':sum(x[1]['mode']=='purge' for x in items),'negative_no_dispatch_trials':1,
            'positive_cpu_words_compared':sum(x[1]['cpu_words_compared'] for x in positive),'negative_cpu_words_compared':items[0][1]['cpu_words_compared'],
            'guard_bytes_compared':sum(x[1]['guard_bytes_compared'] for x in items),'build_inputs_SHA256':items[0][2]['build_inputs_SHA256'],
            'metallib_SHA256':items[0][2]['metallib_SHA256'],'GPU_execution_proved':True,'physical_memory_reclaimed_proved':False,
            'resource_id_correlation_proved':False,'video_execution_proved':False,'observations':rows}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results',nargs=7);a=p.parse_args();print(json.dumps(audit(a.results),indent=2,sort_keys=True))
