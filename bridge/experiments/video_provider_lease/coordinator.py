#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe pinned display mask and vector conditions in a user process.
No Sierra export or private GPU selector is called by the gate.
"""
import argparse,hashlib,json,os,pathlib,plistlib,shutil,subprocess,sys
B=pathlib.Path.home()/'Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge'
HERE=pathlib.Path(__file__).resolve().parent
OLD=B/'results/video-alias-native-build-20261027-04'
OLD_MANIFEST='79bf7bbf267b9ea5e3e635b970c67c1a3a59383db58af56f6a31aedc6e9207d7'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def save(p,x):
 with pathlib.Path(p).open('x') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def require(x,s):
 if not x:raise ValueError(s)
def profile():
 sys.path.insert(0,str(OLD/'src'));from video_metal_resource_observer import check_profile
 p=check_profile();rows=plistlib.loads(subprocess.check_output(['ioreg','-a','-w0','-r','-c','nvAccelerator'],timeout=20))
 require(len(rows)==1 and rows[0].get('IORegistryEntryID')==4294968416 and rows[0].get('IORegistryEntryName')=='nvAccelerator','GPU profile changed');return p
def verify_old():
 require(sha(OLD/'inputs.json')==OLD_MANIFEST,'prior build manifest changed')
 data=load(OLD/'inputs.json')
 for p,h in data['frozen'].items():require(sha(OLD/p)==h,'Prior frozen input changed: '+p)
 prior=pathlib.Path(data['old_build']);require(sha(prior/'inputs.json')==data['old_manifest_SHA256'],'Prior manifest changed')
 for p,h in load(prior/'inputs.json')['reused_objects_and_libraries_SHA256'].items():require(sha(p)==h,'Prior linked file changed: '+p)
 return data
def build(a):
 old=verify_old();machine=profile();require(machine==old['profile'] and os.getuid()==old['user_UID'],'profile/user changed')
 out=a.out.resolve();require(not out.exists() and out.parent.is_dir(),'fresh output required');out.mkdir();(out/'src').mkdir()
 for n in ('video_provider_fields_observer.mm','video_provider_lookup_client.mm','video_provider_gate_main.mm'):shutil.copy2(HERE/n,out/'src'/n)
 for n in ('VideoContextLease.h','VideoContextLease.cpp'):shutil.copy2(HERE.parent/'video_context_lease'/n,out/'src'/n)
 shutil.copy2(pathlib.Path(__file__),out/'src/coordinator.py');shutil.copytree(OLD/'assets',out/'assets');shutil.copytree(OLD/'runtime',out/'runtime')
 common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fblocks','-fno-objc-arc','-Wno-deprecated-declarations']
 client=out/'libLookupClient.dylib';observer=out/'libLookupObserver.dylib';main=out/'main.o'
 cmds=[('client',common+['-dynamiclib',str(out/'src/video_provider_lookup_client.mm'),'-install_name',str(client),'-o',str(client)]),('observer',common+['-dynamiclib',str(out/'src/video_provider_fields_observer.mm'),str(out/'src/VideoContextLease.cpp'),str(client),'-framework','Foundation','-framework','IOKit','-framework','Metal','-install_name',str(observer),'-o',str(observer)]),('sign-client',['codesign','--force','--sign','-',str(client)]),('sign-observer',['codesign','--force','--sign','-',str(observer)]),('main',common+['-c',str(out/'src/video_provider_gate_main.mm'),'-o',str(main)])]
 link=next(x['argv'] for x in load(OLD/'commands.json') if x['label']=='application');require(link.count(str(OLD/'main.o'))==1 and link[-2:]==['-o',str(OLD/'application')],'prior link ambiguous')
 link=[str(main) if v==str(OLD/'main.o') else v for v in link[:-2]];link[1:1]=[str(observer),str(client)];cmds.append(('application',link+['-o',str(out/'application')]))
 records=[]
 for label,cmd in cmds:
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=90);records.append({'label':label,'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
  if r.returncode:save(out/'commands.json',records);raise RuntimeError(label+' failed: '+r.stderr[:2000])
 save(out/'commands.json',records)
 files=[p for p in out.rglob('*') if p.is_file() and p.name!='inputs.json']
 save(out/'inputs.json',{'frozen':{str(p.relative_to(out)):sha(p) for p in files},'prior_manifest_SHA256':sha(OLD/'inputs.json'),'profile':machine,'user_UID':os.getuid(),'GPU_registry_ID':4294968416,'build_executes_provider':False})
 print(json.dumps({'status':'BUILD_PASS','application_SHA256':sha(out/'application')}))
def run(a):
 require(a.mode=='hardware' or a.route=='passive','non-passive gate restricted to create-only hardware mode')
 require(not a.probe or (a.mode=='hardware' and a.route=='enabled'),'context probe requires enabled hardware route')
 require(not a.attach or a.probe,'association requires probe')
 build=a.build.resolve();data=load(build/'inputs.json');old=verify_old();require(sha(OLD/'inputs.json')==data['prior_manifest_SHA256'],'prior manifest changed')
 for p,h in data['frozen'].items():require(sha(build/p)==h,'build input changed: '+p)
 require(sha(pathlib.Path(__file__))==data['frozen']['src/coordinator.py'],'coordinator changed');require(profile()==data['profile'] and os.getuid()==data['user_UID'],'profile/user changed')
 out=a.out.resolve();require(not out.exists() and out.parent.is_dir(),'fresh output required');out.mkdir()
 shutil.copytree(build/'assets',out/'assets');shutil.copytree(build/'runtime',out/'runtime');(out/'outputs').mkdir();shutil.copy2(build/'application',out/'application')
 choice='present-key' if a.mode=='hardware' else 'native';policy='current-board' if a.mode=='hardware' else 'observe'
 for n,v in [('owned-choice.json',{'route':'owned'}),('dependency-choice.json',{'mode':choice}),('factory-policy-choice.json',{'mode':policy}),('alias-choice.json',{'mode':'observe'}),('provider-gate-choice.json',{'mode':a.route}),('service-probe-choice.json',{'enabled':a.probe,'attach':a.attach})]:(out/'assets'/n).write_text(json.dumps(v,indent=2)+'\n')
 save(out/'inputs.json',{'build_manifest_SHA256':sha(build/'inputs.json'),'prior_manifest_SHA256':data['prior_manifest_SHA256'],'mode':a.mode,'route':a.route,'probe':a.probe,'attach':a.attach,'assets_SHA256':{str(p.relative_to(out/'assets')):sha(p) for p in (out/'assets').rglob('*') if p.is_file()},'source_SHA256':{p:h for p,h in data['frozen'].items() if p.startswith('src/')}})
 sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
 proc=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),a.mode],B)
 require(profile()==data['profile'],'profile changed after host');verify_old()
 result=load(out/'execution/execution.stdout');lookup=load(out/'outputs/provider-gate.json');alias=load(out/'outputs/alias-native.json');factory=load(out/'outputs/factory-resolver.json')
 require(result['status']=='OBSERVATION_COMPLETED' and lookup['status']=='COMPLETE' and alias['status']=='COMPLETE' and factory['status']=='COMPLETE','host incomplete')
 for n,v in [('result.json',result),('provider-gate.json',lookup),('alias-native.json',alias),('factory-resolver.json',factory)]:save(out/n,v)
 events=[e for e in lookup['events'] if e['name'].startswith('AVD_')];print(json.dumps({'status':'GATE_OBSERVED','mode':a.mode,'pid':proc['pid'],'lookup_events':events,'gate_calls':lookup['gate_calls'],'hardware_video_execution_proved':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','run']);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--build',type=pathlib.Path);p.add_argument('--mode',choices=['inspect','cpu','hardware']);p.add_argument('--route',choices=['passive','enabled','wrong-caller','wrong-target','wrong-name'],default='passive');p.add_argument('--probe',action='store_true');p.add_argument('--attach',action='store_true');a=p.parse_args()
 if a.action=='build':build(a)
 else:
  if not a.build or not a.mode:p.error('--build and --mode required')
  run(a)
