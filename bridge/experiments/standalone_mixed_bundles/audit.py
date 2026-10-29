#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit pinned app/bundle default Metal-library GPU witnesses offline."""
from pathlib import Path
import argparse,json,plistlib,struct,subprocess,sys
from collections import Counter
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,sha,write

def need(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--runs',type=Path,nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(len(a.runs)==25 and a.out.parent.is_dir() and not a.out.exists(),'25 runs and fresh output required');meta=check_library(a.library);b=read(a.build/'build.json');need(b['status']=='PREPARED' and b['library_sha256']==meta['static_library_SHA256'] and all(sha(a.build/n)==h for n,h in b['files_sha256'].items()),'build differs')
 for n,src in [('client.mm',HERE/'client.mm'),('bootstrap.mm',HERE/'bootstrap.mm'),('workload.inc',BRIDGE/'experiments/public_mixed_client/client.mm'),('wrong_compute.metal',HERE/'wrong_compute.metal'),('wrong_render.metal',HERE/'wrong_render.metal')]:need(sha(a.build/n)==sha(src),'source differs')
 nm=subprocess.run(['nm','-u',str(a.build/'application')],capture_output=True,text=True,timeout=15);need(nm.returncode==0 and 'KPCPU' not in nm.stdout and 'Kepler' not in nm.stdout,'project imports')
 prior=read(a.prior);need(prior['status']=='PASS_PUBLIC_MIXED_METAL_CLIENT_GPU','prior differs');registry=prior['rows'][0]['GPU_identity']['registry_id']
 rows=[];seen=Counter();ids=[];intervals=[];groups={}
 for path in a.runs:
  e=read(path/'execution.json');v=read(path/'verification.json');mode=e['mode'];c=e['compute_route'];r=e['render_route'];need(c in ('main','file') and r in ('bundle','file') and v['mode']==mode and v['compute_route']==c and v['render_route']==r,'route differs');seen[(mode,c,r)]+=1
  negative=mode in ('wrong-client','wrong-manifest','bad-descriptor','wrong-compute','wrong-render');expected=3 if mode in ('wrong-client','wrong-manifest') else 1 if negative else 0
  need(v['status']=='PASS' and e['exit_code']==e['expected_exit_code']==expected and e['reservation']['state']=='terminal' and not e['reservation']['SIGKILL_requested'] and not e['reservation']['authoritative_ps_status'],'process outcome')
  app=b['files_sha256']['wrong-application' if mode=='wrong-client' else 'application'];host=path/'Probe.app/Contents/MacOS/application';need(sha(host)==e['host_sha256']==app and e['build_sha256']==sha(a.build/'build.json') and e['stdout_sha256']==sha(path/'stdout.json') and e['stderr_sha256']==sha(path/'stderr.log') and e['driver_before_sha256']==e['driver_after_sha256'],'provenance')
  source=a.build/('wrong-application' if mode=='wrong-client' else 'application');need(subprocess.run(['codesign','--verify','--strict',str(source)],capture_output=True,timeout=15).returncode==0,'source signature')
  need(e['bundle_files_sha256_before']==e['bundle_files_sha256_after'] and all(not (path/n).is_symlink() and sha(path/n)==h for n,h in e['bundle_files_sha256_before'].items()),'bundle resources differ')
  names={'Probe.app/Contents/Info.plist','Probe.app/Contents/Resources/default.metallib','Render.bundle/Contents/Info.plist','Render.bundle/Contents/Resources/default.metallib'};need(set(e['bundle_files_sha256_before'])==names,'bundle inventory differs')
  main=plistlib.loads((path/'Probe.app/Contents/Info.plist').read_bytes());render=plistlib.loads((path/'Render.bundle/Contents/Info.plist').read_bytes());need(main.get('CFBundleExecutable')=='application' and main.get('CFBundlePackageType')=='APPL' and render.get('CFBundlePackageType')=='BNDL','bundle plists differ')
  need(sha(path/'Probe.app/Contents/Resources/default.metallib')==b['files_sha256']['wrong_compute.metallib' if mode=='wrong-compute' else 'compute.metallib'] and sha(path/'Render.bundle/Contents/Resources/default.metallib')==b['files_sha256']['wrong_render.metallib' if mode=='wrong-render' else 'render.metallib'],'default library differs')
  if mode!='direct':need(e['bootstrap_sha256']==b['files_sha256']['bootstrap.dylib'] and subprocess.run(['codesign','--verify','--strict',str(a.build/'bootstrap.dylib')],capture_output=True,timeout=15).returncode==0,'bootstrap mismatch')
  log=(path/'stderr.log').read_text();hashes=None
  if not negative:
   d=read(path/'stdout.json');need(d['status']=='PASS' and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==registry and d['loader_routes']==[c,r] and d['compute_segments']==d['render_segments']==0 and d['client']['command_status']==4 and d['created_pipelines_by_public_API'] and d['client']['same_command_buffer'] and d['client']['no_cpu_read_between_compute_render'],'client outcome')
   if mode!='direct':
    need(all(log.count(x)==1 for x in ('KM_MIX enabled','KM_MIX queue matched','KM_MIX compute pipeline matched','KM_MIX render pipeline matched','KM_MIX '+c+' library compute matched','KM_MIX '+r+' library render matched')),'loader evidence')
    ev=read(path/'events.json');n=lambda name:sum(x.get('operation')==name for x in ev);need(n('executeCommandsInBuffer')==n('execute_CPU_render_ICB')==n('scope_restore')==1 and n('automatic_compute_encoder')>=1 and n('automatic_render_encoder')>=1,'indirect evidence');need(all(x.get('device_class_restored') for x in ev if x.get('operation')=='scope_restore') and n('automatic_compute_factories_restored')==n('automatic_render_factories_restored')==1 and all(x.get('queue_class_restored') for x in ev if x.get('operation') in ('automatic_compute_factories_restored','automatic_render_factories_restored')),'restore')
   pix=(path/'outputs/pixels.bin').read_bytes();idx=(path/'outputs/indices.bin').read_bytes();ctr=(path/'outputs/counter.bin').read_bytes();need(len(pix)==49664 and len(idx)==128 and len(ctr)==132,'output size');need(pix[:256]==pix[-256:]==b'\xa5'*256 and idx[:64]==b'\xa5'*64 and idx[80:]==b'\xa5'*48 and ctr[:64]==ctr[68:]==b'\xa5'*64,'guards')
   prod=mode!='no-producer';draw=mode in ('direct','auto');need(struct.unpack_from('<I',ctr,64)[0]==(32 if prod else 0) and struct.unpack_from('<4I',idx,64)==((0,1,2,0x4521) if prod else (0,0,0,0x77777777)),'compute')
   for y in range(48):
    for x in range(64):need(struct.unpack_from('<4f',pix,256+16*(y*64+x))==((.75,.125,.25,1.) if draw and 3<=x<16 and 4<=y<13 else (0.,0.,0.,0.)),'pixel mismatch')
   hashes=tuple(sha(path/'outputs'/name) for name in ('pixels.bin','indices.bin','counter.bin'));groups.setdefault(mode,[]).append(hashes)
  elif mode in ('wrong-compute','wrong-render'):
   route=c if mode=='wrong-compute' else r;ev=read(path/'events.json');need('KM_MIX '+route+' library unapproved, native fallback' in log and ('Pipeline is not owned by this registered scope' if mode=='wrong-compute' else 'Render pipeline is not owned by this scope') in log and not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in ev) and v['gpu_execution'] and not v['user_compute_render_executed'],'wrong library')
  elif mode=='bad-descriptor':
   ev=read(path/'events.json');need('render descriptor not qualified; native fallback' in log and 'Render pipeline is not owned by this scope' in log and not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in ev) and v['gpu_execution'] and not v['user_compute_render_executed'],'descriptor')
  else:need('KM_MIX identity refused' in log and not (path/'events.json').exists() and not list((path/'outputs').iterdir()) and not v['gpu_execution'],'identity')
  ids.append(e['reservation']['reservation_id']);intervals.append((e['started_at'],e['completed_at']));rows.append({'mode':mode,'compute_route':c,'render_route':r,'exit_code':expected,'reservation_id':ids[-1],'pixel_sha256':hashes[0] if hashes else None,'bundle_file_hashes':e['bundle_files_sha256_before'],'terminal':True})
 expected=Counter()
 for mode in ('direct','auto'):
  for c in ('main','file'):
   for r in ('bundle','file'):expected[(mode,c,r)]=2
 for mode in ('no-producer','no-render'):expected[(mode,'main','bundle')]=2
 for mode in ('wrong-compute','wrong-render','wrong-client','wrong-manifest','bad-descriptor'):expected[(mode,'main','bundle')]=1
 need(seen==expected,'cohort coverage');need(len(set(groups['direct']+groups['auto']))==1 and len({x[0] for x in groups['no-producer']+groups['no-render']})==1 and groups['auto'][0][0]!=groups['no-render'][0][0],'outputs differ')
 intervals.sort();need(len(set(ids))==25 and all(intervals[i][1]<=intervals[i+1][0] for i in range(24)),'reservation overlap')
 result={'status':'PASS_STANDALONE_DEFAULT_BUNDLE_LIBRARIES_GPU','processes':25,'output_processes':20,'expected_refusals':5,'compute_render_route_combinations':4,'checked_float_channels':20*64*48*4,'same_output_all_direct_auto':True,'client_no_kepler_imports_checked':True,'explicit_process_injection_required':True,'app_bundle_code_signed_as_unit':False,'executable_signature_checked_outside_bundle':True,'unmodified_third_party_application':False,'full_ICB_contract':False,'hardware_video_execution_proved':False,'system_modified':False,'performance_benchmark':False,'negative_initialization_blit_executed_for_wrong_libraries_and_descriptor':True,'runtime_sha256':meta['static_library_SHA256'],'prior_receipt_sha256':sha(a.prior),'client_source_sha256':sha(HERE/'client.mm'),'bootstrap_source_sha256':sha(HERE/'bootstrap.mm'),'current_runner_source_sha256':sha(HERE/'experiment.py'),'runner_source_pinned_per_run':False,'audit_sha256':sha(Path(__file__)),'rows':rows}
 write(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
