#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently audit local Apple-renderer captures and ICB packet evidence."""
import argparse,base64,hashlib,json,plistlib,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
from adapt import EXPECTED
from adapt_controller import CONTROLLER_HASHES
from experiment import tree,MAIN_SHA

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok: raise ValueError(why)
def signature(p): need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('sample','build','archive','vertex','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',nargs=6,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==6,'fresh output and runs')
    sample=a.sample.resolve();build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json')
    need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive')
    for name,h in EXPECTED.items():need(sha(sample/'source'/'Renderer'/name)==h,'Apple source '+name)
    for name,h in CONTROLLER_HASHES.items():need(sha(sample/'source'/'Application'/name)==h,'Apple controller/storyboard '+name)
    need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build archive')
    need(b['apple_source_sha256']==EXPECTED and b['controller_source_sha256']==CONTROLLER_HASHES and b['sample_main_sha256']==MAIN_SHA==sha(sample/'source/Application/main.m') and b['adapt_sha256']==sha(HERE/'adapt.py') and b['controller_adapt_sha256']==sha(HERE/'adapt_controller.py') and b['lab_runtime_sha256']==sha(HERE/'lab_runtime.mm') and tree(build/'local')==b['local_files_sha256'] and tree(build/'Sample.app')==b['bundle_files_sha256'],'source/bundle provenance')
    info=plistlib.loads((build/'Sample.app/Contents/Info.plist').read_bytes());need(info['NSMainStoryboardFile']=='Main' and info['LSUIElement'] and info['CFBundleExecutable']=='Indirect Command Buffers on CPU' and any('Main.storyboardc/' in k for k in b['bundle_files_sha256']),'bundle metadata')
    need('_NSApplicationMain' in subprocess.run(['nm','-u',str(build/'application')],capture_output=True,text=True,check=True).stdout,'NSApplicationMain import')
    for name,h in ar['source_SHA256'].items():need(sha(archive/'src'/name)==sha(BRIDGE/'src'/name)==h,'runtime source '+name)
    for name,h in b['assets_sha256'].items():need(sha(build/name)==h,'build asset '+name)
    need(sha(build/'vertex.metallib')==sha(a.vertex) and sha(build/'profiles.json')==sha(HERE/'profiles.json'),'shader or profile')
    signature(build/'application');rows=[];images=[];blanks=[];intervals=[];packets=0
    counts=[36,48,60,72,84,96,108,120,288,324,360,396,432,468,504]
    for path,mode in zip(a.runs,('direct','auto','direct','auto','blank','blank')):
        path=path.resolve();m=load(path/'manifest.json');lease=m['reservation']
        need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(path/'signed-application')==sha(path/'Sample.app/Contents/MacOS/Indirect Command Buffers on CPU')==b['executable_sha256'] and m['bundle_files_sha256']==tree(path/'Sample.app')==b['bundle_files_sha256'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');signature(path/'signed-application')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(path/'stdout.json') and m['stderr_sha256']==sha(path/'stderr.log'),'logs/system')
        need('native ICB family gate = NO' in (path/'stderr.log').read_text(),'original family gate observation')
        x=load(path/'stdout.json');need(x['status']=='PASS' and x['mode']==mode and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['actual_apple_renderer'] and x['original_storyboard'] and x['actual_apple_view_controller'] and x['application_modified'] and x['application_bundle'] and x['nsapplicationmain'] and x['view_did_appear'] and x['queue_adapted']==(mode=='auto') and x['queue_restored'] and x['shared_methods_unchanged'] and not x['framebuffer_only'] and x['window_visible'] and not x['window_key'] and x['depth_actions']==[0]*8 and x['refusals']==(8 if mode=='auto' else 0) and x['binding_refusals']==(1 if mode=='auto' else 0) and x['only_last_waited_explicitly'] and len(x['cases'])==8 and len(x['submission_statuses'])==len(x['pending_observations'])==8 and all(2<=st<=4 for st in x['submission_statuses']) and all(0<=n<=3 for n in x['pending_observations']),'client')
        events=[e for e in x['events'] if e['operation']=='execute_CPU_render_ICB'];need(len(events)==(8 if mode=='auto' else 0),'event count')
        enables=[e for e in x['events'] if e['operation']=='automatic_render_factories_enabled']
        factories=[e for e in x['events'] if e['operation']=='automatic_render_encoder']
        buffers=[e for e in x['events'] if e['operation']=='automatic_command_buffer']
        need(len(enables)==(1 if mode=='auto' else 0) and len(factories)==len(buffers)==(24 if mode=='auto' else 0),'automatic factory event count')
        need(all(e['queue_instance_only'] and not e['shared_native_methods_replaced'] for e in enables) and all(e['selector']=='renderCommandEncoderWithDescriptor:' and not e['explicit_adaptation_required'] for e in factories) and all(e['selector']=='commandBuffer' and e['class_layout_preserved'] and e['retained_references'] for e in buffers),'automatic factory evidence')
        materials=[e for e in x['events'] if e['operation']=='materialize_CPU_render_command'];need([e['index'] for e in materials]==(list(range(15))+[0] if mode=='auto' else []) and all(e['GPU_render_dispatches']==0 for e in materials),'materialization/invalidation')
        for frame,event in enumerate(events):
            expected_reuse=[] if frame==0 else list(range(1,15)) if frame==4 else list(range(15));need(event['reused_inherited_indices']==expected_reuse,'cache reuse')
            ev=event['evidence'];need(event['executed_indices']==list(range(15)) and ev['raw_records_copied']==15 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==15,'event')
            for i,entry in enumerate(ev['sequence_records']):
                meta=entry['record'];bindings=meta['bindings'];packet=base64.b64decode(entry['commands_base64'],validate=True)
                need(meta['name']=='apple_explicit_view' and meta['vertex_count']==counts[i] and meta['vertex_start']==0 and meta['instances']==1 and meta['base_instance']==i and meta['library_SHA256']==b['assets_sha256']['vertex.metallib'] and meta['manifest_SHA256']==b['assets_sha256']['profiles.json'] and len(bindings)==3 and [q['index'] for q in bindings]==[0,1,2] and [q['length'] for q in bindings]==[(counts[1]*16 if i==0 and frame>=4 else counts[i]*16),120,8] and [q['storage_mode'] for q in bindings]==[0,0,2] and struct.unpack('<6I',packet)==(0xa0050ea8,4,counts[i],1,0,i) and sha_bytes(packet)==meta['SHA256'],'packet');packets+=1
        frame_hash=[]
        for i,item in enumerate(x['cases']):
            need(item['frame']==i and item['aspect_variant']==i%2 and item['completed'] and item['guard_bytes']==512 and item['color_readback'],'frame')
            raw=(path/'outputs'/f'frame-{i}.bin').read_bytes();width,height=(800,600) if i%2 else (64,48);pitch=(width*4+255)&~255;need(len(raw)==512+pitch*height and raw[:256]==raw[-256:]==b'\xa5'*256,'guards')
            rows_data=[raw[256+y*pitch:256+(y+1)*pitch] for y in range(height)];need(all(row[width*4:]==b'\xa5'*(pitch-width*4) for row in rows_data),'row padding');color=b''.join(row[:width*4] for row in rows_data);colors=set(color[j:j+4] for j in range(0,len(color),4));need(len(colors)==1 if mode=='blank' else len(colors)>2,'image discrimination')
            frame_hash.append(sha_bytes(color))
        need(all(h==frame_hash[(i//4)*4+(i%2)] for i,h in enumerate(frame_hash)) and (len(set(frame_hash))==2 if mode=='blank' else len(set(frame_hash))==4),'frame discrimination')
        (blanks if mode=='blank' else images).append(frame_hash);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'image_sha256':frame_hash,'submission_statuses':x['submission_statuses'],'pending_observations':x['pending_observations']})
    need(all(x==images[0] for x in images) and all(x==blanks[0] for x in blanks) and images[0]!=blanks[0] and packets==240,'images differ')
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(5)),'overlap')
    out={'status':'PASS_APPLE_EXTENT_TRANSITION','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_source_sha256':EXPECTED,'apple_controller_source_sha256':CONTROLLER_HASHES,'archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'processes':6,'frames':48,'draw_frames':32,'blank_frames':16,'adapted_packets_checked':packets,'vertex_counts':counts,'pixels_compared':11593728,'guard_bytes_checked':24576,'direct_adapted_images_identical':True,'blank_uniform':True,'depth_store_action':'dont_care','invalid_store_refusals':16,'short_rebind_refusals':2,'materializations_per_adapted_process':16,'cache_reuses_per_adapted_process':104,'automatic_render_factory_enabled':True,'automatic_encoder_events_per_adapted_process':24,'client_render_encoder_events_per_adapted_process':8,'recording_encoder_events_per_adapted_process':16,'shared_native_methods_replaced':False,'native_class_IMPs_checked_unchanged':True,'queue_class_restored':True,'actual_apple_renderer':True,'application_modified':True,'apple_storyboard_instantiated':True,'apple_controller_instantiated':True,'application_bundle_executed':True,'modified_executable':True,'original_unmodified_executable':False,'drawable_color_readback':True,'visible_presentation_proved':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
    out['target_extents']=[[64,48],[800,600]]
    out['row_padding_bytes_checked']=1843200
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':out['status'],'frames':48,'packets':packets}))
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
if __name__=='__main__':main()
