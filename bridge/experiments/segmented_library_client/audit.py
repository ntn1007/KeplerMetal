#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently check segmented library clients, launcher receipts and GPU output."""
import argparse, datetime, hashlib, json, struct, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v, why):
 if not v: raise ValueError(why)
def arg_hash(a): return hashlib.sha256(json.dumps(a,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--foreign',type=Path,required=True);p.add_argument('--native',type=Path,nargs=2,required=True);p.add_argument('--optin',type=Path,nargs=2,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 b=a.build.resolve();paths=[a.foreign.resolve(),*[x.resolve() for x in a.native],*[x.resolve() for x in a.optin]];need(len(set(paths))==5,'Distinct receipts required');need(not a.out.exists() and a.out.parent.is_dir(),'Fresh audit path required')
 i=read(b/'inputs.json');need(sha(HERE/'client.mm')==i['frozen']['src/client.mm'],'Client source differs')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'Build differs: '+n)
 for file in ('application','assets/bootstrap.dylib'):subprocess.run(['codesign','--verify','--strict',str(b/file)],check=True,capture_output=True)
 symbols=subprocess.run(['nm','-u',str(b/'application')],check=True,capture_output=True,text=True).stdout;need('Kepler' not in symbols and 'KPCreate' not in symbols,'Project symbols found')
 policy=read(b/'policy.json');need(policy=={'version':1,'allowed_clients':[i['application_SHA256']]},'Policy differs')
 manifest=read(b/'assets/client-manifest.json');profile=next(r for r in manifest['profiles'] if r['function']=='sdk_cas_noise');need(profile['candidate'],'Noise profile not a candidate')
 rows=[];intervals=[];pids=set()
 for path in paths:
  foreign=path==paths[0];mode='native' if path in paths[1:3] else 'optin';r=read(path/'manifest.json');lease=r['GPU_reservation'];out=Path(str(path)+'-output');client=read(path/'execution.stdout');trace=(path/'execution.stderr').read_text()
  need(r['status']=='TERMINAL' and r['mode']==mode and r['exit_code']==0 and r['profile']==i['profile'] and r['profile_unchanged'] and all(r['inputs_unchanged'].values()),'Launcher receipt differs')
  need(lease['state']=='terminal' and lease['child_PID']==r['pid'] and lease['signed_binary_sha256']==r['executable_SHA256']==i['application_SHA256'] and not lease['known_signed_processes_live'] and not lease['authoritative_ps_status'] and not lease['SIGKILL_requested'],'Reservation differs')
  need(r['bootstrap_SHA256']==i['bootstrap_SHA256'] and r['policy_SHA256']==i['policy_SHA256'],'Policy or bootstrap differs')
  for name in ('launch_certified_cas.py','lab_gpu_reservation.py','video_metal_resource_observer.py'):
   matches=[h for k,h in r['runtime_SHA256'].items() if Path(k).name==name];need(matches==[sha(BRIDGE/'tools'/name)],'Launcher source differs: '+name)
  args=[str(b/'assets'/('wrong.metallib' if foreign else 'cas_client.metallib')),str(out),'construct' if foreign else 'run'];need(r['arguments_SHA256']==arg_hash(args),'Client arguments differ')
  need(client['device']=='NVIDIA GeForce GTX 880M' and client['registry_id']==4294968416 and client['segments']>=2 and client['library_bytes']==(b/'assets'/('wrong.metallib' if foreign else 'cas_client.metallib')).stat().st_size,'Client identity or segments differ')
  need(r['pid'] not in pids,'Duplicate PID');pids.add(r['pid']);intervals.append((datetime.datetime.fromisoformat(r['started_at']),datetime.datetime.fromisoformat(r['completed_at'])))
  if foreign:
   need(client['mode']=='construct' and not client['runs'] and not list(out.iterdir()) and 'KM_CAS data library unapproved' in trace and 'KM_CAS repaired' not in trace and not read(path/'events.json')['events'],'Foreign library control differs')
   rows.append({'mode':'foreign','segments':client['segments'],'dispatches':0});continue
  need(client['mode']=='run' and len(client['runs'])==18,'Client matrix differs')
  if mode=='native':need(not trace and not (path/'events.json').exists(),'Native run modified')
  else:
   e=read(path/'events.json');need(e['client_SHA256']==i['application_SHA256'] and e['policy_SHA256']==i['policy_SHA256'] and e['identity']['registry_id']==client['registry_id'] and e['identity']['PCI_vendor_id']==0x10de and e['identity']['PCI_device_id']==0x1198,'Bootstrap identity differs')
   need(trace.count('KM_CAS data library matched')==1 and trace.count('KM_CAS repaired sdk_cas_noise')==1 and len(e['events'])==1,'Data loading or repair trace differs')
   ev=e['events'][0];proof=ev['proof'];imp=proof['native_import'];need(ev['function']=='sdk_cas_noise' and ev['factory']=='basic' and proof['certificate_SHA256']==profile['certificate_SHA256'] and proof['library_SHA256']==manifest['library_SHA256'] and proof['gate_accepted'] and proof['immutable_library_data'] and proof['constructor_restored'] and imp['contract_verified'] and imp['target_imports']==imp['verified_imports']==1 and imp['driver_sha256']==manifest['driver_SHA256'],'Import proof differs')
   need(any(x.get('code_replaced') and all(x.get(k) for k in ('expected_original_code_identical','native_metadata_identical_to_certificate','imported_code_identical','native_metadata_preserved_except_instruction_count','code_input_unchanged_after_constructor')) for x in imp['events']),'Constructor evidence differs')
  combinations=set();wrong=operations=0;indices=set()
  for case in client['runs']:
   local,groups,variant,iteration,seed=(case[k] for k in ('local','groups','variant','iteration','seed'));need(local in (33,128,1024) and groups==3 and variant in (0,1) and iteration in (0,1,2) and seed==0x2468+53*iteration and case['command_status']==4,'Run parameters differ')
   key=(local,variant,iteration);need(key not in combinations,'Duplicate dispatch');combinations.add(key);indices.update((seed+g)&3 for g in range(groups))
   name=f'case-{local}-{variant}-{iteration}.bin';need(case['file']==name,'Output path differs');data=(out/name).read_bytes();n=local*groups;need(len(data)==n*16+128 and data[:64]==data[-64:]==b'\xa5'*64,'Output guards differ');winners=[0]*groups
   for k in range(n):
    old,success,final,index=struct.unpack_from('<4I',data,64+16*k);need(success in (0,1),'Invalid success flag');g=k//local;winners[g]+=success;initial=(seed+g*0x10001)&0xffffffff;replacement=seed^0x55667788
    expected_old=initial if variant or success else replacement;expected_final=initial if variant else replacement;expected_index=(k^(((seed*0x9e3779b9)&0xffffffff)^(k*17)))&0xffffffff
    need(final==expected_final and index==expected_index,'Final value or neighboring sentinel differs');wrong+=old!=expected_old;operations+=1
   need(winners==([0,0,0] if variant else [1,1,1]),'Winner counts differ')
  need(len(combinations)==18 and indices=={0,1,2,3} and operations==21330 and wrong==(21303 if mode=='native' else 0),'CAS results differ')
  need({x.name for x in out.iterdir()}=={x['file'] for x in client['runs']},'Extra or missing output')
  rows.append({'mode':mode,'segments':client['segments'],'dispatches':len(client['runs']),'operations':operations,'incorrect_expected_words':wrong,'stdout_SHA256':sha(path/'execution.stdout')})
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Overlapping processes')
 result={'status':'PASS','client_SHA256':i['application_SHA256'],'bootstrap_SHA256':i['bootstrap_SHA256'],'policy_SHA256':i['policy_SHA256'],'host_processes':len(rows),'nonoverlapping':True,'segmented_regions_min':min(x['segments'] for x in rows),'repaired_CAS_operations':sum(x['operations'] for x in rows if x['mode']=='optin'),'repaired_dispatches':sum(x['dispatches'] for x in rows if x['mode']=='optin'),'native_incorrect_expected_words':sum(x['incorrect_expected_words'] for x in rows if x['mode']=='native'),'foreign_library_user_dispatches':0,'rows':rows,'scope':'Separate purpose-built client using a known certified shader; not an independently supplied application or general Metal support.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
