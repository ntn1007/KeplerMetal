#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch one explicitly selected client with the scoped CAS bootstrap.

This is a local experiment, not a security boundary or general Metal driver.
The bootstrap still admits only its qualified library, certificates and GPU.
"""
import argparse, datetime, hashlib, json, os, re, stat, subprocess, sys
from pathlib import Path
import lab_gpu_reservation as reservation_module
import video_metal_resource_observer as profile_module
from lab_gpu_reservation import GPUReservation
from video_metal_resource_observer import check_profile

HEX=re.compile(r'^[0-9a-f]{64}$')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def need(v,s):
 if not v:raise ValueError(s)
def regular(p):
 p=Path(p).resolve(strict=True);need(stat.S_ISREG(p.stat().st_mode),'Expected regular file');return p
def digest_string(s):
 need(isinstance(s,str) and HEX.fullmatch(s) is not None,'Expected lowercase SHA-256');return s
def asset(root,name):
 need(isinstance(name,str) and name and Path(name).name==name and name not in ('.','..'),'Unsafe asset name')
 p=regular(root/name);need(p.parent==root,'Asset escapes root');return p
def signature(p):
 r=subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True,text=True,timeout=20);need(r.returncode==0,'Code signature verification failed')
def prepare(executable,bootstrap,bootstrap_hash,assets,policy,policy_hash,signature_check=signature):
 exe=regular(executable);boot=regular(bootstrap);policy=regular(policy);root=Path(assets).resolve(strict=True);need(root.is_dir(),'Asset directory required')
 digest_string(bootstrap_hash);digest_string(policy_hash);need(sha(boot)==bootstrap_hash,'Bootstrap hash mismatch')
 need(policy.stat().st_size<=65536 and sha(policy)==policy_hash,'Policy hash or size mismatch')
 try:spec=json.loads(policy.read_bytes())
 except (ValueError,UnicodeDecodeError) as e:raise ValueError('Policy JSON invalid') from e
 need(type(spec) is dict and set(spec)=={'version','allowed_clients'} and type(spec['version']) is int and spec['version']==1,'Policy schema invalid')
 clients=spec['allowed_clients'];need(type(clients) is list and 1<=len(clients)<=16,'Policy client count invalid')
 for x in clients:digest_string(x)
 need(len(set(clients))==len(clients),'Duplicate policy client');exe_hash=sha(exe);need(exe_hash in clients,'Executable not authorized')
 manifest=asset(root,'client-manifest.json');need(manifest.stat().st_size<=65536,'Manifest too large')
 try:doc=json.loads(manifest.read_bytes())
 except (ValueError,UnicodeDecodeError) as e:raise ValueError('Manifest JSON invalid') from e
 need(type(doc) is dict and type(doc.get('profiles')) is list and len(doc['profiles'])==5,'Manifest profiles invalid')
 library=asset(root,doc.get('library'));digest_string(doc.get('library_SHA256'));need(sha(library)==doc['library_SHA256'],'Library hash mismatch')
 seen=set();checked={str(manifest):sha(manifest),str(library):sha(library)}
 for row in doc['profiles']:
  need(type(row) is dict and isinstance(row.get('function'),str) and row['function'] not in seen,'Manifest function invalid');seen.add(row['function'])
  cert=asset(root,row.get('certificate'));expected=digest_string(row.get('certificate_SHA256'));need(sha(cert)==expected,'Certificate hash mismatch');checked[str(cert)]=expected
 signature_check(exe);signature_check(boot)
 checked.update({str(exe):exe_hash,str(boot):bootstrap_hash,str(policy):policy_hash})
 return {'executable':str(exe),'executable_SHA256':exe_hash,'bootstrap':str(boot),'bootstrap_SHA256':bootstrap_hash,'assets':str(root),'policy':str(policy),'policy_SHA256':policy_hash,'inputs':checked}
def arg_hash(args):return hashlib.sha256(json.dumps(args,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def launch(prepared,mode,args,reservation,receipt):
 need(mode in ('native','optin'),'Unsupported mode');root=Path(reservation).resolve(strict=True);receipt=Path(receipt).absolute();need(not receipt.exists() and receipt.parent.is_dir(),'Fresh receipt directory required')
 profile=check_profile();runtime={str(Path(p).resolve()):sha(p) for p in (__file__,reservation_module.__file__,profile_module.__file__)};receipt.mkdir(mode=0o700);lease=GPUReservation(root);child=None;outcome_saved=False
 env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_'))}
 if mode=='optin':env.update(DYLD_INSERT_LIBRARIES=prepared['bootstrap'],KM_CAS_ASSET_PATH=prepared['assets'],KM_CAS_POLICY_PATH=prepared['policy'],KM_CAS_POLICY_SHA256=prepared['policy_SHA256'],KM_CAS_EVENT_PATH=str(receipt/'events.json'))
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();app=prepared['executable'];exe_hash=prepared['executable_SHA256'];registry=root/'results/signed-native-jobs.json'
 try:
  lease.spawning(app,exe_hash)
  with open(receipt/'execution.stdout','x',opener=lambda p,f:os.open(p,f,0o600)) as out,open(receipt/'execution.stderr','x',opener=lambda p,f:os.open(p,f,0o600)) as err:
   child=subprocess.Popen([app,*args],stdout=out,stderr=err,env=env,pass_fds=(lease.fd,));lease.bind_child(child.pid)
   jobs=json.loads(registry.read_text()) if registry.exists() else []
   jobs.append({'started_at':started,'pid':child.pid,'signed_executable':app,'signed_binary_sha256':exe_hash});registry.write_text(json.dumps(jobs,indent=2)+'\n')
   code=child.wait()
  ps=subprocess.run(['ps','-o','pid=,lstart=,command=','-p',str(child.pid)],capture_output=True,text=True,timeout=10).stdout.strip()
  lease.finish(code,False,ps);outcome_saved=True;terminal=dict(lease.data)
  unchanged={}
  for name,digest in {**prepared['inputs'],**runtime}.items():
   try:unchanged[name]=sha(name)==digest
   except OSError:unchanged[name]=False
  try:profile_unchanged=check_profile()==profile
  except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):profile_unchanged=False
  result={'status':'TERMINAL' if terminal['state']=='terminal' else 'UNRESOLVED','mode':mode,'pid':child.pid,'exit_code':code,'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'arguments_SHA256':arg_hash(args),'executable_SHA256':exe_hash,'bootstrap_SHA256':prepared['bootstrap_SHA256'],'policy_SHA256':prepared['policy_SHA256'],'profile':profile,'profile_unchanged':profile_unchanged,'runtime_SHA256':runtime,'GPU_reservation':terminal,'inputs_unchanged':unchanged,'system_modified':False}
  with open(receipt/'manifest.json','x',opener=lambda p,f:os.open(p,f,0o600)) as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
  return result
 except BaseException:
  if not outcome_saved:lease.finish(-1 if child is None else None,False,'' if child is None else 'launcher interrupted; child outcome unresolved')
  raise
 finally:lease.close()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--executable',required=True);p.add_argument('--bootstrap',required=True);p.add_argument('--bootstrap-sha256',required=True);p.add_argument('--assets',required=True);p.add_argument('--policy',required=True);p.add_argument('--policy-sha256',required=True);p.add_argument('--reservation',required=True);p.add_argument('--receipt',required=True);p.add_argument('--mode',choices=['native','optin'],required=True);p.add_argument('--check-only',action='store_true');p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
 try:
  prepared=prepare(a.executable,a.bootstrap,a.bootstrap_sha256,a.assets,a.policy,a.policy_sha256)
  if a.check_only:
   check_profile();print(json.dumps({'status':'PREFLIGHT_PASS','profile_checked':True,'executable_SHA256':prepared['executable_SHA256'],'policy_SHA256':prepared['policy_SHA256'],'bootstrap_SHA256':prepared['bootstrap_SHA256']}));return 0
  args=a.arguments[1:] if a.arguments and a.arguments[0]=='--' else a.arguments
  r=launch(prepared,a.mode,args,a.reservation,a.receipt);print(json.dumps({'status':r['status'],'exit_code':r['exit_code'],'receipt':str(Path(a.receipt).absolute())}));return 0 if r['status']=='TERMINAL' and r['exit_code']==0 and r['profile_unchanged'] and all(r['inputs_unchanged'].values()) else 1
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:print('CAS launcher refused:',str(e),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
