#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run client A with the same A+B policy used for client B."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_driver_profile,read,sha,write

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reservation-root',type=Path,required=True);p.add_argument('--scenario',type=int,choices=(0,3),required=True);p.add_argument('--route',choices=('same','separate'),required=True);p.add_argument('--registry-id',type=int,required=True);a=p.parse_args();b=a.build.resolve();o=a.out.resolve();i=read(b/'inputs.json');assert not o.exists() and o.parent.is_dir() and a.registry_id>0
 for name,digest in i['frozen'].items():assert sha(b/name)==digest,name
 assert sha(b/'application')==i['executable_A_SHA256'] and sha(b/'runtime_archive.a')==i['static_library_SHA256'];driver=check_driver_profile();o.mkdir()
 for folder in ('src','assets','runtime','library-src'):shutil.copytree(b/folder,o/folder)
 for name in ('runtime_archive.a','archive-manifest.json','application'):shutil.copyfile(b/name,o/name)
 (o/'application').chmod(0o755);(o/'outputs').mkdir();policy='policy-ab.json';policySHA=sha(b/'assets'/policy)
 write(o/'inputs.json',dict(i,mode='optin-a',tag='a',scenario=a.scenario,route=a.route,registry_id=a.registry_id,driver_SHA256=driver,policy_name=policy,policy_expected_SHA256=policySHA,build_inputs_SHA256=sha(b/'inputs.json'),run_executable_SHA256=sha(o/'application'),same_policy_runner_SHA256=sha(HERE/'same_policy.py')))
 env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_'))};env.update(DYLD_INSERT_LIBRARIES=str(o/'assets/bootstrap.dylib'),KM_CARRIER_PATH=str(o/'assets/partial_dual.metallib'),KM_MANIFEST_PATH=str(o/'assets/partial_dual.json'),KM_EVENT_PATH=str(o/'events.json'),KM_COPY_POLICY_PATH=str(o/'assets'/policy),KM_COPY_POLICY_SHA256=policySHA)
 sys.path.insert(0,str(o/'runtime'));from run_host import run_host
 run_host(o/'application',o/'execution',[str(o/'assets/partial_dual.metallib'),str(o/'outputs'),str(a.scenario),a.route],a.reservation_root.resolve(),child_env=env,expected_exit=0)
 result=subprocess.run([sys.executable,'-I',str(o/'src/verify.py'),str(o)],capture_output=True,text=True,timeout=60);(o/'verification.stdout').write_text(result.stdout);(o/'verification.stderr').write_text(result.stderr);write(o/'verification-execution.json',{'exit_code':result.returncode,'isolated_interpreter':True})
 if result.returncode:raise RuntimeError('Independent oracle failed; inspect '+str(o/'verification.stderr'))
 print(result.stdout.strip(),flush=True)
if __name__=='__main__':main()
