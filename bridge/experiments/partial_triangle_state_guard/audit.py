#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify state-guard receipts and raw rendered pixels without GPU work."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','archive','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=2,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==2,'fresh output and distinct runs')
    build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json')
    need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==sha(archive/'libKeplerMetal.a')==ar['static_library_SHA256'] and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'archive provenance')
    for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source: '+n)
    for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build: '+n)
    need(sha(build/'client.mm')==sha(HERE/'client.mm'),'client source differs')
    need(subprocess.run(['codesign','--verify','--strict',str(build/'application')],capture_output=True).returncode==0,'signature differs')
    refused=('pipeline','binding','indexed_pipeline');successful=('unchanged','restore','copy','complete');rows=[];intervals=[];allhashes=[]
    for root in a.runs:
        root=root.resolve();m=load(root/'manifest.json');out=load(root/'stdout.json');lease=m['reservation']
        need(m['status']=='TERMINAL' and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['runner_sha256']==sha(HERE/'experiment.py') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'],'run provenance')
        need(m['args']==[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(root/'outputs')],'arguments differ')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'terminal reservation')
        need(m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log') and m['system_before']==m['system_after']==SYSTEM,'log or system profile')
        need(subprocess.run(['codesign','--verify','--strict',str(root/'application')],capture_output=True).returncode==0,'host signature')
        need(out['status']=='PASS' and out['device']=='NVIDIA GeForce GTX 880M' and out['registry_id'] and [x['case'] for x in out['cases']]==list(refused+successful),'client output')
        for row in out['cases']:
            expected=row['case'] in refused;need(row['refused']==expected and row['submitted']==(not expected),'refusal/submit differs')
            if not expected:need(row['checked_channels']==12288 and row['guard_bytes']==512,'checked shape')
        need({p.name for p in (root/'outputs').iterdir()}=={n+'.bin' for n in successful},'capture set')
        hashes={}
        for name in successful:
            path=root/'outputs'/f'{name}.bin';data=path.read_bytes();need(len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256,'guards');values=struct.unpack('<12288f',data[256:-256]);color=(.75,.125,.25,1.)
            need(all(v==(color[i%4] if name=='complete' else 0.0) for i,v in enumerate(values)),'pixel oracle: '+name);hashes[name]=sha(path)
        intervals.append((m['started_at'],m['completed_at']));allhashes.append(hashes);rows.append({'manifest_sha256':sha(root/'manifest.json'),'stdout_sha256':sha(root/'stdout.json'),'images_sha256':hashes})
    need(allhashes[0]==allhashes[1],'repetition differs');intervals.sort();need(all(start<=end for start,end in intervals) and intervals[0][1]<=intervals[1][0],'run intervals overlap')
    result={'status':'PASS_PARTIAL_STATE_GUARD','runtime_archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'runs':rows,'terminal_nonoverlapping_processes':2,'refusals':6,'unsubmitted_refusal_buffers':6,'completed_render_buffers':8,'checked_float_channels':98304,'guard_bytes':4096,'ordinary_complete_draws':2,'incomplete_draws_gpu_submitted':False,'untracked_application_or_shader_scope_qualified':False,'system_modified':False,'performance_benchmark':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'refusals':6,'completed_render_buffers':8}))
if __name__=='__main__':main()
