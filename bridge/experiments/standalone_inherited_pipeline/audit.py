#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit public-client inherited ICB captures and scoped refusal controls."""
import argparse,base64,hashlib,json,math,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
 if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def image(p):
 raw=p.read_bytes();need(len(raw)==49664 and raw[:256]==raw[-256:]==b'\xa5'*256,'guard differs');values=struct.unpack('<12288f',raw[256:-256]);need(all(math.isfinite(x) for x in values),'nonfinite image')
 for y in range(48):
  for x in range(64):
   q=values[(y*64+x)*4:(y*64+x)*4+4];need(q[3]==1,'alpha differs')
   if 16<=x<32:need(q==(1.,0.,0.,1.),'flat differs')
   if 48<=x<64:need(q==(0.,1.,0.,1.),'caller vertex differs')
   if x<16 or 32<=x<48:need(all(0<=v<=1 for v in q[:3]) and abs(sum(q[:3])-1)<1e-6,'smooth differs')
 return raw
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','archive','m1','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--runs',type=Path,nargs=8,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==8,'fresh output / distinct runs')
 build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'archive/build provenance')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs')
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build input differs '+n)
 for n in ('client.mm','bootstrap.mm'):need(sha(build/n)==sha(HERE/n),'source differs')
 need('Kepler' not in (build/'client-imports.txt').read_text() and 'KPCPU' not in (build/'client-imports.txt').read_text(),'project imports');sign(build/'application');sign(build/'bootstrap.dylib')
 modes=('direct','auto','direct','auto','native','wrong-client','wrong-manifest','wrong-library');codes=(0,0,0,0,1,3,3,1);intervals=[];rows=[];captures=[]
 for root,mode,code in zip(a.runs,modes,codes):
  root=root.resolve();m=load(root/'manifest.json');lease=m['reservation'];expected=b['files_sha256']['wrong-application' if mode=='wrong-client' else 'application'];injected=mode not in ('direct','native')
  need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==m['expected_exit_code']==code and m['host_sha256']==sha(root/'application')==expected and m['build_sha256']==sha(build/'build.json') and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(root/'application')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==code and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
  need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log') and m['bootstrap_sha256']==(sha(build/'bootstrap.dylib') if injected else None),'logs/system/bootstrap')
  log=(root/'stderr.log').read_text();intervals.append((m['started_at'],m['completed_at']));row={'mode':mode,'manifest_sha256':sha(root/'manifest.json')}
  if mode in ('direct','auto'):
   report=load(root/'stdout.json');need(report['status']=='PASS' and report['device']=='NVIDIA GeForce GTX 880M' and report['mode']==('icb' if injected else 'direct') and report['cases'][0]['completed'],'client result');raw=image(root/'outputs/image.bin');captures.append(raw);row['image_sha256']=hashlib.sha256(raw).hexdigest()
   if injected:
    need('registered pipeline smooth matched' in log and 'registered pipeline flat matched' in log and m['events_sha256']==sha(root/'events.json'),'bootstrap evidence');events=load(root/'events.json');records=[e for e in events if e['operation']=='execute_CPU_render_ICB'];need(len(records)==3,'execution count')
    for e,name in zip(records,('smooth','flat','smooth')):
     ev=e['evidence'];need(e['executed_indices']==[0] and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'record');entry=ev['sequence_records'][0];raw_packet=base64.b64decode(entry['commands_base64'],validate=True);need(entry['record']['name']==name and struct.unpack('<6I',raw_packet)==(0xa0050ea8,4,3,1,1,0) and hashlib.sha256(raw_packet).hexdigest()==entry['record']['SHA256'],'packet')
  else:
   need(not list((root/'outputs').iterdir()),'negative produced image');needle={'native':'newIndirectCommandBufferWithDescriptor:maxCount:options:','wrong-client':'identity refused','wrong-manifest':'transform identity refused','wrong-library':'shader functions missing'}[mode];need(needle in log,'control reason differs')
  rows.append(row)
 need(all(x==captures[0] for x in captures),'GTX images differ');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(7)),'overlap')
 m1=a.m1.resolve();m1direct=load(m1/'direct.json');m1icb=load(m1/'icb.json');need(m1direct['status']==m1icb['status']=='PASS' and m1direct['device']==m1icb['device']=='Apple M1 Max' and m1direct['mode']=='direct' and m1icb['mode']=='icb','M1 result');m1raw=image(m1/'direct.bin');need(image(m1/'icb.bin')==m1raw,'M1 direct/native differ');provenance=(m1/'provenance.txt').read_text();need(sha(HERE/'client.mm') in provenance and sha(build/'transform.metallib') in provenance and hashlib.sha256(m1raw).hexdigest() in provenance and 'arm64' in provenance,'M1 transfer provenance')
 result={'status':'PASS_PUBLIC_CLIENT_INHERITED_PIPELINE','archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'public_client_sha256':sha(build/'application'),'no_project_symbol_imports':True,'gtx_processes':8,'gtx_completed_images':4,'gtx_refusal_controls':4,'gtx_checked_float_channels':49152,'gtx_guard_bytes':2048,'gtx_direct_adapted_exact':True,'m1_direct_native_icb_match':True,'m1_image_sha256':hashlib.sha256(m1raw).hexdigest(),'m1_provenance_sha256':sha(m1/'provenance.txt'),'m1_raw_float_bits_match_gtx':m1raw==captures[0],'m1_capture_not_gtx_execution':True,'full_icb_contract':False,'third_party_client':False,'transparent_system_integration':False,'performance_benchmark':False,'checked_system_files_unchanged':True,'runs':rows}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'gtx_completed_images':4,'gtx_refusal_controls':4}))
if __name__=='__main__':main()
