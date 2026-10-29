#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck Apple shader CPU ICB results, bounds refusals and GTX packets."""
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
 for n in ('sample','build','archive','baseline','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--runs',type=Path,nargs=4,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==4,'fresh output / distinct runs')
 sample=a.sample.resolve();need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','sample archive differs')
 build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build/archive')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs')
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build asset differs')
 need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'profiles.json')==sha(HERE/'profiles.json') and sha(build/'vertex.metallib')==sha(sample/'apple.metallib')=='adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf','client/library differs');sign(build/'application')
 intervals=[];rows=[];captures=[];order=((False,0),(False,1),(True,0),(True,1))
 for path,mode in zip(a.runs,('direct','auto','direct','auto')):
  root=path.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(root/'application')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system')
  x=load(root/'stdout.json');need(x['status']=='PASS' and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['mode']==mode and len(x['cases'])==4 and x['refusals']==(5 if mode=='auto' else 0),'client report');events=[e for e in x['events'] if e['operation']=='execute_CPU_render_ICB'];need(len(events)==(4 if mode=='auto' else 0),'event count');images={}
  for idx,(item,(private,base)) in enumerate(zip(x['cases'],order)):
   need(item['private_frame']==private and item['base_instance']==base and item['completed'] and item['checked_channels']==12288 and item['guard_bytes']==512,'case differs')
   if mode=='auto':
    event=events[idx];ev=event['evidence'];need(event['executed_indices']==[0] and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'ICB event');entry=ev['sequence_records'][0];meta=entry['record'];packet=base64.b64decode(entry['commands_base64'],validate=True);need(meta['name']=='apple_explicit' and meta['vertex_count']==3 and meta['vertex_start']==0 and meta['instances']==1 and meta['base_instance']==base and meta['library_SHA256']==b['files_sha256']['vertex.metallib'] and meta['manifest_SHA256']==b['files_sha256']['profiles.json'] and len(meta['bindings'])==3 and meta['bindings'][2]['storage_mode']==(2 if private else 0) and struct.unpack('<6I',packet)==(0xa0050ea8,4,3,1,0,base) and hashlib.sha256(packet).hexdigest()==meta['SHA256'],'ICB packet/metadata')
   name=('private' if private else 'shared')+'-'+str(base)+'.bin';data=(root/'outputs'/name).read_bytes();need(len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256,'guards differ');values=struct.unpack('<12288f',data[256:-256]);color=(0.,0.,0.,0.) if base else (.25,.75,0.,1.);need(all(v==color[i%4] for i,v in enumerate(values)),'pixels differ');images[name]=hashlib.sha256(data).hexdigest()
  need(images['private-0.bin']==images['shared-0.bin'] and images['private-1.bin']==images['shared-1.bin'] and images['private-0.bin']!=images['private-1.bin'],'frame/base discrimination');captures.append(images);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'images_sha256':images})
 need(all(x==captures[0] for x in captures),'direct/adapted/repeated images differ');baseline=a.baseline.resolve();bm=load(baseline/'manifest.json');bl=bm['reservation'];need(bm['status']=='TERMINAL' and bm['mode']=='direct' and bm['exit_code']==0 and bm['host_sha256']==sha(baseline/'application') and bm['stdout_sha256']==sha(baseline/'stdout.json') and bm['stderr_sha256']==sha(baseline/'stderr.log') and bm['system_before']==bm['system_after']==SYSTEM and bl['state']=='terminal' and bl['child_PID']==bm['pid'] and not bl['SIGKILL_requested'] and not bl['authoritative_ps_status'],'native baseline provenance');sign(baseline/'application');need(all(sha(baseline/'outputs'/name)==digest for name,digest in captures[0].items()),'native baseline differs');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'process overlap')
 result={'status':'PASS_APPLE_EXPLICIT_CPU_ICB','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_library_sha256':sha(build/'vertex.metallib'),'archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'processes':4,'completed_render_buffers':16,'float_channels_checked':196608,'guard_bytes_checked':8192,'expected_bounds_refusals':10,'adapted_packets_checked':8,'private_frame_copy_before_draw':True,'private_copy_negative_control':False,'base_instance_values':[0,1],'same_raw_pixels_direct_adapted_and_native_baseline':True,'apple_app_executed':False,'general_explicit_shaders_supported':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'completed_render_buffers':16,'expected_bounds_refusals':10}))
if __name__=='__main__':main()
