#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently audit local Apple-renderer captures and ICB packet evidence."""
import argparse,base64,hashlib,json,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
from adapt import EXPECTED

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok: raise ValueError(why)
def signature(p): need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('sample','build','archive','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',nargs=6,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==6,'fresh output and runs')
    sample=a.sample.resolve();build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json')
    need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive')
    for name,h in EXPECTED.items():need(sha(sample/'source'/'Renderer'/name)==h,'Apple source '+name)
    need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build archive')
    need(b['apple_source_sha256']==EXPECTED and b['adapt_sha256']==sha(HERE/'adapt.py') and sha(build/'client.mm')==sha(HERE/'client.mm'),'source provenance')
    for name,h in ar['source_SHA256'].items():need(sha(archive/'src'/name)==sha(BRIDGE/'src'/name)==h,'runtime source '+name)
    for name,h in b['files_sha256'].items():need(sha(build/name)==h,'build file '+name)
    need(sha(build/'vertex.metallib')==sha(sample/'apple.metallib') and sha(build/'profiles.json')==sha(HERE/'profiles.json'),'shader or profile')
    signature(build/'application');rows=[];images=[];blanks=[];intervals=[];packets=0
    counts=[36,48,60,72,84,96,108,120,288,324,360,396,432,468,504]
    for path,mode in zip(a.runs,('direct','auto','direct','auto','blank','blank')):
        path=path.resolve();m=load(path/'manifest.json');lease=m['reservation']
        need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(path/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');signature(path/'application')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(path/'stdout.json') and m['stderr_sha256']==sha(path/'stderr.log'),'logs/system')
        x=load(path/'stdout.json');need(x['status']=='PASS' and x['mode']==mode and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['actual_apple_renderer'] and x['application_modified'] and not x['framebuffer_only'] and x['window_visible'] and not x['window_key'] and x['depth_actions']==[0,0] and x['refusals']==(2 if mode=='auto' else 0) and len(x['cases'])==2,'client')
        events=[e for e in x['events'] if e['operation']=='execute_CPU_render_ICB'];need(len(events)==(2 if mode=='auto' else 0),'event count')
        for event in events:
            ev=event['evidence'];need(event['executed_indices']==list(range(15)) and ev['raw_records_copied']==15 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==15,'event')
            for i,entry in enumerate(ev['sequence_records']):
                meta=entry['record'];bindings=meta['bindings'];packet=base64.b64decode(entry['commands_base64'],validate=True)
                need(meta['name']=='apple_explicit_view' and meta['vertex_count']==counts[i] and meta['vertex_start']==0 and meta['instances']==1 and meta['base_instance']==i and meta['library_SHA256']==b['files_sha256']['vertex.metallib'] and meta['manifest_SHA256']==b['files_sha256']['profiles.json'] and len(bindings)==3 and [q['index'] for q in bindings]==[0,1,2] and [q['length'] for q in bindings]==[counts[i]*16,120,8] and [q['storage_mode'] for q in bindings]==[0,0,2] and struct.unpack('<6I',packet)==(0xa0050ea8,4,counts[i],1,0,i) and sha_bytes(packet)==meta['SHA256'],'packet');packets+=1
        frame_hash=[]
        for i,item in enumerate(x['cases']):
            need(item['frame']==i and item['completed'] and item['guard_bytes']==512 and item['color_readback'],'frame')
            raw=(path/'outputs'/f'frame-{i}.bin').read_bytes();need(len(raw)==12800 and raw[:256]==raw[-256:]==b'\xa5'*256,'guards')
            color=raw[256:-256];colors=set(color[j:j+4] for j in range(0,len(color),4));need(len(colors)==1 if mode=='blank' else len(colors)>2,'image discrimination')
            frame_hash.append(sha_bytes(color))
        need(frame_hash[0]==frame_hash[1],'frame mismatch')
        (blanks if mode=='blank' else images).append(frame_hash);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'image_sha256':frame_hash})
    need(all(x==images[0] for x in images) and all(x==blanks[0] for x in blanks) and images[0]!=blanks[0] and packets==60,'images differ')
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(5)),'overlap')
    out={'status':'PASS_DEPTH_DONTCARE','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_source_sha256':EXPECTED,'archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'processes':6,'frames':12,'draw_frames':8,'blank_frames':4,'adapted_packets_checked':packets,'vertex_counts':counts,'pixels_compared':36864,'guard_bytes_checked':6144,'direct_adapted_images_identical':True,'blank_uniform':True,'depth_store_action':'dont_care','invalid_store_refusals':4,'actual_apple_renderer':True,'application_modified':True,'apple_original_ui_executed':False,'drawable_color_readback':True,'visible_presentation_proved':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':out['status'],'frames':12,'packets':packets}))
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
if __name__=='__main__':main()
