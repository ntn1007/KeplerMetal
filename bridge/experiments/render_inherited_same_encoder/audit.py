#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit same-encoder inherited pipeline switching and caller-state restoration."""
import argparse, base64, hashlib, json, math, struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','archive','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=4,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==4,'fresh output / distinct runs')
    build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json')
    need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build provenance')
    for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs: '+n)
    for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build input differs: '+n)
    need(sha(build/'client.mm')==sha(HERE/'client.mm'),'client differs');sign(build/'application')
    rows=[];intervals=[];images=[];names=['smooth','flat','smooth']
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        root=root.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process evidence')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log') and m['args']==[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(root/'outputs'),mode],'logs/system/arguments');sign(root/'application')
        out=load(root/'stdout.json');need(out['status']=='PASS' and out['device']=='NVIDIA GeForce GTX 880M' and out['registry_id'] and out['mode']==mode and out['cases']==[{'pipelines':names,'completed':True,'guard_bytes':512,'same_encoder':True,'followup_direct_draw':True}],'client report')
        events=[e for e in out['events'] if e['operation']=='execute_CPU_render_ICB'];materials=[e for e in out['events'] if e['operation']=='materialize_CPU_render_command']
        if mode=='auto':
            need(len(events)==len(materials)==3 and [x['record']['name'] for x in materials]==names,'pipeline rematerialization')
            for event,name in zip(events,names):
                ev=event['evidence'];need(event['executed_indices']==[0] and event['caller_pipeline_restored'] and event['caller_vertex_slots_restored']==2 and ev['raw_records_copied']==1 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'render event')
                item=ev['sequence_records'][0];meta=item['record'];packet=base64.b64decode(item['commands_base64'],validate=True)
                need(meta['name']==name and meta['vertex_count']==3 and meta['vertex_start']==1 and meta['instances']==1 and hashlib.sha256(packet).hexdigest()==meta['SHA256'] and struct.unpack('<6I',packet)==(0xa0050ea8,4,3,1,1,0),'packet')
        else:need(not events and not materials,'direct control uses adapter')
        data=(root/'outputs/image.bin').read_bytes();need(len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256,'guard differs');values=struct.unpack('<12288f',data[256:-256]);need(all(math.isfinite(x) for x in values),'nonfinite image')
        for y in range(48):
            for x in range(64):
                pixel=values[(y*64+x)*4:(y*64+x)*4+4];need(pixel[3]==1,'alpha')
                if 16<=x<32:need(pixel==(1.,0.,0.,1.),'flat region')
                if 48<=x<64:need(pixel==(0.,1.,0.,1.),'caller restoration region')
                if x<16 or 32<=x<48:need(all(0<=v<=1 for v in pixel[:3]) and abs(sum(pixel[:3])-1)<1e-6,'smooth region')
        need(values[(24*64+8)*4] != values[(24*64+9)*4] and values[(24*64+40)*4] != values[(24*64+41)*4],'smooth interpolation control')
        images.append(data);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'image_sha256':hashlib.sha256(data).hexdigest()})
    need(all(v==images[0] for v in images),'direct/adapted pixels differ');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'process overlap')
    result={'status':'PASS_INHERITED_SAME_ENCODER_GPU','archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'processes':4,'completed_render_buffers':4,'checked_float_channels':49152,'checked_guard_bytes':2048,'cpu_exact_flat_pixels':3072,'cpu_exact_caller_pixels':3072,'same_encoder_pipeline_sequence':names,'followup_direct_draw_without_pipeline_or_vertex_rebind':True,'raw_direct_and_adapted_images_match':True,'full_icb_contract':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'completed_render_buffers':4,'cpu_exact_caller_pixels':3072}))
if __name__=='__main__':main()
