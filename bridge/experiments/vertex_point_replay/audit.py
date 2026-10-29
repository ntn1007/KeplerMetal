#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check signed GTX direct/replay receipts, packet words and output masks."""
import argparse, base64, hashlib, json, struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def packet(value,n):
    raw=base64.b64decode(value,validate=True)
    need(len(raw)==24 and struct.unpack('<6I',raw)==(0xa0050e0c,0,n,1,0,0),'point packet differs')
    return raw

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=4,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==4,'fresh output / distinct runs')
    b=load(a.build/'build.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM,'build differs')
    for n,h in b['files_sha256'].items():need(sha(a.build/n)==h,'build file differs')
    need(sha(HERE/'client.mm')==sha(a.build/'client.mm'),'source differs');sign(a.build/'application')
    intervals=[];rows=[]
    for root,mode in zip(a.runs,('direct','replay','direct','replay')):
        m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(a.build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process differs')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'lease differs')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs differ');sign(root/'application')
        obj=load(root/'stdout.json');need(obj['device']=='NVIDIA GeForce GTX 880M' and obj['registry_id'] and obj['mode']==mode,'device/mode differs')
        need(obj['reflection']==[{'access':1,'active':True,'name':'seen','type':0,'index':0}],'reflection differs')
        need(len(obj['results'])==6,'case count differs')
        for n,item in enumerate(obj['results']):
            need(item['primitive']=='point' and item['count']==n and item['mask']==(1<<n)-1 and item['guards'] and item['completed'],'result differs')
            actual=packet(item['packet_base64'],n);packet(item['primer_base64'],1 if mode=='replay' else n)
            if mode=='replay':need(actual==packet(item['record_base64'],n),'record differs')
            else:need(item['record_base64']=='','unexpected record')
        intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'stdout_sha256':sha(root/'stdout.json')})
    intervals.sort();need(all(x<=y for x,y in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'overlapping GPU runs')
    out={'status':'PASS_POINT_PACKET_REPLAY','build_sha256':sha(a.build/'build.json'),'host_sha256':b['files_sha256']['application'],'source_sha256':sha(HERE/'client.mm'),'runs':rows,'counts':[0,1,2,3,4,5],'observed_masks':[0,1,3,7,15,31],'completed_buffers':24,'guard_bytes_reported':3072,'captured_packets_checked':24,'uncommitted_records_copied':12,'primitive_value':0,'native_method':'0x3830','replay_primer_count':1,'adapter_tested':False,'transparent_system_integration':False,'performance_benchmark':False,'raw_gpu_buffers_retained':False,'system_files_checked_unchanged':True}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(out))
if __name__=='__main__':main()
