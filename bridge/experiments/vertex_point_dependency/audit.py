#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit tracked-buffer render-to-compute captures and process receipts."""
import argparse,base64,hashlib,json,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def packet(x,n):
    raw=base64.b64decode(x,validate=True);need(len(raw)==24 and struct.unpack('<6I',raw)==(0xa0050e0c,0,n,1,0,0),'packet differs');return raw

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=4,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==4,'fresh output / distinct runs')
    build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build differs')
    for name,h in ar['source_SHA256'].items():need(sha(archive/'src'/name)==sha(BRIDGE/'src'/name)==h,'source differs '+name)
    for name,h in b['files_sha256'].items():need(sha(build/name)==h,'build input differs '+name)
    need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'profiles.json')==sha(BRIDGE/'experiments/vertex_point_adapter/profiles.json'),'client/profile differs');sign(build/'application')
    cases=[('same',1),('same',3),('same',5),('split',1),('split',3),('split',5),('no_producer',0)];intervals=[];rows=[];captures=[]
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        root=root.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process differs')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'lease differs');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs differ');sign(root/'application')
        need(m['args']==[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(root/'outputs'),mode],'arguments differ')
        obj=load(root/'stdout.json');need(obj['status']=='PASS' and obj['device']=='NVIDIA GeForce GTX 880M' and obj['registry_id'] and obj['mode']==mode and len(obj['results'])==len(cases),'client differs')
        hashes={}
        for (kind,n),item in zip(cases,obj['results']):
            mask=(1<<n)-1;value=mask^0xc0de0000
            need(item=={'kind':kind,'count':n,'input':mask,'output':value,'producer_present':kind!='no_producer','completed':True,'guards':True,'cpu_wait_before_consumer_commit':False},'result summary differs')
            f=root/'outputs'/f'{kind}-{n}.bin';raw=f.read_bytes();need(len(raw)==264,'raw length differs')
            for part,expected in ((raw[:132],mask),(raw[132:],value)):need(part[:64]==part[68:]==b'\xa5'*64 and struct.unpack('<I',part[64:68])[0]==expected,'raw output/guard differs')
            hashes[f'{kind}-{n}']=sha(f)
        events=[e for e in obj['events'] if e['operation']=='execute_CPU_render_ICB']
        if mode=='auto':
            need(len(events)==6,'adapted execution count differs')
            for n,e in zip((1,3,5,1,3,5),events):
                ev=e['evidence'];need(e['executed_indices']==[0] and ev['raw_records_copied']==1 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'execution differs')
                item=ev['sequence_records'][0];record=item['record'];raw=packet(item['commands_base64'],n);packet(item['primer_draw_base64'],1)
                need(item['vertex_write_usage'] and item['native_primer_draw_removed'] and record['primitive']==0 and record['vertex_count']==n and record['direct_method']==0x3830 and hashlib.sha256(raw).hexdigest()==record['SHA256'],'record differs')
        else:need(not events,'direct mode unexpectedly uses ICB')
        captures.append(hashes);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'buffers_sha256':hashes})
    need(all(x==captures[0] for x in captures),'direct/adapted buffers differ');intervals.sort();need(all(x<=y for x,y in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'process overlap')
    out={'status':'PASS_POINT_RENDER_TO_COMPUTE','archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'runs':rows,'processes':4,'same_command_buffer_cases':12,'same_queue_split_cases':12,'no_producer_controls':4,'raw_buffers_verified':56,'guard_bytes_verified':7168,'expected_masks':[1,7,31],'cpu_wait_before_consumer_commit':False,'gpu_overlap_proved':False,'cross_queue_tested':False,'general_metal_support':False,'performance_benchmark':False,'system_files_checked_unchanged':True}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':out['status'],'raw_buffers_verified':56,'no_producer_controls':4}))
if __name__=='__main__':main()
