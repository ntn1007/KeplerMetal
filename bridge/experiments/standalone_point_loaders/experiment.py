#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run a public Metal library routes with process-local opt-in."""
import argparse,datetime,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,why):
 if not v:raise ValueError(why)
def cmd(args):
 r=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120);need(r.returncode==0,str(args[0])+' failed: '+r.stderr[-2500:]);return r.stdout

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 b=sub.add_parser('build')
 for n in ('lab','archive','legacy','shader','wrong-shader','manifest','out'):b.add_argument('--'+n,type=Path,required=True)
 r=sub.add_parser('run')
 for n in ('lab','build','out'):r.add_argument('--'+n,type=Path,required=True)
 r.add_argument('--mode',choices=('direct','native','auto','wrong-client','wrong-manifest','wrong-library','bad-descriptor'),required=True);r.add_argument('--route',choices=('file','url','data','segmented'),required=True)
 a=p.parse_args();lab=a.lab.resolve();out=a.out.resolve();out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required');before={k:sha(k) for k in SYSTEM};need(before==SYSTEM,'system differs')
 if a.action=='build':
  archive=a.archive.resolve();m=json.loads((archive/'manifest.json').read_text());need(m['status']=='PASS' and not m['GPU_execution'] and sha(archive/'libKeplerMetal.a')==m['static_library_SHA256'],'archive differs')
  for n,h in m['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs: '+n)
  pins={'carrier.metallib':(a.legacy,'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'),'transform.metallib':(a.shader,'0bd90c4639674a1542e535b06c56a47d550f6784a2bd127278d55b0c393438ae'),'wrong-transform.metallib':(a.wrong_shader,'6a1febcbae0b2099d01a401ae2b8c275c5896226c61b3eaefa314cf3de81595d'),'profiles.json':(a.manifest,'74a479ff7dcfa46bb298715a1ccd633ce8503fbf166835487013ac34c86be48a')}
  for source,h in pins.values():need(sha(source)==h,'asset differs')
  out.mkdir();shutil.copyfile(HERE/'client.mm',out/'client.mm');shutil.copyfile(HERE/'bootstrap.mm',out/'bootstrap.mm')
  for n,(source,h) in pins.items():shutil.copyfile(source,out/n)
  bad=bytearray((out/'profiles.json').read_bytes());bad[0]^=1;(out/'wrong-profiles.json').write_bytes(bad)
  cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
  imports=cmd(['nm','-u',out/'application']);need('Kepler' not in imports and 'KPCPU' not in imports,'client imports project symbols');(out/'client-imports.txt').write_text(imports)
  cmd(['codesign','--force','--sign','-',out/'application']);cmd(['codesign','--verify','--strict',out/'application']);app=sha(out/'application');raw=(out/'application').read_bytes();need(raw.count(b'no device\n')==1,'wrong-client mutation differs');wrong=out/'wrong-application';wrong.write_bytes(raw.replace(b'no device\n',b'No device\n',1));wrong.chmod(0o755);cmd(['codesign','--force','--sign','-',wrong]);cmd(['codesign','--verify','--strict',wrong]);need(sha(wrong)!=app,'wrong client identical')
  cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-I',archive/'src','-DKM_APPROVED_APP_SHA256="'+app+'"',out/'bootstrap.mm',archive/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'bootstrap.dylib']);cmd(['codesign','--force','--sign','-',out/'bootstrap.dylib']);cmd(['codesign','--verify','--strict',out/'bootstrap.dylib'])
  record={'status':'PREPARED_ONLY','gpu_execution':False,'system':before,'archive_sha256':m['static_library_SHA256'],'archive_manifest_sha256':sha(archive/'manifest.json'),'files_sha256':{x.name:sha(x) for x in out.iterdir() if x.is_file()}};(out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PREPARED_ONLY'}));return
 build=a.build.resolve();build.relative_to(lab/'results');record=json.loads((build/'build.json').read_text());need(record['status']=='PREPARED_ONLY' and record['system']==before,'build/system differs')
 for n,h in record['files_sha256'].items():need(sha(build/n)==h,'build file differs '+n)
 for n in ('client.mm','bootstrap.mm'):need(sha(build/n)==sha(HERE/n),'source differs '+n)
 leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','lease differs');spec=importlib.util.spec_from_file_location('standalone_transform_reservation',leasepath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);lease=mod.GPUReservation(lab);child=None;terminal=False
 try:
  out.mkdir();(out/'outputs').mkdir();shutil.copyfile(build/('wrong-application' if a.mode=='wrong-client' else 'application'),out/'application');host=out/'application';host.chmod(0o755);cmd(['codesign','--verify','--strict',host]);expected_host=record['files_sha256']['wrong-application' if a.mode=='wrong-client' else 'application'];need(sha(host)==expected_host,'host differs')
  env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};injected=a.mode in ('auto','wrong-client','wrong-manifest','wrong-library','bad-descriptor');bootstrap=build/'bootstrap.dylib'
  if injected:
   cmd(['codesign','--verify','--strict',bootstrap]);env.update({'DYLD_INSERT_LIBRARIES':str(bootstrap),'KM_CARRIER_PATH':str(build/'carrier.metallib'),'KM_TRANSFORM_PATH':str(build/'transform.metallib'),'KM_MANIFEST_PATH':str(build/('wrong-profiles.json' if a.mode=='wrong-manifest' else 'profiles.json')),'KM_EVENT_PATH':str(out/'events.json')})
  library=build/('wrong-transform.metallib' if a.mode=='wrong-library' else 'transform.metallib');clientmode='direct' if a.mode=='direct' else 'icb-bad-mask' if a.mode=='bad-descriptor' else 'icb';args=[str(library),str(out/'outputs'),clientmode,a.route];lease.spawning(host,sha(host));start=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
   child=subprocess.Popen([str(host),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode}),flush=True);code=child.wait()
  table=mod.process_table();need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible');terminal=True;lease.finish(code,False,'');expected=0 if a.mode in ('direct','auto') else 3 if a.mode in ('wrong-client','wrong-manifest') else 8
  result={'status':'TERMINAL','mode':a.mode,'route':a.route,'exit_code':code,'expected_exit_code':expected,'pid':child.pid,'args':args,'started_at':start,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'host_sha256':sha(host),'build_sha256':sha(build/'build.json'),'runner_sha256':sha(Path(__file__)),'bootstrap_sha256':sha(bootstrap) if injected else None,'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'events_sha256':sha(out/'events.json') if (out/'events.json').is_file() else None,'system_before':before,'system_after':{k:sha(k) for k in SYSTEM}}
  (out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');need(code==expected and result['system_after']==SYSTEM,'exit/system differs');print(json.dumps({'status':'TERMINAL','mode':a.mode,'route':a.route,'exit_code':code}),flush=True)
 except BaseException:
  if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
  raise
 finally:lease.close()
if __name__=='__main__':main()
