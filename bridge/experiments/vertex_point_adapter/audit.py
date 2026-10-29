#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the four certified point-write GPU captures and command records."""
import argparse, base64, hashlib, json, struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; BRIDGE=HERE.parents[1]
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
    need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'profiles.json')==sha(HERE/'profiles.json'),'client/profile differs');sign(build/'application')
    intervals=[];rows=[];captures=[]
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        root=root.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process differs')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'lease differs');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs differ');sign(root/'application')
        need(m['args']==[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(root/'outputs'),mode],'arguments differ')
        obj=load(root/'stdout.json');need(obj['status']=='PASS' and obj['device']=='NVIDIA GeForce GTX 880M' and obj['registry_id'] and obj['mode']==mode and obj['registration_refusals']==2 and obj['rejections']==(9 if mode=='auto' else 0),'client differs')
        need(obj['results']==[{'count':n,'mask':(1<<n)-1,'completed':True,'guards':True} for n in range(6)],'results differ')
        events=[e for e in obj['events'] if e['operation']=='execute_CPU_render_ICB']
        if mode=='auto':
            need(len(events)==6 and events[0]['executed_indices']==[],'zero draw differs')
            for n,event in enumerate(events[1:],1):
                ev=event['evidence'];need(event['executed_indices']==[0] and ev['raw_records_copied']==1 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'execution differs')
                item=ev['sequence_records'][0];record=item['record'];raw=packet(item['commands_base64'],n);packet(item['primer_draw_base64'],1)
                need(item['vertex_write_usage'] and item['native_primer_draw_removed'] and record['primitive']==0 and record['vertex_count']==n and record['vertex_start']==0 and record['instances']==1 and record['direct_method']==0x3830 and record['library_SHA256']=='d3c4675aa2e0668be09527c8a861487ea092b7697c082a9224defe6dbd4ffacc' and hashlib.sha256(raw).hexdigest()==record['SHA256'],'record differs')
        else:need(not events,'direct mode unexpectedly uses ICB')
        hashes={}
        for n in range(6):
            f=root/'outputs'/f'count-{n}.bin';raw=f.read_bytes();need(len(raw)==132 and raw[:64]==raw[68:]==b'\xa5'*64 and struct.unpack('<I',raw[64:68])[0]==(1<<n)-1,'raw buffer differs');hashes[str(n)]=sha(f)
        captures.append(hashes);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'buffers_sha256':hashes})
    need(all(x==captures[0] for x in captures),'direct/adapted buffers differ');intervals.sort();need(all(x<=y for x,y in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'overlap')
    result={'status':'PASS_CERTIFIED_POINT_WRITE_ICB','archive_sha256':b['archive_sha256'],'shader_sha256':sha(build/'vertex.metallib'),'profile_sha256':sha(build/'profiles.json'),'build_sha256':sha(build/'build.json'),'runs':rows,'processes':4,'completed_buffers':24,'raw_results_verified':24,'guard_bytes_verified':3072,'shader_identity_refusals':8,'other_refusals':18,'adapted_draw_packets_verified':10,'direct_and_adapted_buffers_match':True,'resource_write_usage_declared':True,'record_leases_reported':True,'gpu_indirect_range_supported':False,'general_shader_support':False,'transparent_system_integration':False,'performance_benchmark':False,'system_files_checked_unchanged':True}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'completed_buffers':24,'other_refusals':18}))
if __name__=='__main__':main()
