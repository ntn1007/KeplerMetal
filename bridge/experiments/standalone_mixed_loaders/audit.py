#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit two-library public Metal loading routes without GPU work."""
from pathlib import Path
import argparse,json,struct,subprocess,sys
from collections import Counter
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,sha,write
ROUTES=('file','url','data','segmented')
def need(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--runs',type=Path,nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(len(a.runs)==39 and a.out.parent.is_dir() and not a.out.exists(),'39 runs and fresh output required');meta=check_library(a.library);b=read(a.build/'build.json');need(b['status']=='PREPARED' and b['library_sha256']==meta['static_library_SHA256'] and all(sha(a.build/n)==h for n,h in b['files_sha256'].items()),'build differs')
 for n,src in [('client.mm',HERE/'client.mm'),('bootstrap.mm',HERE/'bootstrap.mm'),('workload.inc',BRIDGE/'experiments/public_mixed_client/client.mm'),('wrong_compute.metal',HERE/'wrong_compute.metal'),('wrong_render.metal',HERE/'wrong_render.metal')]:need(sha(a.build/n)==sha(src),'source differs')
 nm=subprocess.run(['nm','-u',str(a.build/'application')],capture_output=True,text=True,timeout=15);need(nm.returncode==0 and 'KPCPU' not in nm.stdout and 'Kepler' not in nm.stdout,'project imports')
 prior=read(a.prior);need(prior['status']=='PASS_PUBLIC_MIXED_METAL_CLIENT_GPU','prior differs');registry=prior['rows'][0]['GPU_identity']['registry_id']
 rows=[];seen=Counter();ids=[];intervals=[];groups={}
 for path in a.runs:
  e=read(path/'execution.json');v=read(path/'verification.json');mode=e['mode'];c=e['compute_route'];r=e['render_route'];need(c in ROUTES and r in ROUTES and v['mode']==mode and v['compute_route']==c and v['render_route']==r,'route differs');seen[(mode,c,r)]+=1
  negative=mode in ('wrong-client','wrong-manifest','bad-descriptor','wrong-compute','wrong-render');expected=3 if mode in ('wrong-client','wrong-manifest') else 1 if negative else 0
  need(v['status']=='PASS' and e['exit_code']==e['expected_exit_code']==expected and e['reservation']['state']=='terminal' and not e['reservation']['SIGKILL_requested'] and not e['reservation']['authoritative_ps_status'],'process outcome')
  app=b['files_sha256']['wrong-application' if mode=='wrong-client' else 'application'];need(sha(path/'application')==e['host_sha256']==app and e['build_sha256']==sha(a.build/'build.json') and e['stdout_sha256']==sha(path/'stdout.json') and e['stderr_sha256']==sha(path/'stderr.log') and e['driver_before_sha256']==e['driver_after_sha256'],'provenance')
  need(subprocess.run(['codesign','--verify','--strict',str(path/'application')],capture_output=True,timeout=15).returncode==0,'application signature')
  if mode!='direct':need(e['bootstrap_sha256']==b['files_sha256']['bootstrap.dylib'] and subprocess.run(['codesign','--verify','--strict',str(a.build/'bootstrap.dylib')],capture_output=True,timeout=15).returncode==0,'bootstrap mismatch')
  log=(path/'stderr.log').read_text();hashes=None
  if not negative:
   d=read(path/'stdout.json');need(d['status']=='PASS' and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==registry and d['loader_routes']==[c,r] and d['client']['command_status']==4 and d['created_pipelines_by_public_API'] and d['client']['same_command_buffer'] and d['client']['no_cpu_read_between_compute_render'],'client outcome')
   for key,route in [('compute_segments',c),('render_segments',r)]:need(d[key]==(2 if route=='segmented' else 1 if route=='data' else 0),'data segments')
   if mode!='direct':
    need(all(log.count(x)==1 for x in ('KM_MIX enabled','KM_MIX queue matched','KM_MIX compute pipeline matched','KM_MIX render pipeline matched','KM_MIX '+('data' if c=='segmented' else c)+' library compute matched','KM_MIX '+('data' if r=='segmented' else r)+' library render matched')),'loader evidence')
    ev=read(path/'events.json');n=lambda s:sum(x.get('operation')==s for x in ev);need(n('executeCommandsInBuffer')==n('execute_CPU_render_ICB')==n('scope_restore')==1 and n('automatic_compute_encoder')>=1 and n('automatic_render_encoder')>=1,'indirect evidence');need(all(x.get('device_class_restored') for x in ev if x.get('operation')=='scope_restore') and all(x.get('queue_class_restored') for x in ev if x.get('operation') in ('automatic_compute_factories_restored','automatic_render_factories_restored')),'restore')
   pix=(path/'outputs/pixels.bin').read_bytes();idx=(path/'outputs/indices.bin').read_bytes();ctr=(path/'outputs/counter.bin').read_bytes();need(len(pix)==49664 and len(idx)==128 and len(ctr)==132,'output size');need(pix[:256]==pix[-256:]==b'\xa5'*256 and idx[:64]==b'\xa5'*64 and idx[80:]==b'\xa5'*48 and ctr[:64]==ctr[68:]==b'\xa5'*64,'guards')
   prod=mode!='no-producer';draw=mode in ('direct','auto');need(struct.unpack_from('<I',ctr,64)[0]==(32 if prod else 0) and struct.unpack_from('<4I',idx,64)==((0,1,2,0x4521) if prod else (0,0,0,0x77777777)),'compute')
   for y in range(48):
    for x in range(64):need(struct.unpack_from('<4f',pix,256+16*(y*64+x))==((.75,.125,.25,1.) if draw and 3<=x<16 and 4<=y<13 else (0.,0.,0.,0.)),'pixel mismatch')
   hashes=tuple(sha(path/'outputs'/name) for name in ('pixels.bin','indices.bin','counter.bin'));groups.setdefault(mode,[]).append(hashes)
  elif mode in ('wrong-compute','wrong-render'):
   route=c if mode=='wrong-compute' else r;route='data' if route=='segmented' else route;ev=read(path/'events.json');need('KM_MIX '+route+' library unapproved, native fallback' in log and ('Pipeline is not owned by this registered scope' if mode=='wrong-compute' else 'Render pipeline is not owned by this scope') in log and not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in ev) and v['gpu_execution'] and not v['user_compute_render_executed'],'wrong-library refusal')
  elif mode=='bad-descriptor':
   ev=read(path/'events.json');need('render descriptor not qualified; native fallback' in log and 'Render pipeline is not owned by this scope' in log and not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in ev) and v['gpu_execution'] and not v['user_compute_render_executed'],'descriptor refusal')
  else:need('KM_MIX identity refused' in log and not (path/'events.json').exists() and not list((path/'outputs').iterdir()) and not v['gpu_execution'],'identity refusal')
  ids.append(e['reservation']['reservation_id']);intervals.append((e['started_at'],e['completed_at']));rows.append({'mode':mode,'compute_route':c,'render_route':r,'exit_code':expected,'reservation_id':ids[-1],'pixel_sha256':hashes[0] if hashes else None,'terminal':True})
 expected=Counter()
 for route in ROUTES:expected[('direct',route,route)]=1;expected[('auto',route,route)]=2
 for c in ROUTES:
  for r in ROUTES:
   if c!=r:expected[('auto',c,r)]=1
 for route in ('file','segmented'):
  for mode in ('no-producer','no-render'):expected[(mode,route,route)]=1
 for route in ROUTES:
  for mode in ('wrong-compute','wrong-render'):expected[(mode,route,route)]=1
 for mode in ('wrong-client','wrong-manifest','bad-descriptor'):expected[(mode,'file','file')]=1
 need(seen==expected,'cohort coverage differs');need(len(set(groups['direct']+groups['auto']))==1 and len({x[0] for x in groups['no-producer']+groups['no-render']})==1 and groups['auto'][0][0]!=groups['no-render'][0][0],'cross-route outputs differ')
 intervals.sort();need(len(set(ids))==39 and all(intervals[i][1]<=intervals[i+1][0] for i in range(38)),'reservation overlap')
 result={'status':'PASS_STANDALONE_TWO_LIBRARY_LOADERS_GPU','processes':39,'output_processes':28,'expected_refusals':11,'compute_render_route_combinations':16,'diagonal_auto_repeats':4,'checked_float_channels':28*64*48*4,'same_output_all_direct_auto':True,'wrong_library_cases':8,'client_no_kepler_imports_checked':True,'explicit_process_injection_required':True,'unmodified_third_party_application':False,'full_ICB_contract':False,'hardware_video_execution_proved':False,'system_modified':False,'performance_benchmark':False,
 'bad_descriptor_and_wrong_library_initialization_blits_executed':True,'negative_user_compute_render_executed':False,'runtime_sha256':meta['static_library_SHA256'],'prior_receipt_sha256':sha(a.prior),'client_source_sha256':sha(HERE/'client.mm'),'bootstrap_source_sha256':sha(HERE/'bootstrap.mm'),'current_runner_source_sha256':sha(HERE/'experiment.py'),'runner_source_pinned_per_run':False,'audit_sha256':sha(Path(__file__)),'rows':rows}
 write(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
