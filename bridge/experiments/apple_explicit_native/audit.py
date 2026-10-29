#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck Apple shader native images and draw packets on GTX."""
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
 p.add_argument('--runs',type=Path,nargs=2,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==2,'fresh output / distinct runs')
 sample=a.sample.resolve();need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','sample archive differs')
 build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build/archive')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs')
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build asset differs')
 need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'vertex.metallib')==sha(sample/'apple.metallib')=='adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf','client/library differs');sign(build/'application')
 intervals=[];rows=[];captures=[]
 for path in a.runs:
  root=path.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']=='direct' and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(root/'application')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system')
  x=load(root/'stdout.json');need(x['status']=='PASS' and x['device']=='NVIDIA GeForce GTX 880M' and x['registry_id'] and x['mode']=='direct' and len(x['cases'])==4,'client report');images={}
  for item,(private,base) in zip(x['cases'],((False,0),(False,1),(True,0),(True,1))):
   need(item['private_frame']==private and item['base_instance']==base and item['completed'] and item['checked_channels']==12288 and item['guard_bytes']==512,'case differs');packet=base64.b64decode(item['packet_base64'],validate=True);need(struct.unpack('<6I',packet)==(0xa0050ea8,4,3,1,0,base),'draw packet differs')
   name=('private' if private else 'shared')+'-'+str(base)+'.bin';data=(root/'outputs'/name).read_bytes();need(len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256,'guards differ');values=struct.unpack('<12288f',data[256:-256]);color=(0.,0.,0.,0.) if base else (.25,.75,0.,1.);need(all(v==color[i%4] for i,v in enumerate(values)),'pixels differ');images[name]=hashlib.sha256(data).hexdigest()
  need(images['private-0.bin']==images['shared-0.bin'] and images['private-1.bin']==images['shared-1.bin'] and images['private-0.bin']!=images['private-1.bin'],'frame/base discrimination');captures.append(images);intervals.append((m['started_at'],m['completed_at']));rows.append({'manifest_sha256':sha(root/'manifest.json'),'images_sha256':images})
 need(captures[0]==captures[1],'repetition differs');intervals.sort();need(intervals[0][0]<=intervals[0][1]<=intervals[1][0]<=intervals[1][1],'process overlap')
 result={'status':'PASS_APPLE_EXPLICIT_NATIVE_GPU','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_library_sha256':sha(build/'vertex.metallib'),'build_sha256':sha(build/'build.json'),'processes':2,'completed_render_buffers':8,'native_draws':16,'float_channels_checked':98304,'guard_bytes_checked':4096,'private_frame_copy_before_draw':True,'private_copy_negative_control':False,'base_instance_values':[0,1],'expected_base_images_distinct':True,'native_packet_method':'0x3aa0','adapted_icb_tested':False,'apple_app_executed':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'completed_render_buffers':8,'float_channels_checked':98304}))
if __name__=='__main__':main()
