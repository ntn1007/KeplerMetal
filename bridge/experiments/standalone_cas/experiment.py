#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pin a public-Metal client and test an opt-in process-local CAS bootstrap."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import commands,preflight,sha,write,read
from video_metal_resource_observer import check_profile
MODES=('native','optin','wrong-library','wrong-client','wrong-cert')
def require(v,s):
 if not v:raise ValueError(s)

def build(a):
 sdk=a.sdk.resolve();source=a.shader.resolve();out=a.out.resolve();preflight(out);profile=check_profile()
 report=read(BRIDGE.parent/'docs/cas-sdk-regenerated-validation.json');m=read(sdk/'BUILD_MANIFEST.json');assets=read(sdk/'assets/client-manifest.json')
 require(m['decoder_evidence_required'] and sha(sdk/'lib/libKeplerNativeCAS.a')==m['static_archive_SHA256']==report['final_archive_SHA256'],'Qualified SDK archive differs')
 for name,h in m['source_SHA256'].items():require(sha(sdk/name)==h==sha(BRIDGE/name),'SDK source differs: '+name)
 for name in ('KeplerNativeCAS.h','KeplerGPUIdentity.h'):require(sha(sdk/'include'/name)==sha(sdk/'src'/name),'SDK public header differs: '+name)
 require(sha(sdk/'assets'/assets['library'])==assets['library_SHA256'],'Library differs')
 for row,qualified in zip(assets['profiles'],report['certificates']):
  require(row['function']==qualified['function'] and row['candidate']==qualified['candidate'] and row['certificate_SHA256']==qualified['certificate_SHA256']==sha(sdk/'assets'/row['certificate']),'Certificate differs')
 require(len(assets['profiles'])==len(report['certificates'])==5,'Profile count differs')
 shader=source.read_text();require(shader.count('0x10001u')>=1,'Shader source differs')
 out.mkdir();(out/'src').mkdir();(out/'runtime').mkdir();shutil.copytree(sdk/'assets',out/'assets')
 for n in ('client.mm','bootstrap.mm','verify.py','experiment.py'):shutil.copyfile(HERE/n,out/'src'/n)
 shutil.copyfile(source,out/'src/fixture.metal');(out/'src/wrong.metal').write_text(shader.replace('0x10001u','0x10003u',1))
 shutil.copyfile(sdk/'include/KeplerNativeCAS.h',out/'src/KeplerNativeCAS.h');shutil.copyfile(sdk/'include/KeplerGPUIdentity.h',out/'src/KeplerGPUIdentity.h');shutil.copyfile(sdk/'lib/libKeplerNativeCAS.a',out/'runtime/libKeplerNativeCAS.a')
 shutil.copyfile(BRIDGE/'experiments/standalone_icb/run_host.py',out/'runtime/run_host.py');shutil.copyfile(BRIDGE/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
 run=commands(out);run('wrong-metal',['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',out/'src/wrong.metal','-o',out/'wrong.air']);run('wrong-metallib',['xcrun','metallib',out/'wrong.air','-o',out/'assets/wrong.metallib'])
 require(sha(out/'assets/wrong.metallib')!=assets['library_SHA256'],'Wrong library matches')
 run('client',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'src/client.mm','-framework','Metal','-framework','Foundation','-o',out/'application']);run('client-symbols',['nm','-u',out/'application'])
 imports=(out/'client-symbols.stdout').read_text();require('Kepler' not in imports and 'KPCreate' not in imports,'Client imports project API')
 run('client-sign',['codesign','--force','--sign','-',out/'application']);run('client-sign-check',['codesign','--verify','--strict',out/'application']);apphash=sha(out/'application')
 original=(out/'application').read_bytes();require(original.count(b'no device\n')==1,'Negative client marker differs');wrong=out/'assets/wrong-application';wrong.write_bytes(original.replace(b'no device\n',b'No device\n',1));wrong.chmod(0o755);run('wrong-client-sign',['codesign','--force','--sign','-',wrong]);require(sha(wrong)!=apphash,'Negative client unchanged')
 bootstrap=out/'assets/bootstrap.dylib';run('bootstrap',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-I',out/'src',f'-DKM_CAS_APP_HASH="{apphash}"',f'-DKM_CAS_LIBRARY_HASH="{assets["library_SHA256"]}"',f'-DKM_CAS_MANIFEST_HASH="{sha(out/"assets/client-manifest.json")}"',out/'src/bootstrap.mm','-Wl,-all_load',out/'runtime/libKeplerNativeCAS.a','-framework','Metal','-framework','Foundation','-o',bootstrap]);run('bootstrap-sign',['codesign','--force','--sign','-',bootstrap]);run('bootstrap-sign-check',['codesign','--verify','--strict',bootstrap])
 frozen={str(x.relative_to(out)):sha(x) for folder in ('src','runtime','assets') for x in (out/folder).rglob('*') if x.is_file()}
 write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':apphash,'profile':profile,'user_UID':os.getuid(),'archive_SHA256':m['static_archive_SHA256'],'client_imports_project_symbols':False,'GPU_dispatch':False})
 print(json.dumps({'status':'BUILD_PASS','GPU_dispatch':False,'application_SHA256':apphash}))

def run(a):
 b=a.build.resolve();o=a.out.resolve();i=read(b/'inputs.json');require(not o.exists() and o.parent.is_dir() and (a.reservation_root/'results').is_dir(),'Fresh output and shared lab required')
 for name,h in i['frozen'].items():require(sha(b/name)==h,'Frozen input changed: '+name)
 require(sha(b/'application')==i['executable_SHA256'] and sha(HERE/'experiment.py')==i['frozen']['src/experiment.py'] and check_profile()==i['profile'] and os.getuid()==i['user_UID'],'Client, coordinator or profile changed')
 o.mkdir();shutil.copytree(b/'src',o/'src');shutil.copytree(b/'runtime',o/'runtime');shutil.copytree(b/'assets',o/'assets');(o/'outputs').mkdir()
 app=b/'assets/wrong-application' if a.mode=='wrong-client' else b/'application';shutil.copyfile(app,o/'application');(o/'application').chmod(0o755)
 if a.mode=='wrong-cert':
  manifest=read(o/'assets/client-manifest.json');name=manifest['profiles'][0]['certificate'];p=o/'assets'/name;raw=bytearray(p.read_bytes());raw[-2]^=1;p.write_bytes(raw)
 env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_'))}
 if a.mode!='native':env.update(DYLD_INSERT_LIBRARIES=str(o/'assets/bootstrap.dylib'),KM_CAS_ASSET_PATH=str(o/'assets'),KM_CAS_EVENT_PATH=str(o/'events.json'))
 lib='wrong.metallib' if a.mode=='wrong-library' else 'cas_client.metallib';client_mode='construct' if a.mode=='wrong-library' else 'run';expected=3 if a.mode in ('wrong-client','wrong-cert') else 0
 frozen={str(x.relative_to(o)):sha(x) for folder in ('src','runtime') for x in (o/folder).iterdir() if x.is_file()};assets={x.name:sha(x) for x in (o/'assets').iterdir() if x.is_file()}
 write(o/'inputs.json',{'mode':a.mode,'registry_id':a.registry_id,'application_SHA256':sha(o/'application'),'bootstrap_SHA256':sha(o/'assets/bootstrap.dylib'),'assets_SHA256':assets,'frozen':frozen,'build_inputs_SHA256':sha(b/'inputs.json'),'profile':i['profile']})
 sys.path.insert(0,str(o/'runtime'));from run_host import run_host
 run_host(o/'application',o/'execution',[str(o/'assets'/lib),str(o/'outputs'),client_mode],a.reservation_root.resolve(),child_env=env,expected_exit=expected)
 require(check_profile()==i['profile'],'Profile changed after host')
 if a.mode not in ('wrong-client','wrong-cert'):write(o/'results.json',read(o/'execution/execution.stdout'))
 v=subprocess.run([sys.executable,'-I',str(o/'src/verify.py'),str(o)],capture_output=True,text=True,timeout=120);(o/'verification.stdout').write_text(v.stdout);(o/'verification.stderr').write_text(v.stderr)
 require(v.returncode==0,'Offline verifier failed: '+str(o/'verification.stderr'));write(o/'verification.json',json.loads(v.stdout));print(v.stdout.strip())
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True);b=s.add_parser('build');b.add_argument('--sdk',type=Path,required=True);b.add_argument('--shader',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.set_defaults(fn=build)
 r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--reservation-root',type=Path,required=True);r.add_argument('--registry-id',type=int,required=True);r.add_argument('--mode',choices=MODES,required=True);r.set_defaults(fn=run);a=p.parse_args();a.fn(a)
