#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and execute one pinned public Metal application with process-local opt-in."""
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'));sys.path.insert(0,str(BRIDGE/'experiments/public_mixed_client'))
from public_large_scratch import check_library,check_driver_profile,preflight,sha,write
from lab_gpu_reservation import GPUReservation,process_table
from experiment import verify_pixels
C='7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911';R='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7';M='225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be'
def need(b,m):
 if not b:raise ValueError(m)
def command(label,cmd,out):
 x=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=120);(out/(label+'.stdout')).write_bytes(x.stdout);(out/(label+'.stderr')).write_bytes(x.stderr);need(x.returncode==0,label+' failed');return x

def build(a):
 out=a.out.resolve();lib=a.library.resolve();preflight(out);meta=check_library(lib)
 for path,h in [(a.compute,C),(a.render,R),(BRIDGE/'src/cpu_icb_gpu_indices.json',M)]:need(sha(path)==h,'asset differs')
 out.mkdir()
 for path,name in [(HERE/'client.mm','client.mm'),(HERE/'bootstrap.mm','bootstrap.mm'),(BRIDGE/'experiments/public_mixed_client/client.mm','workload.inc'),(a.compute,'compute.metallib'),(a.render,'render.metallib'),(BRIDGE/'src/cpu_icb_gpu_indices.json','manifest.json')]:shutil.copyfile(path,out/name)
 common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc']
 command('client',common+[out/'client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'],out)
 nm=command('imports',['nm','-u',out/'application'],out).stdout.decode();need('Kepler' not in nm and 'KPCPU' not in nm,'client imports project')
 command('client-sign',['codesign','--force','--sign','-',out/'application'],out);command('client-verify',['codesign','--verify','--strict',out/'application'],out);app=sha(out/'application')
 raw=(out/'application').read_bytes();need(raw.count(b'no device\n')==1,'negative app mutation differs');(out/'wrong-application').write_bytes(raw.replace(b'no device\n',b'No device\n'));(out/'wrong-application').chmod(0o755);command('wrong-sign',['codesign','--force','--sign','-',out/'wrong-application'],out);command('wrong-verify',['codesign','--verify','--strict',out/'wrong-application'],out);need(sha(out/'wrong-application')!=app,'negative app unchanged')
 bad=bytearray((out/'manifest.json').read_bytes());bad[0]^=1;(out/'wrong-manifest.json').write_bytes(bad)
 command('bootstrap',common+['-dynamiclib','-I',lib/'src','-DKM_APPROVED_APP_SHA256="'+app+'"',out/'bootstrap.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'bootstrap.dylib'],out)
 command('bootstrap-sign',['codesign','--force','--sign','-',out/'bootstrap.dylib'],out);command('bootstrap-verify',['codesign','--verify','--strict',out/'bootstrap.dylib'],out)
 names=['client.mm','bootstrap.mm','workload.inc','compute.metallib','render.metallib','manifest.json','wrong-manifest.json','application','wrong-application','bootstrap.dylib'];write(out/'build.json',{'status':'PREPARED','gpu_execution':False,'library_sha256':meta['static_library_SHA256'],'files_sha256':{n:sha(out/n) for n in names},'system_modified':False});print(json.dumps({'status':'BUILD_PASS','application_sha256':app,'gpu_execution':False}))

def run(a):
 out=a.out.resolve();b=a.build.resolve();preflight(out);before=check_driver_profile();build=json.loads((b/'build.json').read_text());need(build['status']=='PREPARED' and all(sha(b/n)==h for n,h in build['files_sha256'].items()),'build differs')
 for n,source in [('client.mm',HERE/'client.mm'),('bootstrap.mm',HERE/'bootstrap.mm'),('workload.inc',BRIDGE/'experiments/public_mixed_client/client.mm')]:need(sha(b/n)==sha(source),'source differs')
 lease=GPUReservation(a.lab.resolve());child=None;terminal=False
 try:
  out.mkdir();(out/'outputs').mkdir();shutil.copyfile(b/('wrong-application' if a.mode=='wrong-client' else 'application'),out/'application');host=out/'application';host.chmod(0o755);command('host-verify',['codesign','--verify','--strict',host],out)
  env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};injected=a.mode!='direct'
  if injected:
   command('bootstrap-verify',['codesign','--verify','--strict',b/'bootstrap.dylib'],out);env.update({'DYLD_INSERT_LIBRARIES':str(b/'bootstrap.dylib'),'KM_COMPUTE_PATH':str(b/'compute.metallib'),'KM_RENDER_PATH':str(b/'render.metallib'),'KM_MANIFEST_PATH':str(b/('wrong-manifest.json' if a.mode=='wrong-manifest' else 'manifest.json')),'KM_EVENT_PATH':str(out/'events.json')})
  client_mode=a.mode if a.mode in ('direct','no-producer','no-render','bad-descriptor') else 'icb';args=[str(b/'compute.metallib'),str(b/'render.metallib'),str(out/'outputs'),client_mode]
  lease.spawning(host,sha(host));start=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
   child=subprocess.Popen([str(host),*args],stdout=stdout,stderr=stderr,env=env,pass_fds=(lease.fd,));lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','mode':a.mode,'pid':child.pid}),flush=True)
   try:code=child.wait(timeout=30)
   except subprocess.TimeoutExpired:
    lease.finish(None,False,'child not reaped after timeout');raise RuntimeError('child outcome unresolved; do not retry without checking the process')
  need(child.pid not in process_table(),'child still present');terminal=True;lease.finish(code,False,'')
  expected=3 if a.mode in ('wrong-client','wrong-manifest') else 1 if a.mode=='bad-descriptor' else 0;record={'mode':a.mode,'exit_code':code,'expected_exit_code':expected,'pid':child.pid,'started_at':start,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'host_sha256':sha(host),'bootstrap_sha256':sha(b/'bootstrap.dylib') if injected else None,'build_sha256':sha(b/'build.json'),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'driver_before_sha256':before,'driver_after_sha256':check_driver_profile()};write(out/'execution.json',record);need(code==expected and record['driver_after_sha256']==before,'exit or driver differs')
  log=(out/'stderr.log').read_text();positive=a.mode in ('direct','auto','no-producer','no-render')
  if positive:
   d=json.loads((out/'stdout.json').read_text());need(d['status']=='PASS' and d['created_pipelines_by_public_API'] and d['client']['command_status']==4,'client status')
   if injected:
    need(all(log.count(x)==1 for x in ['KM_MIX enabled','KM_MIX compute pipeline matched','KM_MIX render pipeline matched','KM_MIX library compute matched','KM_MIX library render matched']),'bootstrap match missing')
    events=json.loads((out/'events.json').read_text());n=lambda name:sum(x.get('operation')==name for x in events);need(n('automatic_compute_encoder')>=1 and n('automatic_render_encoder')>=1 and n('executeCommandsInBuffer')==1 and n('execute_CPU_render_ICB')==1 and n('scope_restore')==1,'scope events differ')
   proof=verify_pixels(out,'icb' if a.mode=='auto' else a.mode)
  elif a.mode=='bad-descriptor':
   events=json.loads((out/'events.json').read_text());need('render descriptor not qualified; native fallback' in log and 'Render pipeline is not owned by this scope' in log and
     not any(x.get('operation') in ('executeCommandsInBuffer','execute_CPU_render_ICB') for x in events) and not list((out/'outputs').iterdir()),'bad descriptor control differs');proof={'unsupported_descriptor_refused_before_main_work':True}
  else:
   need('KM_MIX identity refused' in log and not (out/'events.json').exists() and not list((out/'outputs').iterdir()),'identity refusal missing');proof={'identity_refused_before_scope':True}
  proof.update({'status':'PASS','mode':a.mode,'expected_exit_code':expected,'signed_client_sha256':sha(host),'bootstrap_sha256':record['bootstrap_sha256'],'reservation_id':lease.data['reservation_id'],'gpu_execution':positive or a.mode=='bad-descriptor','user_compute_render_executed':positive,'system_modified':False});write(out/'verification.json',proof);print(json.dumps(proof,sort_keys=True))
 except BaseException:
  if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
  raise
 finally:lease.close()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build')
 for n in ('library','compute','render','out'):b.add_argument('--'+n,type=Path,required=True)
 b.set_defaults(func=build);r=sub.add_parser('run')
 for n in ('build','lab','out'):r.add_argument('--'+n,type=Path,required=True)
 r.add_argument('--mode',choices=['direct','auto','no-producer','no-render','wrong-client','wrong-manifest','bad-descriptor'],required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
