#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit overlapping GTX draws with depth writes enabled and disabled."""
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
 p.add_argument('--runs',type=Path,nargs=4,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==4,'fresh output / distinct runs')
 sample=a.sample.resolve();need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','sample archive differs');build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build/archive')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs')
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build asset differs')
 need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'profiles.json')==sha(HERE/'profiles.json') and sha(build/'vertex.metallib')==sha(sample/'apple.metallib')=='adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf','client/library differs');sign(build/'application')
 intervals=[];rows=[];captures=[];names=('write_on','write_off','clear_zero')
 for path,mode in zip(a.runs,('direct','auto','direct','auto')):
  root=path.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(root/'application')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system')
  x=load(root/'stdout.json');need(x['status']=='PASS' and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['mode']==mode and [c['case'] for c in x['cases']]==list(names) and all(c['completed'] and c['guard_bytes']==512 for c in x['cases']),'client report');events=[e for e in x['events'] if e['operation']=='execute_CPU_render_ICB'];need(len(events)==(3 if mode=='auto' else 0),'ICB event count');images={}
  for i,name in enumerate(names):
   if mode=='auto':
    ev=events[i]['evidence'];need(events[i]['executed_indices']==[0,1] and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==2,'ICB event');meshes=[];shared=[]
    for slot,entry in enumerate(ev['sequence_records']):
     meta=entry['record'];packet=base64.b64decode(entry['commands_base64'],validate=True);prefix=base64.b64decode(entry['prefix_base64'],validate=True);expected_prefix=(0xa0040eb0,0x405,0x900,3,0x3f800000,0xa0010eac,0) if slot==0 else (0xa0010eac,0);need(meta['name']=='apple_explicit_view' and meta['vertex_count']==3 and meta['base_instance']==0 and meta['library_SHA256']==b['files_sha256']['vertex.metallib'] and meta['manifest_SHA256']==b['files_sha256']['profiles.json'] and len(meta['bindings'])==3 and struct.unpack('<6I',packet)==(0xa0050ea8,4,3,1,0,0) and hashlib.sha256(packet).hexdigest()==meta['SHA256'] and struct.unpack('<%dI'%(len(prefix)//4),prefix)==expected_prefix and hashlib.sha256(prefix).hexdigest()==entry['prefix_SHA256'],'packet/prefix');meshes.append(meta['bindings'][0]['GPU_address']);shared.append(tuple(v['GPU_address'] for v in meta['bindings'][1:]))
    need(meshes[0]!=meshes[1] and shared[0]==shared[1],'resource identity')
   data=(root/'outputs'/f'{name}.bin').read_bytes();need(len(data)==12800 and data[:256]==data[-256:]==b'\xa5'*256,'guards differ');color=(bytes((0,191,64,255)),bytes((0,64,191,255)),bytes(4))[i];need(data[256:-256]==color*3072,'pixel oracle');images[name]=hashlib.sha256(data).hexdigest()
  need(len(set(images.values()))==3,'controls not discriminating');captures.append(images);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'images_sha256':images})
 need(all(x==captures[0] for x in captures),'direct/adapted/repeated images differ');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'process overlap')
 result={'status':'PASS_APPLE_DEPTH_DEPENDENCY','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_library_sha256':sha(build/'vertex.metallib'),'archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'processes':4,'completed_render_buffers':12,'color_bytes_checked':147456,'guard_bytes_checked':6144,'adapted_packets_checked':12,'two_draws_same_depth':True,'write_on_preserves_first':True,'write_off_allows_second':True,'clear_zero_rejects_both':True,'depth_texture_cpu_readback':False,'direct_adapted_raw_images_identical':True,'apple_app_executed':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'render_buffers':12,'adapted_packets':12}))
if __name__=='__main__':main()
