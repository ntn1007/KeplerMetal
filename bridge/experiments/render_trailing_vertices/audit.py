#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify direct/adapted render captures and encoded draw counts offline."""
import argparse
import base64
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

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','archive','baseline-build','baseline-direct','baseline-auto','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=4,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==4,'fresh output / distinct runs')
    build=a.build.resolve();archive=a.archive.resolve();baseline=a.baseline_build.resolve();b=load(build/'build.json');old=load(baseline/'build.json');ar=load(archive/'manifest.json')
    need(b['status']==old['status']=='PREPARED_ONLY' and not b['gpu_execution'] and not old['gpu_execution'] and b['system']==old['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build provenance')
    need(old['archive_sha256']=='21b32ca58d2f5bca072721ff7c71f03855cd9e2587465bda7a3c55869bb81eb9','baseline archive differs')
    for name,h in ar['source_SHA256'].items():need(sha(archive/'src'/name)==sha(BRIDGE/'src'/name)==h,'archive source differs')
    for root,manifest in ((build,b),(baseline,old)):
        for n,h in manifest['files_sha256'].items():need(sha(root/n)==h,'build input differs: '+n)
        sign(root/'application')
    need(sha(build/'client.mm')==sha(HERE/'client.mm'),'client source differs')
    def common(root,mode,code,manifest,bd):
        m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==code and m['build_sha256']==sha(bd/'build.json') and m['host_sha256']==sha(root/'application')==manifest['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process evidence')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==code and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system');sign(root/'application');return m
    bdirect=a.baseline_direct.resolve();bauto=a.baseline_auto.resolve();common(bdirect,'direct',0,old,baseline);common(bauto,'auto',1,old,baseline)
    need('KeplerCPUICBUnsupported: Direct render geometry outside supported profile' in (bauto/'stderr.log').read_text() and {x.name for x in (bauto/'outputs').iterdir()}=={'count-3.bin'},'baseline refusal differs')
    control=load(bdirect/'stdout.json');need(control['status']=='PASS' and control['mode']=='direct' and [x['count'] for x in control['cases']]==[3,4,5],'baseline direct differs')
    rows=[];intervals=[];images=[]
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        root=root.resolve();m=common(root,mode,0,b,build);out=load(root/'stdout.json');need(m['args']==[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(root/'outputs'),mode],'arguments')
        need(out['status']=='PASS' and out['device']=='NVIDIA GeForce GTX 880M' and out['registry_id'] and out['mode']==mode and out['rejections']==(5 if mode=='auto' else 0) and [x['count'] for x in out['cases']]==[3,4,5] and all(x['completed'] and x['checked_channels']==12288 and x['guard_bytes']==512 for x in out['cases']),'client report')
        events=[x for x in out['events'] if x['operation']=='execute_CPU_render_ICB']
        if mode=='auto':
            need(len(events)==3,'ICB events')
            for event,count in zip(events,(3,4,5)):
                evidence=event['evidence'];need(event['executed_indices']==[0] and evidence['raw_records_copied']==1 and evidence['resource_usage_declared'] and len(evidence['sequence_records'])==1,'render record')
                item=evidence['sequence_records'][0];meta=item['record'];packet=base64.b64decode(item['commands_base64'],validate=True)
                need(len(packet)==24 and sha_bytes(packet)==meta['SHA256'] and meta['vertex_count']==count and meta['vertex_start']==1 and meta['instances']==1 and meta['name']=='smooth','command metadata')
                words=struct.unpack('<6I',packet);need(words[1:]==(4,count,1,1,0) and words[0]>>29==5 and (words[0]>>16)&0x1fff==5 and (words[0]&0x1fff)*4==0x3aa0,'command packet')
        else:need(not events,'native control unexpectedly records ICB')
        hashes={}
        for count in (3,4,5):
            path=root/'outputs'/f'count-{count}.bin';raw=path.read_bytes();need(len(raw)==49664 and raw[:256]==raw[-256:]==b'\xa5'*256,'guards');values=struct.unpack('<12288f',raw[256:-256]);color=(.75,.125,.25,1.);need(all(v==color[i%4] for i,v in enumerate(values)),'pixel oracle');hashes[str(count)]=sha(path)
        images.append(hashes);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'images_sha256':hashes})
    need(all(x==images[0] for x in images),'images differ');need(all(sha(bdirect/'outputs'/f'count-{c}.bin')==images[0][str(c)] for c in (3,4,5)) and sha(bauto/'outputs/count-3.bin')==images[0]['3'],'baseline pixels differ')
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'overlap')
    result={'status':'PASS_TRAILING_VERTEX_GPU','archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'baseline_refusal_before_count4':True,'baseline_direct_3_4_5_passed':True,'processes':4,'rendered_cases':12,'checked_float_channels':147456,'guard_bytes':6144,'expected_api_refusals':10,'packet_counts_verified':[3,4,5],'same_raw_pixels_direct_and_adapted':True,'trailing_vertex_invocations_proved':False,'general_metal_support':False,'system_modified':False,'performance_benchmark':False,'runs':rows}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'rendered_cases':12,'expected_api_refusals':10}))
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
if __name__=='__main__':main()
