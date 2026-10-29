#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit paired Apple render-command benchmark and image controls."""
import argparse,base64,hashlib,json,statistics,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
from adapt import EXPECTED
from adapt_controller import CONTROLLER_HASHES

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(x,why):
    if not x:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('sample','baseline-build','cache-build','baseline-archive','cache-archive','direct','blank','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',nargs=12,type=Path,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs+[a.direct,a.blank]))==14,'fresh output or duplicate runs')
    sample=a.sample.resolve();need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive')
    for n,h in EXPECTED.items():need(sha(sample/'source'/'Renderer'/n)==h,'renderer source')
    for n,h in CONTROLLER_HASHES.items():need(sha(sample/'source'/'Application'/n)==h,'controller source')
    archives=[a.baseline_archive.resolve(),a.cache_archive.resolve()];builds=[a.baseline_build.resolve(),a.cache_build.resolve()];ars=[load(x/'manifest.json') for x in archives];bs=[load(x/'build.json') for x in builds]
    old='e7561f8f60f9fde126db7e7eb6b8913235582924d1f9fb2c0c163dc37cad2367';new='8212f9cece201bba4e231e4795c6fb0b380c638992cd75f05ef28af14e627b4e'
    need([ar['source_SHA256']['KeplerCPUICB.mm'] for ar in ars]==[old,new] and ars[0]['architecture']==ars[1]['architecture']=='x86_64' and ars[0]['SDK']==ars[1]['SDK'] and ars[0]['clang']==ars[1]['clang'] and ars[0]['builder_SHA256']==ars[1]['builder_SHA256'],'archive compiler/revisions')
    need({k for k in ars[0]['source_SHA256'] if ars[0]['source_SHA256'][k]!=ars[1]['source_SHA256'].get(k)}=={'KeplerCPUICB.mm'} and ars[0]['source_SHA256'].keys()==ars[1]['source_SHA256'].keys(),'source delta')
    need({k for k in ars[0]['object_SHA256'] if ars[0]['object_SHA256'][k]!=ars[1]['object_SHA256'].get(k)}=={'KeplerCPUICB.o'} and ars[0]['object_SHA256'].keys()==ars[1]['object_SHA256'].keys(),'object delta')
    for build,archive,b,ar in zip(builds,archives,bs,ars):
        need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build archive')
        need(b['apple_source_sha256']==EXPECTED and b['controller_source_sha256']==CONTROLLER_HASHES and b['adapt_sha256']==sha(HERE/'adapt.py') and b['controller_adapt_sha256']==sha(HERE/'adapt_controller.py') and sha(build/'client.mm')==sha(HERE/'client.mm'),'source provenance')
        for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==h and (n=='KeplerCPUICB.mm' or sha(BRIDGE/'src'/n)==h),'archive source')
        for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build file')
        need({str(x.relative_to(build)):sha(x) for x in (build/'Storyboard.bundle').rglob('*') if x.is_file()}==b['storyboard_files_sha256'] and b['storyboard_files_sha256'],'storyboard');sign(build/'application')
    need({k:v for k,v in bs[0]['files_sha256'].items() if k!='application'}=={k:v for k,v in bs[1]['files_sha256'].items() if k!='application'},'test asset mismatch')
    need(sha(builds[1]/'vertex.metallib')==sha(sample/'apple.metallib') and sha(builds[1]/'profiles.json')==sha(HERE/'profiles.json'),'shader or profile')
    counts=[36,48,60,72,84,96,108,120,288,324,360,396,432,468,504];intervals=[];summary=[];image_sets=[];blank_set=None;measurements=[[],[]];process_medians=[[],[]];reuse_frames=[1,2,3,5,6,7]
    paths=[(a.direct,1,'direct'),(a.blank,1,'blank')]+[(path,i%2,'auto') for i,path in enumerate(a.runs)]
    for path,version,mode in paths:
        path=path.resolve();build=builds[version];b=bs[version];m=load(path/'manifest.json');lease=m['reservation']
        need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(path/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py') and m['storyboard_build_sha256']==sha(builds[1]/'build.json') and len(m['args'])==6 and m['args'][5]==str(builds[1]/'Storyboard.bundle'),'process provenance');sign(path/'application')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(path/'stdout.json') and m['stderr_sha256']==sha(path/'stderr.log') and 'native ICB family gate = NO' in (path/'stderr.log').read_text(),'logs/system')
        x=load(path/'stdout.json');need(x['status']=='PASS' and x['mode']==mode and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['actual_apple_renderer'] and x['original_storyboard'] and x['actual_apple_view_controller'] and x['application_modified'] and not x['framebuffer_only'] and x['window_visible'] and not x['window_key'] and x['depth_actions']==[0]*8 and x['refusals']==(8 if mode=='auto' else 0) and x['binding_refusals']==(1 if mode=='auto' else 0) and x['only_last_waited_explicitly'] and len(x['cases'])==8,'client')
        events=[e for e in x['events'] if e['operation']=='execute_CPU_render_ICB'];materials=[e for e in x['events'] if e['operation']=='materialize_CPU_render_command'];need(len(events)==(8 if mode=='auto' else 0),'event count')
        expected_materials=(list(range(15))*8 if version==0 else list(range(15))+[0]) if mode=='auto' else []
        need([e['index'] for e in materials]==expected_materials and all(e['GPU_render_dispatches']==0 for e in materials),'materialization')
        for frame,event in enumerate(events):
            expected=[] if frame==0 else list(range(1,15)) if frame==4 else list(range(15))
            need((event.get('reused_inherited_indices',[])==(expected if version else [])),'reuse')
            ev=event['evidence'];need(event['executed_indices']==list(range(15)) and ev['raw_records_copied']==15 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==15,'event')
            for i,entry in enumerate(ev['sequence_records']):
                meta=entry['record'];bindings=meta['bindings'];packet=base64.b64decode(entry['commands_base64'],validate=True)
                need(meta['name']=='apple_explicit_view' and meta['vertex_count']==counts[i] and meta['vertex_start']==0 and meta['instances']==1 and meta['base_instance']==i and meta['library_SHA256']==b['files_sha256']['vertex.metallib'] and meta['manifest_SHA256']==b['files_sha256']['profiles.json'] and len(bindings)==3 and [q['index'] for q in bindings]==[0,1,2] and [q['length'] for q in bindings]==[(counts[1]*16 if i==0 and frame>=4 else counts[i]*16),120,8] and [q['storage_mode'] for q in bindings]==[0,0,2] and struct.unpack('<6I',packet)==(0xa0050ea8,4,counts[i],1,0,i) and sha_bytes(packet)==meta['SHA256'],'packet')
        frame_hash=[]
        for i,item in enumerate(x['cases']):
            need(item['frame']==i and item['aspect_variant']==i%2 and item['completed'] and item['guard_bytes']==512 and item['color_readback'],'frame')
            raw=(path/'outputs'/f'frame-{i}.bin').read_bytes();need(len(raw)==12800 and raw[:256]==raw[-256:]==b'\xa5'*256,'guards')
            color=raw[256:-256];colors=set(color[j:j+4] for j in range(0,len(color),4));need(len(colors)==1 if mode=='blank' else len(colors)>2,'image discrimination');frame_hash.append(sha_bytes(color))
        need(all(h==frame_hash[(i//4)*4+i%2] for i,h in enumerate(frame_hash)) and (len(set(frame_hash))==1 if mode=='blank' else len(set(frame_hash))==4),'frame discrimination')
        (image_sets.append(frame_hash) if mode!='blank' else None)
        if mode=='blank':blank_set=frame_hash
        timings=x['timings'];need(len(timings)==(8 if mode=='auto' else 0),'timings count')
        if mode=='auto':
            need([t['frame'] for t in timings]==list(range(8)) and all(isinstance(t['wall_ns'],int) and isinstance(t['thread_cpu_ns'],int) and 0<t['thread_cpu_ns']<=t['wall_ns'] for t in timings),'timings')
            selected={metric:[timings[i][metric] for i in reuse_frames] for metric in ('wall_ns','thread_cpu_ns')};med={metric:statistics.median(vals) for metric,vals in selected.items()}
            for metric,values in selected.items():measurements[version].extend((metric,v) for v in values)
            process_medians[version].append(med)
        else:med=None
        intervals.append((m['started_at'],m['completed_at']));summary.append({'mode':mode,'version':'cache' if version else 'baseline','manifest_sha256':sha(path/'manifest.json'),'image_sha256':frame_hash,'timings':timings,'selected_medians_ns':med})
    need(all(x==image_sets[0] for x in image_sets) and blank_set and blank_set!=image_sets[0],'image agreement');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(13)),'overlap')
    for pair in range(6):
        left=load(a.runs[2*pair]/'manifest.json');right=load(a.runs[2*pair+1]/'manifest.json');need((left['started_at']<right['started_at'])==(pair%2==0),'pair order')
        if pair<5:
            future=[load(a.runs[2*pair+2]/'manifest.json')['started_at'],load(a.runs[2*pair+3]/'manifest.json')['started_at']];need(max(left['completed_at'],right['completed_at'])<=min(future),'pair ordering')
    stats={}
    for metric in ('wall_ns','thread_cpu_ns'):
        bmed=[v[metric] for v in process_medians[0]];cmed=[v[metric] for v in process_medians[1]];ratios=[b/c for b,c in zip(bmed,cmed)]
        stats[metric]={'baseline_median_of_process_medians':statistics.median(bmed),'cache_median_of_process_medians':statistics.median(cmed),'median_paired_speed_ratio':statistics.median(ratios),'paired_ratios':ratios,'baseline_process_medians':bmed,'cache_process_medians':cmed}
    out={'status':'PASS_PAIRED_CACHE_BENCHMARK','source_core_sha256':[old,new],'archive_sha256':[b['archive_sha256'] for b in bs],'benchmark_pairs':6,'benchmark_processes':12,'control_processes':2,'frames_total':112,'timed_frames_per_process':reuse_frames,'timed_observations_per_version':36,'adapted_packets_checked':1440,'pixels_checked':344064,'guards_checked':57344,'benchmark_scope':'executeCommandsInBuffer caller thread only','cpu_clock':'CLOCK_THREAD_CPUTIME_ID','wall_clock':'CLOCK_MONOTONIC','gpu_time_measured':False,'system_driver_changed':False,'original_app_executable':False,'transparent_integration':False,'system_file_hashes_unchanged':True,'statistics_ns':stats,'runs':summary}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':out['status'],'statistics_ns':stats}))
if __name__=='__main__':main()
