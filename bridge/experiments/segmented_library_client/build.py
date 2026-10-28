#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a second Metal client against the previously qualified local bootstrap."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import preflight, commands, read, sha, write
from video_metal_resource_observer import check_profile

def need(value, why):
 if not value: raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--qualified-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 old=a.qualified_build.resolve();out=a.out.resolve();preflight(out);profile=check_profile();old_inputs=read(old/'inputs.json');report=read(BRIDGE.parent/'docs/standalone-data-cas-validation.json')
 need(old_inputs['profile']==profile,'Qualified profile differs')
 bootstrap=old/'assets/bootstrap.dylib';need(sha(bootstrap)==old_inputs['frozen']['assets/bootstrap.dylib']==report['bootstrap_SHA256'],'Qualified bootstrap differs')
 manifest=read(old/'assets/client-manifest.json');names=['client-manifest.json',manifest['library'],'wrong.metallib','bootstrap.dylib']+[r['certificate'] for r in manifest['profiles']]
 need(len(names)==len(set(names)) and len(manifest['profiles'])==5,'Unexpected asset list')
 for name in names:
  need(Path(name).name==name and sha(old/'assets'/name)==old_inputs['frozen']['assets/'+name],'Qualified asset differs: '+name)
 need(sha(old/'assets'/manifest['library'])==manifest['library_SHA256'],'Library differs')
 subprocess.run(['codesign','--verify','--strict',str(bootstrap)],check=True,capture_output=True)
 out.mkdir();(out/'assets').mkdir();(out/'src').mkdir()
 for name in names:shutil.copyfile(old/'assets'/name,out/'assets'/name)
 shutil.copyfile(HERE/'client.mm',out/'src/client.mm')
 run=commands(out);run('client',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'src/client.mm','-framework','Metal','-framework','Foundation','-o',out/'application']);run('symbols',['nm','-u',out/'application'])
 symbols=(out/'symbols.stdout').read_text();need('Kepler' not in symbols and 'KPCreate' not in symbols,'Client imports project API')
 run('sign',['codesign','--force','--sign','-',out/'application']);run('signature',['codesign','--verify','--strict',out/'application'])
 exe=sha(out/'application');write(out/'policy.json',{'version':1,'allowed_clients':[exe]})
 frozen={str(x.relative_to(out)):sha(x) for x in list((out/'assets').iterdir())+[out/'application',out/'policy.json',out/'src/client.mm']}
 write(out/'inputs.json',{'frozen':frozen,'bootstrap_SHA256':sha(out/'assets/bootstrap.dylib'),'policy_SHA256':sha(out/'policy.json'),'application_SHA256':exe,'qualified_build_inputs_SHA256':sha(old/'inputs.json'),'profile':profile,'GPU_dispatch':False})
 print(json.dumps({'status':'BUILD_PASS','application_SHA256':exe,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
