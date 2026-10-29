#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe ordinary Metal resource reply fields; no video selector is sent."""
import argparse,datetime,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from video_metal_resource_observer import check_profile
from public_large_scratch import preflight,sha,write
from lab_gpu_reservation import GPUReservation,process_table

def need(x,m):
 if not x:raise ValueError(m)
def command(out,label,argv):
 r=subprocess.run(list(map(str,argv)),capture_output=True,timeout=120);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);need(r.returncode==0,label+' failed')
def build(a):
 out=a.out.resolve();preflight(out);profile=check_profile();out.mkdir();shutil.copyfile(HERE/'host.mm',out/'host.mm');shutil.copyfile(HERE/'experiment.py',out/'runner.py')
 common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-Wno-deprecated-declarations'];lib=out/'libObserver.dylib'
 command(out,'library',common+['-DKP_OBSERVER_LIBRARY','-dynamiclib',out/'host.mm','-framework','Foundation','-framework','IOKit','-install_name',lib,'-o',lib]);command(out,'library-sign',['codesign','--force','--sign','-',lib]);command(out,'library-verify',['codesign','--verify','--strict',lib]);command(out,'host',common+[out/'host.mm',lib,'-framework','Foundation','-framework','IOKit','-framework','Metal','-o',out/'application']);command(out,'host-sign',['codesign','--force','--sign','-',out/'application']);command(out,'host-verify',['codesign','--verify','--strict',out/'application'])
 files=['host.mm','runner.py','application','libObserver.dylib'];write(out/'build.json',{'profile':profile,'uid':os.getuid(),'files':{x:sha(out/x) for x in files},'gpu_execution':False});print(json.dumps({'status':'BUILD_PASS','gpu_execution':False}))
def run(a):
 out=a.out.resolve();b=a.build.resolve();preflight(out);meta=json.loads((b/'build.json').read_text());need(all(sha(b/n)==h for n,h in meta['files'].items()) and sha(HERE/'host.mm')==meta['files']['host.mm'] and sha(HERE/'experiment.py')==meta['files']['runner.py'],'frozen input differs');need(meta['profile']==check_profile() and meta['uid']==os.getuid(),'profile changed');need(a.mode=='inventory' or a.registry_id>0,'registry ID required')
 lease=GPUReservation(a.lab.resolve());child=None;terminal=False
 try:
  out.mkdir();shutil.copyfile(b/'application',out/'application');host=out/'application';host.chmod(0o755);command(out,'host-verify',['codesign','--verify','--strict',host]);command(out,'lib-verify',['codesign','--verify','--strict',b/'libObserver.dylib']);rid=0 if a.mode=='inventory' else a.registry_id
  env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KP_','KM_'))};start=datetime.datetime.now(datetime.timezone.utc).isoformat();lease.spawning(host,sha(host))
  with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
   child=subprocess.Popen([str(host),a.mode,str(rid)],stdout=stdout,stderr=stderr,env=env,pass_fds=(lease.fd,));lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','mode':a.mode,'pid':child.pid}),flush=True)
   try:code=child.wait(timeout=30)
   except subprocess.TimeoutExpired:lease.finish(None,False,'child outcome unresolved');raise RuntimeError('do not retry; inspect exact child')
  need(child.pid not in process_table(),'child still live');terminal=True;lease.finish(code,False,'');after=check_profile();record={'mode':a.mode,'pid':child.pid,'exit_code':code,'started_at':start,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'host_sha256':sha(host),'build_sha256':sha(b/'build.json'),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'profile_unchanged':after==meta['profile']};write(out/'execution.json',record)
  need(code==0 and record['profile_unchanged'],'host/profile differs');result=json.loads((out/'stdout.json').read_text());need(result['pid']==child.pid and not result['dropped'] and not result['observer_inflight_final'] and not result['explicit_GPU_commands'],'host status differs')
  if a.mode=='inventory':
   candidates=[x for x in result['services'] if x['gpu_ancestor'] and not x['class_status'] and not x['registry_status']];need(len(candidates)==1,'GPU ambiguous');proof={'registry_id':candidates[0]['registry_ID']}
  elif a.mode=='control':
   es=result['events'];need(result['status']=='CONTROL_RECORDED' and result['control_open_status']==result['control_close_status']==0 and all(any(e['kind']==kind and e['port']==0 and e['status']!=0 for e in es) for kind in ('method','struct')),'control failed');proof={'interposition_calibrated':True}
  elif a.mode=='baseline':
   need(result['status']=='WARM_COMPARISON_RECORDED' and result['warm_created'] and not result['target_created'] and result['cpu_bytes_correct'],'baseline differs');proof={'baseline_pass':True}
  else:
   q=result['reply_identity'];c=q['comparison'];need(result['status']=='WARM_COMPARISON_RECORDED' and result['target_length']==4194304 and result['cpu_bytes_correct'] and q['status']=='PINNED' and q['resource_fields_read'] and not q['getter_called'] and c['captured_qualified_reply_count']==c['matching_pairs']==1 and c['wrong_value_matches']==0 and not c['raw_addresses_exported'] and result['selected_reply_fields_captured_in_memory'] and not result['raw_payload_exported'],'resource response mismatch');proof={'one_response_matches_live_wrapper':True,'wrong_value_refused':True}
  proof.update({'status':'PASS','mode':a.mode,'reservation_id':lease.data['reservation_id'],'explicit_gpu_commands':False,'hardware_video_execution_proved':False,'system_modified':False});write(out/'verification.json',proof);print(json.dumps(proof,sort_keys=True))
 except BaseException:
  if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'terminal outcome not established')
  raise
 finally:lease.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(required=True);b=sub.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build);r=sub.add_parser('run')
 for n in ('build','lab','out'):r.add_argument('--'+n,type=Path,required=True)
 r.add_argument('--mode',choices=['inventory','control','baseline','large'],required=True);r.add_argument('--registry-id',type=int,default=0);r.set_defaults(func=run);a=p.parse_args();a.func(a)
