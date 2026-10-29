#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the pinned standalone application cohort offline; never launch GPU work."""
from pathlib import Path
import argparse,json,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,sha,write

def need(b,m):
 if not b:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=20,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');meta=check_library(a.library);b=read(a.build/'build.json');need(b['status']=='PREPARED' and b['library_sha256']==meta['static_library_SHA256'] and all(sha(a.build/n)==h for n,h in b['files_sha256'].items()),'build differs')
 for name,source in [('client.mm',HERE/'client.mm'),('bootstrap.mm',HERE/'bootstrap.mm'),('workload.inc',BRIDGE/'experiments/public_mixed_client/client.mm')]:need(sha(a.build/name)==sha(source),'source differs')
 need(b['files_sha256']['runner.py'] in (sha(HERE/'experiment.py'),sha(HERE/'qualified_runner.py')),'unrecognized runner source')
 nm=subprocess.run(['nm','-u',str(a.build/'application')],capture_output=True,text=True,timeout=15);need(nm.returncode==0 and 'KPCPU' not in nm.stdout and 'Kepler' not in nm.stdout,'client imports project')
 reference=read(a.prior);need(reference['status']=='PASS_PUBLIC_MIXED_METAL_CLIENT_GPU','prior GPU reference differs');registry=reference['rows'][0]['GPU_identity']['registry_id']
 rows=[];ids=[];intervals=[];groups={};seen=[];reflections=[]
 for path in a.runs:
  mode=read(path/'execution.json')['mode'];factory=read(path/'execution.json')['factory'];seen.append((factory,mode))
  e=read(path/'execution.json');v=read(path/'verification.json');negative=mode in ('wrong-client','wrong-manifest','bad-descriptor') or (factory=='options-none' and mode=='auto');expect=3 if mode in ('wrong-client','wrong-manifest') else 1 if negative else 0
  need(e['mode']==v['mode']==mode and e['runner_sha256']==b['files_sha256']['runner.py'] and e['exit_code']==e['expected_exit_code']==expect and v['status']=='PASS' and e['reservation']['state']=='terminal' and not e['reservation']['SIGKILL_requested'] and not e['reservation']['authoritative_ps_status'],'terminal/mode differs')
  expected_app=b['files_sha256']['wrong-application' if mode=='wrong-client' else 'application'];need(sha(path/'application')==e['host_sha256']==expected_app and e['build_sha256']==sha(a.build/'build.json') and e['stdout_sha256']==sha(path/'stdout.json') and e['stderr_sha256']==sha(path/'stderr.log') and e['driver_before_sha256']==e['driver_after_sha256'],'provenance differs')
  sig=subprocess.run(['codesign','--verify','--strict',str(path/'application')],capture_output=True,timeout=15);need(sig.returncode==0,'client signature')
  if mode!='direct':need(e['bootstrap_sha256']==b['files_sha256']['bootstrap.dylib'] and subprocess.run(['codesign','--verify','--strict',str(a.build/'bootstrap.dylib')],capture_output=True,timeout=15).returncode==0,'bootstrap differs')
  log=(path/'stderr.log').read_text()
  if not negative:
   d=read(path/'stdout.json');need(d['status']=='PASS' and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==registry and d['created_pipelines_by_public_API'] and d['client']['command_status']==4 and d['client']['same_command_buffer'] and d['client']['no_cpu_read_between_compute_render'] and d['factory']==factory,'GPU result differs')
   if factory=='reflection':
    expected=[{'name':a['name'],'index':a['index'],'type':0,'active':True,'access':a['access'],'size':a['data_size'],'alignment':a['alignment'],'data_type':a['data_type']} for a in read(a.build/'manifest.json')['functions'][0]['buffers']];need(d['reflection_arguments']==expected,'native reflection differs');reflections.append(d['reflection_arguments'])
   else:need(d['reflection_arguments']==[],'unexpected reflection')
   if mode!='direct':
    need(all(log.count(x)==1 for x in ('KM_MIX enabled','KM_MIX queue matched',('KM_MIX compute pipeline matched' if factory=='plain' else 'KM_MIX options pipeline matched'),'KM_MIX render pipeline matched','KM_MIX library compute matched','KM_MIX library render matched')),'match logs differ')
    events=read(path/'events.json');n=lambda name:sum(x.get('operation')==name for x in events);need(n('automatic_compute_encoder')>=1 and n('automatic_render_encoder')>=1 and n('executeCommandsInBuffer')==1 and n('execute_CPU_render_ICB')==1 and n('scope_restore')==1,'ICB event differs');need(all(x.get('device_class_restored') is True for x in events if x.get('operation')=='scope_restore') and all(x.get('queue_class_restored') is True for x in events if x.get('operation') in ('automatic_compute_factories_restored','automatic_render_factories_restored')) and n('automatic_compute_factories_restored')==n('automatic_render_factories_restored')==1,'restore differs')
   pix=(path/'outputs/pixels.bin').read_bytes();idx=(path/'outputs/indices.bin').read_bytes();counter=(path/'outputs/counter.bin').read_bytes();need(len(pix)==49664 and len(idx)==128 and len(counter)==132,'size differs')
   need(pix[:256]==pix[-256:]==b'\xa5'*256 and idx[:64]==b'\xa5'*64 and idx[80:]==b'\xa5'*48 and counter[:64]==counter[68:]==b'\xa5'*64,'guard differs')
   prod=mode!='no-producer';draw=mode in ('direct','auto');need(struct.unpack_from('<I',counter,64)[0]==(32 if prod else 0) and struct.unpack_from('<4I',idx,64)==((0,1,2,0x4521) if prod else (0,0,0,0x77777777)),'compute differs')
   for y in range(48):
    for x in range(64):need(struct.unpack_from('<4f',pix,256+16*(y*64+x))==((.75,.125,.25,1.) if draw and 3<=x<16 and 4<=y<13 else (0.,0.,0.,0.)),'pixel differs')
   hashes=tuple(sha(path/'outputs'/name) for name in ('pixels.bin','indices.bin','counter.bin'));groups.setdefault(mode,[]).append(hashes)
  elif factory=='options-none' and mode=='auto':
   ev=read(path/'events.json');need('options pipeline native fallback' in log and 'Pipeline is not owned by this registered scope' in log and not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in ev) and v['gpu_execution'] and not v['user_compute_render_executed'],'options refusal differs');hashes=None
  elif mode=='bad-descriptor':
   ev=read(path/'events.json');need('render descriptor not qualified; native fallback' in log and 'Render pipeline is not owned by this scope' in log and not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in ev) and v['gpu_execution'] and not v['user_compute_render_executed'],'descriptor refusal differs');hashes=None
  else:need('KM_MIX identity refused' in log and not (path/'events.json').exists() and not list((path/'outputs').iterdir()),'identity refusal differs');hashes=None
  ids.append(e['reservation']['reservation_id']);intervals.append((e['started_at'],e['completed_at']));rows.append({'factory':factory,'mode':mode,'exit_code':expect,'reservation_id':ids[-1],'signed_client_sha256':e['host_sha256'],'bootstrap_sha256':e['bootstrap_sha256'],'pixel_sha256':hashes[0] if hashes else None,'terminal':True})
 need(all(len(set(x))==1 for x in groups.values()) and groups['direct'][0]==groups['auto'][0] and groups['no-producer'][0][0]==groups['no-render'][0][0] and groups['auto'][0][0]!=groups['no-render'][0][0],'control comparison differs')
 need(len(set(ids))==20 and all(sorted(intervals)[i][1]<=sorted(intervals)[i+1][0] for i in range(19)),'reservation overlap')
 expected_cases=[(f,m) for f in ('plain','reflection','reflection-null') for m in ('direct','auto') for _ in range(2)]+[('reflection',m) for m in ('no-producer','no-render') for _ in range(2)]+[('reflection',m) for m in ('wrong-client','wrong-manifest','bad-descriptor')]+[('options-none','auto')];need(sorted(seen)==sorted(expected_cases) and len(reflections)==8 and all(x==reflections[0] for x in reflections),'case coverage or reflection mismatch')
 result={'status':'PASS_STANDALONE_MIXED_REFLECTION_GPU','processes':20,'gpu_output_processes':16,'expected_refusals':4,'checked_float_channels':196608,'direct_indirect_outputs_match':True,
 'client_creates_libraries_and_pipelines':True,'client_no_kepler_imports_checked':True,'explicit_process_injection_required':True,'unmodified_third_party_application':False,'full_ICB_contract':False,'system_modified':False,'performance_benchmark':False,
 'bad_descriptor_initialization_blit_executed':True,'bad_descriptor_user_compute_render_executed':False,'runtime_sha256':meta['static_library_SHA256'],'prior_receipt_sha256':sha(a.prior),'client_sha256':sha(HERE/'client.mm'),'workload_sha256':sha(BRIDGE/'experiments/public_mixed_client/client.mm'),
 'bootstrap_sha256':sha(HERE/'bootstrap.mm'),'qualified_runner_sha256':b['files_sha256']['runner.py'],'current_runner_sha256':sha(HERE/'experiment.py'),'runner_source_pinned_per_run':True,'audit_sha256':sha(Path(__file__)),'rows':rows}
 write(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
