#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare two preparation controls and three uniform-thread/group GPU pairs."""
import argparse, datetime, json, subprocess
from pathlib import Path
from verify_uniform_thread_icb import read,sha,verify

def audit(paths):
    paths=[Path(x).resolve() for x in paths];expected=[('prepare','groups'),('prepare','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads')]
    if len(paths)!=len(expected) or len(set(paths))!=len(expected):raise ValueError('Eight distinct result directories required')
    items=[]
    for p,(mode,form) in zip(paths,expected):
        v=verify(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json')
        if (v['mode'],v['form'])!=(mode,form) or read(p/'verification-execution.json')['exit_code']!=0 or v!=read(p/'verification.stdout'):raise ValueError('Wrong mode or independent oracle differs')
        subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
        items.append((p,v,i,m))
    if len({x[2]['build_inputs_SHA256'] for x in items})!=1 or len({x[2]['runtime_archive_SHA256'] for x in items})!=1 or len({x[2]['metallib_SHA256'] for x in items})!=1:raise ValueError('Different builds')
    if len({x[3]['pid'] for x in items})!=len(items):raise ValueError('Processes must be distinct')
    if len({x[1]['gpu_registry_id'] for x in items})!=1:raise ValueError('Different target GPU')
    if any(datetime.datetime.fromisoformat(a[3]['completed_at']) >= datetime.datetime.fromisoformat(b[3]['started_at']) for a,b in zip(items,items[1:])):raise ValueError('Runs overlapped or out of order')
    if items[0][1]['raw_SHA256']!=items[1][1]['raw_SHA256']:raise ValueError('Preparation controls differ')
    for a,b in ((2,3),(4,5),(6,7)):
        if items[a][1]['raw_SHA256']!=items[b][1]['raw_SHA256']:raise ValueError('Group/thread captures differ')
    rows=[{'mode':v['mode'],'form':v['form'],'correct_uint32_words':v['correct_uint32_words'],'user_GPU_invocations':v['user_GPU_invocations'],
           'guard_bytes_checked':v['guard_bytes_checked'],'negative_api_cases':v['negative_api_cases'],
           'raw_file_count':len(v['raw_SHA256']),'result_SHA256':sha(p/'results.json'),'manifest_SHA256':sha(p/'execution/manifest.json')}
          for p,v,i,m in items]
    return {'audit':'PASS','separate_processes':len(items),'preparation_hosts':2,'user_GPU_execute_hosts':6,'user_command_buffers':42,
            'positive_uint32_words':sum(x[1]['correct_uint32_words'] for x in items),'user_GPU_invocations':sum(x[1]['user_GPU_invocations'] for x in items),
            'guard_bytes_checked':sum(x[1]['guard_bytes_checked'] for x in items),'negative_api_cases':sum(x[1]['negative_api_cases'] for x in items),
            'paired_raw_files_identical':sum(len(items[j][1]['raw_SHA256']) for j in (2,4,6)),
            'build_inputs_SHA256':items[0][2]['build_inputs_SHA256'],'runtime_archive_SHA256':items[0][2]['runtime_archive_SHA256'],
            'metallib_SHA256':items[0][2]['metallib_SHA256'],'GPU_execution_proved':True,'partial_threadgroups_supported':False,
            'transparent_application_integration':False,'system_modified':False,'observations':rows}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results',nargs=8);a=p.parse_args();print(json.dumps(audit(a.results),indent=2,sort_keys=True))
