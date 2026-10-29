#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit MTKView framebuffer-only renders using independent depth readback."""
import argparse,base64,hashlib,json,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
 if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('sample','build','archive','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--runs',type=Path,nargs=6,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==6,'fresh output / distinct runs')
 sample=a.sample.resolve();need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','sample archive differs');build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build/archive')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs')
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build asset differs')
 need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'profiles.json')==sha(HERE/'profiles.json') and sha(build/'vertex.metallib')==sha(sample/'apple.metallib')=='adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf','client/library differs');sign(build/'application')
 intervals=[];rows=[];captures=[];blanks=[];callbacks=0;positive=0;order=((False,0),(False,1),(True,0),(True,1))
 for path,mode in zip(a.runs,('direct','auto','direct','auto','blank','blank')):
  root=path.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(root/'application')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system')
  x=load(root/'stdout.json');need(x['status']=='PASS' and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['mode']==mode and x['mtkview'] and x['layer_attached_to_window'] and x['window_visible'] and not x['window_key'] and x['framebuffer_only'] and len(x['cases'])==4 and x['refusals']==(1 if mode=='auto' else 0),'client report');events=[e for e in x['events'] if e['operation']=='execute_CPU_render_ICB'];need(len(events)==(4 if mode=='auto' else 0),'event count');images={}
  for idx,(item,(private,generation)) in enumerate(zip(x['cases'],order)):
   need(item['private_frame']==private and item['generation']==generation and item['completed'] and item['centers_checked']==15 and item['guard_bytes']==512 and item['mtkview_descriptor'] and item['drawable_obtained'] and item['presentation_scheduled'] and item['depth_readback'] and item['blank_control']==(mode=='blank'),'case differs');callbacks+=int(item['presented_callback']);positive+=int(item['presented_time']>0)
   if mode=='auto':
    event=events[idx];ev=event['evidence'];need(event['executed_indices']==list(range(15)) and ev['raw_records_copied']==15 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==15,'ICB event');mesh=set();objects=set();frames=set()
    for i,entry in enumerate(ev['sequence_records']):
     meta=entry['record'];packet=base64.b64decode(entry['commands_base64'],validate=True);bindings=meta['bindings'];prefix=base64.b64decode(entry['prefix_base64'],validate=True);expected_prefix=struct.pack('<7I',0xa0040eb0,0x405,0x900,3,0x3f800000,0xa0010eac,0) if i==0 else struct.pack('<2I',0xa0010eac,0);need(meta['name']=='apple_explicit_view' and meta['vertex_count']==3 and meta['vertex_start']==0 and meta['instances']==1 and meta['base_instance']==i and meta['library_SHA256']==b['files_sha256']['vertex.metallib'] and meta['manifest_SHA256']==b['files_sha256']['profiles.json'] and len(bindings)==3 and [q['index'] for q in bindings]==[0,1,2] and [q['length'] for q in bindings]==[48,120,8] and bindings[2]['storage_mode']==(2 if private else 0) and struct.unpack('<6I',packet)==(0xa0050ea8,4,3,1,0,i) and hashlib.sha256(packet).hexdigest()==meta['SHA256'] and prefix==expected_prefix and hashlib.sha256(prefix).hexdigest()==entry['prefix_SHA256'],'packet/metadata/prefix');mesh.add(bindings[0]['GPU_address']);objects.add(bindings[1]['GPU_address']);frames.add(bindings[2]['GPU_address'])
    need(len(mesh)==15 and len(objects)==len(frames)==1,'resource identity differs')
   name=('private' if private else 'shared')+'-'+str(generation)+'.bin';data=(root/'outputs'/name).read_bytes();need(len(data)==12800 and data[:256]==data[-256:]==b'\xa5'*256,'guards differ');depth=struct.unpack('<3072f',data[256:-256]);need(all(v in (0.,1.) for v in depth) and depth[0]==1.,'depth values');
   for i in range(15):
    xx=8+12*(i%5);yy=24+(6 if generation else 12)*(1-i//5);need(depth[yy*64+xx]==(1. if mode=='blank' else 0.),'depth center differs')
   if mode=='blank':need(all(v==1. for v in depth),'blank depth differs')
   images[name]=hashlib.sha256(data).hexdigest()
  if mode=='blank':blanks.append(images)
  else:need(images['private-0.bin']==images['shared-0.bin'] and images['private-1.bin']==images['shared-1.bin'] and images['private-0.bin']!=images['private-1.bin'],'frame generation discrimination');captures.append(images)
  intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'depth_sha256':images})
 need(all(x==captures[0] for x in captures) and blanks[0]==blanks[1] and all(v not in set(blanks[0].values()) for v in captures[0].values()),'direct/adapted/blank mismatch');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(5)),'process overlap')
 result={'status':'PASS_MTKVIEW_ICB_DEPTH','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_library_sha256':sha(build/'vertex.metallib'),'archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'processes':6,'completed_render_buffers':24,'draw_render_buffers':16,'blank_render_buffers':8,'commands_per_draw_render':15,'adapted_packets_checked':120,'depth_floats_checked':73728,'guard_bytes_checked':12288,'last_slot_short_object_refusals':2,'frame_update_generations':2,'same_icb_reused_for_each_frame':True,'private_frame_copy_before_draw':True,'private_copy_negative_control':False,'direct_adapted_depth_identical':True,'blank_depth_all_one':True,'drawable_framebuffer_only':True,'drawable_color_readback':False,'mtkview':True,'layer_attached_to_window':True,'window_visible':True,'window_key':False,'presented_callbacks':callbacks,'nonzero_presented_timestamps':positive,'visible_display_proved':False,'apple_app_executed':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'render_buffers':24,'adapted_packets':120,'presented_callbacks':callbacks,'nonzero_presented_timestamps':positive}))
if __name__=='__main__':main()
