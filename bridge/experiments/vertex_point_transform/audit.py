#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit native and scoped two-buffer point-transform GPU captures."""
import argparse,base64,hashlib,json,struct,subprocess,sys
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
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','archive','native-build','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=4,required=True);p.add_argument('--native-runs',type=Path,nargs=2,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs+a.native_runs))==6,'fresh output / distinct runs')
    build=a.build.resolve();archive=a.archive.resolve();native=a.native_build.resolve();b=load(build/'build.json');nb=load(native/'build.json');ar=load(archive/'manifest.json')
    need(b['status']==nb['status']=='PREPARED_ONLY' and not b['gpu_execution'] and not nb['gpu_execution'] and b['system']==nb['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build differs')
    for name,h in ar['source_SHA256'].items():need(sha(archive/'src'/name)==sha(BRIDGE/'src'/name)==h,'source differs '+name)
    for root,record in ((build,b),(native,nb)):
        for name,h in record['files_sha256'].items():need(sha(root/name)==h,'build input differs '+name)
        sign(root/'application')
    need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(native/'client.mm')==sha(HERE/'native/client.mm') and sha(build/'profiles.json')==sha(HERE/'profiles.json'),'source/profile differs')
    shader='0bd90c4639674a1542e535b06c56a47d550f6784a2bd127278d55b0c393438ae';need(sha(build/'vertex.metallib')==sha(native/'transform.metallib')==shader,'shader differs')
    intervals=[]
    def common(root,record,bd,runner,mode):
        root=root.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['exit_code']==0 and m['build_sha256']==sha(bd/'build.json') and m['host_sha256']==sha(root/'application')==record['files_sha256']['application'] and m['runner_sha256']==sha(runner),'process differs')
        if mode:need(m['mode']==mode and m['args']==[str(bd/'legacy.metallib'),str(bd/'vertex.metallib'),str(bd/'profiles.json'),str(root/'outputs'),mode],'args differ')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'lease differs');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs differ');sign(root/'application');intervals.append((m['started_at'],m['completed_at']));return load(root/'stdout.json')
    def rawcheck(root,n):
        f=root/'outputs'/f'count-{n}.bin';raw=f.read_bytes();need(len(raw)==2304,'raw length differs');src,dst=raw[:1152],raw[1152:]
        for part in (src,dst):need(part[:64]==part[1088:]==b'\xa5'*64,'guard differs')
        a=struct.unpack('<256I',src[64:1088]);b=struct.unpack('<256I',dst[64:1088]);expected=tuple((i*17)^0x12345678 for i in range(256));need(a==expected and b==tuple(((x*3+7)&0xffffffff) if i<n else 0xa5a5a5a5 for i,x in enumerate(expected)),'CPU oracle differs');return sha(f)
    nativehash=[]
    for root in a.native_runs:
        obj=common(root,nb,native,HERE/'native/experiment.py',None);need(obj['status']=='PASS' and obj['device']=='NVIDIA GeForce GTX 880M' and obj['registry_id'] and obj['reflection']==[{'name':'source','index':0,'access':0,'active':True,'type':0},{'name':'destination','index':1,'access':1,'active':True,'type':0}],'native reflection differs')
        counts=(0,1,17,256);need(obj['results']==[{'count':n,'completed':True,'guards':True,'checked_values':256} for n in counts],'native results differ');nativehash.append({str(n):rawcheck(root,n) for n in counts})
    rows=[];captures=[];counts=(0,1,17,128,256)
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        obj=common(root,b,build,HERE/'experiment.py',mode);need(obj['status']=='PASS' and obj['device']=='NVIDIA GeForce GTX 880M' and obj['registry_id'] and obj['mode']==mode and obj['registration_refusals']==2 and obj['rejections']==(14 if mode=='auto' else 0),'client differs')
        need(obj['results']==[{'count':n,'completed':True,'guards':True,'checked_values':256} for n in counts],'results differ')
        events=[e for e in obj['events'] if e['operation']=='execute_CPU_render_ICB']
        if mode=='auto':
            need(len(events)==5 and events[0]['executed_indices']==[],'zero draw differs')
            for n,event in zip(counts[1:],events[1:]):
                ev=event['evidence'];need(event['executed_indices']==[0] and ev['raw_records_copied']==1 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'execution differs')
                item=ev['sequence_records'][0];record=item['record'];raw=packet(item['commands_base64'],n);packet(item['primer_draw_base64'],1)
                need(item['vertex_write_usage'] and item['native_primer_draw_removed'] and record['primitive']==0 and record['vertex_count']==n and record['vertex_start']==0 and record['instances']==1 and record['direct_method']==0x3830 and record['library_SHA256']==shader and [x['index'] for x in record['bindings']]==[0,1] and hashlib.sha256(raw).hexdigest()==record['SHA256'],'record differs')
        else:need(not events,'direct mode unexpectedly uses ICB')
        hashes={str(n):rawcheck(root,n) for n in counts};captures.append(hashes);rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'buffers_sha256':hashes})
    need(all(x==captures[0] for x in captures),'direct/adapted buffers differ');need(all(all(h[str(n)]==captures[0][str(n)] for n in (0,1,17,256)) for h in nativehash),'native baseline differs')
    intervals.sort();need(all(x<=y for x,y in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(5)),'process overlap')
    result={'status':'PASS_POINT_TRANSFORM_ICB','archive_sha256':b['archive_sha256'],'shader_sha256':shader,'profile_sha256':sha(build/'profiles.json'),'build_sha256':sha(build/'build.json'),'runs':rows,'native_processes':2,'adapted_and_direct_processes':4,'final_completed_buffers':20,'native_completed_buffers':8,'final_values_checked':10240,'native_values_checked':4096,'final_guard_bytes_verified':5120,'native_guard_bytes_verified':2048,'registration_identity_refusals':8,'adapted_api_refusals':28,'adapted_packets_verified':8,'direct_native_adapted_match':True,'arbitrary_shader_support':False,'transparent_system_integration':False,'performance_benchmark':False,'system_files_checked_unchanged':True}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'final_values_checked':10240,'adapted_api_refusals':28}))
if __name__=='__main__':main()
