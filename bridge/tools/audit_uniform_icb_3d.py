#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare 3D group/thread outputs and independently decoded native geometry."""
import argparse,datetime,json,subprocess
from pathlib import Path
from verify_uniform_icb_3d import verify,sha

def read(p):return json.loads(Path(p).read_text())
def comparable(v):return {k:h for k,h in v['raw_SHA256'].items() if not k.endswith('.commands.bin')}
def audit(paths):
    paths=[Path(x).resolve() for x in paths];expected=[('prepare','groups'),('prepare','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads')]
    if len(paths)!=len(expected) or len(set(paths))!=len(expected):raise ValueError('Eight distinct result directories required')
    items=[]
    for p,(mode,form) in zip(paths,expected):
        v=verify(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json')
        if (v['mode'],v['form'])!=(mode,form) or read(p/'verification-execution.json')['exit_code']!=0 or v!=read(p/'verification.stdout'):raise ValueError('Wrong mode or independent oracle differs')
        subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15);items.append((p,v,i,m))
    if len({(x[2]['build_inputs_SHA256'],x[2]['runtime_archive_SHA256'],x[2]['library_SHA256'],x[2]['manifest_SHA256']) for x in items})!=1:raise ValueError('Different builds or shader profiles')
    if len({x[3]['pid'] for x in items})!=len(items):raise ValueError('Processes must be distinct')
    if len({x[1]['gpu_registry_id'] for x in items})!=1:raise ValueError('Different target GPU')
    if any(datetime.datetime.fromisoformat(a[3]['completed_at'])>=datetime.datetime.fromisoformat(b[3]['started_at']) for a,b in zip(items,items[1:])):raise ValueError('Runs overlapped or out of order')
    if len(comparable(items[0][1]))!=36 or comparable(items[0][1])!=comparable(items[1][1]):raise ValueError('Preparation controls differ')
    for a,b in ((2,3),(4,5),(6,7)):
        if len(comparable(items[a][1]))!=180 or comparable(items[a][1])!=comparable(items[b][1]):raise ValueError('Group/thread output captures differ')
    rows=[{'mode':v['mode'],'form':v['form'],'GPU_user_submissions':v['GPU_user_submissions'],'GPU_invocations_counted':v['GPU_invocations_counted'],
           'correct_uint32_words':v['correct_uint32_words'],'dimension_rejection_controls':v['dimension_rejection_controls'],
           'raw_files_verified':v['raw_files_verified'],'result_SHA256':sha(p/'results.json'),'manifest_SHA256':sha(p/'execution/manifest.json')}
          for p,v,i,m in items]
    return {'audit':'PASS','separate_processes':len(items),'preparation_hosts':2,'user_GPU_execute_hosts':6,
            'user_command_buffers':sum(x[1]['GPU_user_submissions'] for x in items),'positive_uint32_words':sum(x[1]['correct_uint32_words'] for x in items),
            'user_GPU_invocations':sum(x[1]['GPU_invocations_counted'] for x in items),'negative_api_cases':sum(x[1]['dimension_rejection_controls'] for x in items),
            'paired_data_files_identical':sum(len(comparable(items[j][1])) for j in (2,4,6)),
            'native_command_stream_files_verified':sum(x[1]['GPU_user_submissions'] if x[1]['mode']=='execute' else 1 for x in items),
            'nonempty_native_streams_decoded_not_compared':sum(6 if x[1]['mode']=='execute' else 1 for x in items),
            'build_inputs_SHA256':items[0][2]['build_inputs_SHA256'],'runtime_archive_SHA256':items[0][2]['runtime_archive_SHA256'],
            'library_SHA256':items[0][2]['library_SHA256'],'manifest_SHA256':items[0][2]['manifest_SHA256'],
            'GPU_execution_proved':True,'partial_threadgroups_supported':False,'transparent_application_integration':False,'system_modified':False,'observations':rows}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results',nargs=8);a=p.parse_args();print(json.dumps(audit(a.results),indent=2,sort_keys=True))
