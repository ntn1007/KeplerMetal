#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline CPU oracle for the standalone public-Metal CAS client."""
import hashlib,json,struct,sys
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(c,s):
 if not c:raise ValueError(s)

def verify(path):
 p=Path(path).resolve();i=read(p/'inputs.json');m=read(p/'execution/manifest.json');mode=i['mode'];lease=m['GPU_reservation']
 require(mode in ('native-a','native-b','optin-a','optin-b','denied-b','wrong-policy','wrong-library','wrong-client','wrong-cert','wrong-descriptor','wrong-data'),'Unknown mode')
 expected=3 if mode in ('wrong-client','wrong-cert','wrong-policy','denied-b') else 0
 require(m['exit_code']==expected and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live'],'Host not terminal')
 require(sha(p/'application')==m['original_binary_sha256']==i['application_SHA256'] and sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'Client identity differs')
 require(m['injected_library_SHA256']==(None if mode.startswith('native-') else i['bootstrap_SHA256']),'Injection differs')
 for name,digest in i['assets_SHA256'].items():require(sha(p/'assets'/name)==digest,'Asset differs: '+name)
 for name,digest in i['frozen'].items():require(sha(p/name)==digest,'Frozen input differs: '+name)
 require(m['launcher_SHA256']==i['frozen']['runtime/run_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'Launcher differs')
 trace=(p/'execution/execution.stderr').read_text();lib='wrong.metallib' if mode in ('wrong-library','wrong-data') else 'cas_client.metallib';client_mode='construct-data' if mode=='wrong-data' else 'construct' if mode=='wrong-library' else 'unsupported' if mode=='wrong-descriptor' else 'run-data' if mode in ('native-b','optin-b') else 'run'
 require(m['arguments']==[str(p/'assets'/lib),str(p/'outputs'),client_mode],'Arguments differ')
 if mode in ('wrong-client','wrong-cert','wrong-policy','denied-b'):
  require(not (p/'events.json').exists() and not (p/'execution/execution.stdout').read_text() and 'KM_CAS enabled' not in trace,'Rejected client executed')
  require(('KM_CAS policy refused' if mode=='wrong-policy' else 'KM_CAS certificate refused' if mode=='wrong-cert' else 'KM_CAS identity refused') in trace,'Expected refusal absent')
  if mode=='wrong-policy':require(sha(p/'assets'/i['policy_name'])!=i['policy_expected_SHA256'],'Changed policy not detected')
  if mode=='denied-b':require(sha(p/'assets'/i['policy_name'])==i['policy_expected_SHA256'] and i['application_SHA256'] not in read(p/'assets'/i['policy_name'])['allowed_clients'],'Unlisted client control differs')
  return {'status':'PASS','mode':mode,'user_GPU_dispatches':0,'hardware_execution':False}
 d=read(p/'results.json');require(d==read(p/'execution/execution.stdout') and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==i['registry_id'] and not d['system_modified'] and d['client_tag']==i['client_tag'],'Client result differs')
 names=['sdk_cas_expected','sdk_cas_slot','sdk_cas_noise','sdk_cas_swizzle','sdk_keep_comparand'];require([x['function'] for x in d['proofs']]==names and (mode=='wrong-descriptor' or all(x['pipeline_max_threads']>=1024 for x in d['proofs'])),'Pipelines differ')
 if mode in ('wrong-library','wrong-data'):
  require(d['client_mode']==client_mode and not d['runs'] and ('KM_CAS data library unapproved' if mode=='wrong-data' else 'KM_CAS library unapproved') in trace and 'KM_CAS repaired' not in trace,'Foreign library was adapted')
  require(not read(p/'events.json')['events'],'Unexpected repairs')
  return {'status':'PASS','mode':mode,'user_GPU_dispatches':0,'hardware_execution':False}
 if mode=='wrong-descriptor':
  require(d['client_mode']=='unsupported' and not d['runs'] and trace.count('KM_CAS descriptor unapproved ')==4 and 'KM_CAS repaired' not in trace and not read(p/'events.json')['events'],'Nondefault descriptor adapted')
  return {'status':'PASS','mode':mode,'user_GPU_dispatches':0,'hardware_execution':False}
 expected_factories=['basic','options-none','reflection-full','descriptor-default','basic']
 require(d['client_mode']==client_mode and d['factory']=='mixed' and [x['factory'] for x in d['proofs']]==expected_factories and len(d['runs'])==90,'Dispatch count or factory differs')
 require(d['proofs'][2]['reflection_present'] and len(d['proofs'][2]['arguments'])==3 and all(not x['reflection_present'] for j,x in enumerate(d['proofs']) if j!=2),'Reflection coverage differs')
 if mode.startswith('native-'):require(not (p/'events.json').exists() and not trace,'Native baseline changed')
 else:
  require(('KM_CAS data library matched' in trace)==(mode=='optin-b'),'Library loading path differs')
  e=read(p/'events.json');require(e['client_SHA256']==i['application_SHA256'] and e['policy_SHA256']==i['policy_expected_SHA256'] and sha(p/'assets'/i['policy_name'])==i['policy_expected_SHA256'],'Policy provenance differs');require(e['identity']['registry_id']==i['registry_id'] and e['identity']['PCI_vendor_id']==0x10de and e['identity']['PCI_device_id']==0x1198,'PCI identity differs')
  require([x['function'] for x in e['events']]==names[:4] and [x['factory'] for x in e['events']]==expected_factories[:4] and trace.count('KM_CAS repaired ')==4 and trace.count('KM_CAS native control ')==1 and trace.count('KM_CAS descriptor accepted ')==1,'Repair selection differs')
  manifest=read(p/'assets/client-manifest.json');pins={x['function']:x['certificate_SHA256'] for x in manifest['profiles']}
  for x in e['events']:
   proof=x['proof'];native=proof['native_import'];require(proof['function']==x['function'] and proof['certificate_SHA256']==pins[x['function']] and proof['library_SHA256']==manifest['library_SHA256'] and proof['gate_accepted'] and proof['immutable_library_data'] and proof['constructor_restored'] and native['contract_verified'] and native['registry_id']==i['registry_id'] and native['driver_sha256']==manifest['driver_SHA256'] and native['target_imports']==native['verified_imports']>0,'Import proof differs')
   for event in native['events']:
    if event.get('code_replaced'):require(event['expected_original_code_identical'] and event['native_metadata_identical_to_certificate'] and event['imported_code_identical'] and event['native_metadata_preserved_except_instruction_count'] and event['code_input_unchanged_after_constructor'],'Constructor evidence differs')
 correct=wrong=guards=0
 combinations=set()
 for r in d['runs']:
  local=r['local'];groups=r['groups'];variant=r['variant'];iteration=r['iteration'];n=local*groups
  require(local in (33,128,1024) and groups==3 and variant in (0,1) and iteration in (0,1,2) and r['seed']==0x2468+53*iteration and r['committed'] and r['command_status']==4,'Dispatch shape differs')
  require(r['function'] in names and r['candidate']==(r['function']!='sdk_keep_comparand') and r['layout']==('noise' if r['function']=='sdk_cas_noise' else 'permuted' if r['function']=='sdk_cas_swizzle' else 'standard'),'Dispatch profile differs')
  key=(r['function'],local,variant,iteration);require(key not in combinations,'Duplicate dispatch');combinations.add(key)
  require(r['file']==f"{r['function']}-l{local}-v{variant}-i{iteration}.bin",'Output name differs')
  rel=Path(r['file']);require(not rel.is_absolute() and '..' not in rel.parts,'Invalid output path');raw=(p/'outputs'/rel).read_bytes();require(len(raw)==n*16+128 and raw[:64]==raw[-64:]==b'\xa5'*64,'Output guards differ');guards+=128
  rows=[struct.unpack_from('<4I',raw,64+16*x) for x in range(n)]
  if r['layout']=='permuted':rows=[(x[1],x[2],x[3],x[0]) for x in rows]
  require([sum(rows[x][1]==1 for x in range(g*local,(g+1)*local)) for g in range(3)]==([0]*3 if variant else [1]*3),'Atomic winners differ')
  errors=0
  for k,row in enumerate(rows):
   old,success,final,index=row;require(success in (0,1),'Invalid CAS result');seed=r['seed'];initial=(seed+(k//local)*0x10001)&0xffffffff;replacement=seed^0x55667788
   wanted_old=(initial^(1 if variant else 0)) if not r['candidate'] else (initial if variant or success else replacement)
   wanted_final=initial if variant else replacement;wanted_index=(k^(((seed*0x9e3779b9)&0xffffffff)^(k*17))) if r['layout']=='noise' else k
   target=(wanted_old,success,wanted_final,wanted_index);require(row[1:]==target[1:],'CAS state differs');errors+=sum(a!=b for a,b in zip(row,target))
  if mode.startswith('native-') and r['candidate']:require(errors>0,'Native defect control disappeared');wrong+=errors
  else:require(errors==0,'CPU oracle mismatch');correct+=n
 require(len(combinations)==90,'Dispatch matrix incomplete')
 return {'status':'PASS','mode':mode,'user_GPU_dispatches':90,'correct_CAS_operations':correct,'expected_native_defect_words':wrong,'guard_bytes':guards,'hardware_execution':True,'transparent_system_integration':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
