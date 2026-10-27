#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-oracle and receipt audit for six scoped CAS-launcher hosts."""
import argparse,copy,hashlib,json,shutil,struct,tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from launch_certified_cas import arg_hash,sha

def read(p):return json.loads(Path(p).read_text())
def need(v,s):
 if not v:raise ValueError(s)
def check_manifest(m,mode,exe,boot,policy,profile,args):
 l=m['GPU_reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['profile']==profile and m['profile_unchanged'] and not m['system_modified'] and all(m['inputs_unchanged'].values()),'Host/profile state')
 need(m['executable_SHA256']==exe and m['bootstrap_SHA256']==boot and m['policy_SHA256']==policy and m['arguments_SHA256']==arg_hash(args),'Input identity')
 need(l['state']=='terminal' and l['child_PID']==m['pid'] and l['child_birth_observed'] and l['signed_binary_sha256']==exe and not l['SIGKILL_requested'] and not l['authoritative_ps_status'] and not l['known_signed_processes_live'],'Lease state')

def oracle(d,out,mode):
 names=['sdk_cas_expected','sdk_cas_slot','sdk_cas_noise','sdk_cas_swizzle','sdk_keep_comparand'];need(d['device']=='NVIDIA GeForce GTX 880M' and d['factory']=='mixed' and not d['system_modified'] and [x['function'] for x in d['proofs']]==names and [x['factory'] for x in d['proofs']]==['basic','options-none','reflection-full','descriptor-default','basic'] and len(d['runs'])==30,'Client matrix')
 correct=wrong=guards=0;seen=set()
 for r in d['runs']:
  local=r['local'];groups=r['groups'];variant=r['variant'];iteration=r['iteration'];n=local*groups
  need(local in (33,128,1024) and groups==3 and variant in (0,1) and iteration==0 and r['seed']==0x2468 and r['committed'] and r['command_status']==4,'Dispatch identity')
  need(r['function'] in names and r['candidate']==(r['function']!=names[4]) and r['layout']==('noise' if r['function']==names[2] else 'permuted' if r['function']==names[3] else 'standard'),'Dispatch profile')
  key=(r['function'],local,variant,iteration);need(key not in seen,'Duplicate dispatch');seen.add(key)
  need(r['file']==f"{r['function']}-l{local}-v{variant}-i{iteration}.bin",'Output path differs');raw=(out/r['file']).read_bytes();need(len(raw)==n*16+128 and raw[:64]==raw[-64:]==b'\xa5'*64,'Guard mismatch');guards+=128
  values=[struct.unpack_from('<4I',raw,64+16*x) for x in range(n)]
  if r['layout']=='permuted':values=[(x[1],x[2],x[3],x[0]) for x in values]
  need([sum(values[x][1]==1 for x in range(g*local,(g+1)*local)) for g in range(3)]==([0]*3 if variant else [1]*3),'CAS winner mismatch')
  errors=0
  for k,row in enumerate(values):
   old,success,final,index=row;need(success in (0,1),'CAS success mismatch');seed=r['seed'];initial=(seed+(k//local)*0x10001)&0xffffffff;replacement=seed^0x55667788
   wanted_old=(initial^(1 if variant else 0)) if not r['candidate'] else (initial if variant or success else replacement)
   wanted_final=initial if variant else replacement;wanted_index=(k^(((seed*0x9e3779b9)&0xffffffff)^(k*17))) if r['layout']=='noise' else k
   target=(wanted_old,success,wanted_final,wanted_index);need(row[1:]==target[1:],'CAS state mismatch');errors+=sum(a!=b for a,b in zip(row,target))
  if mode=='native' and r['candidate']:need(errors>0,'Native defect absent');wrong+=errors
  else:need(errors==0,'GPU/CPU mismatch');correct+=n
 need(len(seen)==30,'Incomplete dispatch matrix');return {'correct_CAS_operations':correct,'expected_native_defect_words':wrong,'guard_bytes':guards,'dispatches':30}

def audit(build,runs):
 need(len(runs)==len(set(runs))==6,'Six distinct receipts required');i=read(build/'inputs.json');assets=build/'assets';boot=sha(assets/'bootstrap.dylib');manifest=read(assets/'client-manifest.json');certs={r['function']:r['certificate_SHA256'] for r in manifest['profiles']};rows=[];intervals=[];pids=set();refs=[];labels=[];samples=[]
 runtime_expected={str((Path(__file__).parent/n).resolve()):sha(Path(__file__).parent/n) for n in ('launch_certified_cas.py','lab_gpu_reservation.py','video_metal_resource_observer.py')}
 for receipt in runs:
  m=read(receipt/'manifest.json');d=read(receipt/'execution.stdout');mode=m['mode'];tag=d['client_tag'];need(tag in ('A','B') and mode in ('native','optin') and d['registry_id']==4294968416,'Target differs');exe=i['executable_SHA256'] if tag=='A' else i['executable_B_SHA256'];policy=sha(assets/('policy-a.json' if tag=='A' else 'policy-ab.json'));out=receipt.with_name(receipt.name+'-output');args=[str(assets/'cas_client.metallib'),str(out),'run']
  check_manifest(m,mode,exe,boot,policy,i['profile'],args);need(m['runtime_SHA256']==runtime_expected and all(sha(p)==h for p,h in m['runtime_SHA256'].items()),'Launcher changed');need(sha(build/('application' if tag=='A' else 'application-b'))==exe and sha(assets/'bootstrap.dylib')==boot,'Binary changed')
  trace=(receipt/'execution.stderr').read_text()
  if mode=='native':need(not (receipt/'events.json').exists() and not trace,'Native trace differs')
  else:
   e=read(receipt/'events.json');need(e['client_SHA256']==exe and e['policy_SHA256']==policy and e['identity']['registry_id']==d['registry_id'] and e['identity']['PCI_vendor_id']==0x10de and e['identity']['PCI_device_id']==0x1198 and not e['system_modified'],'Bootstrap identity')
   need([x['function'] for x in e['events']]==[x['function'] for x in d['proofs'][:4]] and [x['factory'] for x in e['events']]==['basic','options-none','reflection-full','descriptor-default'] and trace.count('KM_CAS repaired ')==4 and trace.count('KM_CAS descriptor accepted ')==1,'Bootstrap selection')
   for x in e['events']:
    p=x['proof'];n=p['native_import'];need(p['function']==x['function'] and p['certificate_SHA256']==certs[x['function']] and p['library_SHA256']==manifest['library_SHA256'] and p['gate_accepted'] and p['immutable_library_data'] and p['constructor_restored'] and n['contract_verified'] and n['registry_id']==d['registry_id'] and n['target_imports']==n['verified_imports']>0,'Import evidence')
  result=oracle(d,out,mode);refs.append(d['proofs']);labels.append((mode,tag));need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));samples.append((m,mode,exe,policy,args));rows.append({'mode':mode,'client':tag,'manifest_SHA256':sha(receipt/'manifest.json'),'stdout_SHA256':sha(receipt/'execution.stdout'),'events_SHA256':sha(receipt/'events.json') if mode=='optin' else None,**result})
 need(Counter(labels)==Counter({('native','A'):1,('native','B'):1,('optin','A'):2,('optin','B'):2}),'Coverage differs');need(all(x==refs[0] for x in refs[1:]) and len(refs[0][2]['arguments'])==3,'Reflection differs');changed=copy.deepcopy(refs);changed[1][2]['arguments'][0]['index']+=1;need(changed[1]!=changed[0],'Reflection mutation accepted')
 optreceipt=next(r for r in runs if read(r/'manifest.json')['mode']=='optin');optdata=read(optreceipt/'execution.stdout')
 with tempfile.TemporaryDirectory(prefix='km-cas-oracle-') as temporary:
  altered=Path(temporary)/'outputs';shutil.copytree(optreceipt.with_name(optreceipt.name+'-output'),altered);target=altered/optdata['runs'][0]['file'];raw=bytearray(target.read_bytes());raw[64]^=1;target.write_bytes(raw)
  try:oracle(optdata,altered,'optin')
  except ValueError:pass
  else:raise ValueError('Corrupted GPU output accepted')
 intervals.sort();need(all(a<=b for a,b in intervals) and all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'Overlap');m,mode,exe,policy,args=samples[0];bad=copy.deepcopy(m);bad['GPU_reservation']['state']='unresolved'
 try:check_manifest(bad,mode,exe,boot,policy,i['profile'],args)
 except ValueError:pass
 else:raise ValueError('Unresolved receipt accepted')
 return {'status':'PASS','hosts':6,'native_dispatches':sum(x['dispatches'] for x in rows if x['mode']=='native'),'native_defect_words':sum(x['expected_native_defect_words'] for x in rows),'optin_dispatches':sum(x['dispatches'] for x in rows if x['mode']=='optin'),'corrected_and_control_CAS_operations':sum(x['correct_CAS_operations'] for x in rows if x['mode']=='optin'),'selected_reflection_equal':True,'mutated_output_rejected':True,'unresolved_receipt_rejected':True,'rows':rows,'launcher_SHA256':runtime_expected[str((Path(__file__).parent/'launch_certified_cas.py').resolve())],'bootstrap_SHA256':boot,'system_modified':False,'scope':'Two builds of one test client and one certified library; no general application or system-wide qualification'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--receipts',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh audit required');r=audit(a.build.resolve(),[x.resolve() for x in a.receipts]);
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in r.items() if k!='rows'}))
if __name__=='__main__':main()
