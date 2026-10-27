#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze and run a separate public-Metal client with a process-local bootstrap."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys
from public_large_scratch import ROOT,check_library,check_driver_profile,commands,preflight,read,sha,write
from verify_automatic_render import MODES

def build(a):
 out,lib=a.out.resolve(),a.library.resolve();preflight(out);manifest=check_library(lib);out.mkdir()
 for folder in ('src','assets','runtime','oracles','library-src'):(out/folder).mkdir()
 for name in manifest['source_SHA256']:shutil.copyfile(lib/'src'/name,out/'library-src'/name)
 for name in ('automatic_render_host.mm','ordinary_metal_client.mm'):shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
 for name in ('render_state_carrier.metal','KeplerGPUIdentity.h'):shutil.copyfile(ROOT/'src'/name,out/'src'/name)
 for name in ('verify_automatic_render.py','verify_local_memory.py','public_large_scratch.py'):shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
 shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py');shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py');run=commands(out)
 run('carrier-metal',['xcrun','metal','-std=macos-metal2.4','-c',out/'src/render_state_carrier.metal','-o',out/'carrier.air']);run('carrier-metallib',['xcrun','metallib',out/'carrier.air','-o',out/'assets/render_state_carrier.metallib']);assert sha(out/'assets/render_state_carrier.metallib')=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
 run('ordinary-client',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-install_name','@rpath/OrdinaryMetalClient.dylib',out/'src/ordinary_metal_client.mm','-framework','Metal','-framework','Foundation','-o',out/'assets/client.dylib'])
 run('ordinary-symbols',['nm','-u',out/'assets/client.dylib']);symbols=(out/'ordinary-symbols.stdout').read_text();assert 'Kepler' not in symbols and 'KPCPU' not in symbols
 run('ordinary-sign',['codesign','--force','--sign','-',out/'assets/client.dylib']);run('ordinary-verify',['codesign','--verify','--strict',out/'assets/client.dylib'])
 run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src','-I',out/'library-src',out/'src/automatic_render_host.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
 frozen={str(p.relative_to(out)):sha(p) for folder in ('src','assets','runtime','oracles','library-src') for p in (out/folder).iterdir() if p.is_file()};write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'static_library_SHA256':manifest['static_library_SHA256'],'GPU_execution':False,'ordinary_client_has_no_kepler_imports':True})

def run(a):
 build,out=a.build.resolve(),a.out.resolve();data=read(build/'inputs.json');assert not out.exists() and out.parent.is_dir()
 for name,digest in data['frozen'].items():assert sha(build/name)==digest,name
 assert sha(build/'application')==data['executable_SHA256'];driver=check_driver_profile();out.mkdir();(out/'outputs').mkdir()
 for folder in ('src','assets','runtime','oracles','library-src'):shutil.copytree(build/folder,out/folder)
 shutil.copyfile(build/'application',out/'application');(out/'application').chmod(0o755);write(out/'inputs.json',dict(data,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(build/'inputs.json')))
 sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
 result=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'assets/client.dylib'),str(out/'outputs'),a.mode],a.reservation_root.resolve());write(out/'results.json',read(out/'execution/execution.stdout'))
 code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_automatic_render import verify;print(json.dumps(verify(sys.argv[2])))';p=subprocess.run([sys.executable,'-I','-c',code,str(out/'oracles'),str(out)],capture_output=True,text=True);(out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr);write(out/'verification-execution.json',{'exit_code':p.returncode,'isolated_interpreter':True})
 if p.returncode:raise RuntimeError('Independent oracle failed; inspect terminal host: '+str(out/'verification.stderr'))
 proof=json.loads(p.stdout);write(out/'independent-verification.json',dict(proof,PID=result['pid']));print(proof)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build')
 for k in ('library','out'):b.add_argument('--'+k,type=Path,required=True)
 b.set_defaults(func=build);r=sub.add_parser('run')
 for k in ('build','out','reservation-root'):r.add_argument('--'+k,type=Path,required=True)
 r.add_argument('--mode',choices=MODES,required=True);r.set_defaults(func=run);args=p.parse_args();args.func(args)
