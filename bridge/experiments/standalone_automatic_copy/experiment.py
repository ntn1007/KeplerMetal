#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run an isolated public-Metal client with a pinned local bootstrap."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,check_driver_profile,commands,preflight,read,sha,write
LIB='0985a3057cd487352d801abcd180bf05a681b8dc7357ee5400db044098c32c4c';MANIFEST='c7dcdc81adba7f7ba6cf8175ecc179a086a9bd150b44d71ca1a39ad18846ef9a'

def build(a):
 out=a.out.resolve();lib=a.library.resolve();dual=a.metallib.resolve();preflight(out);check_driver_profile();m=check_library(lib)
 if sha(dual)!=LIB or sha(BRIDGE/'src/partial_dual.json')!=MANIFEST:raise ValueError('Pinned dual registration differs')
 out.mkdir()
 for folder in ('src','assets','runtime','library-src'):(out/folder).mkdir()
 for name in m['source_SHA256']:shutil.copyfile(lib/'src'/name,out/'library-src'/name)
 for name in ('client.mm','bootstrap.mm','verify.py','experiment.py'):shutil.copyfile(HERE/name,out/'src'/name)
 shutil.copyfile(BRIDGE/'tools/verify_partial_gpu_dual_copy.py',out/'src/verify_partial_gpu_dual_copy.py');shutil.copyfile(BRIDGE/'experiments/standalone_icb/run_host.py',out/'runtime/run_host.py');shutil.copyfile(BRIDGE/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
 shutil.copyfile(dual,out/'assets/partial_dual.metallib');shutil.copyfile(BRIDGE/'src/partial_dual.json',out/'assets/partial_dual.json');shutil.copyfile(lib/'libKeplerMetal.a',out/'runtime_archive.a');shutil.copyfile(lib/'manifest.json',out/'archive-manifest.json')
 barrier=(BRIDGE/'src/partial_wide_barrier.metal').read_text();needle='scratch[laneIndex] = laneIndex ^ p.seed;';assert barrier.count(needle)==1
 (out/'src/wrong_barrier.metal').write_text(barrier.replace(needle,'scratch[laneIndex] = laneIndex ^ p.seed ^ 1u;'));shutil.copyfile(BRIDGE/'src/partial_buffer_stencil.metal',out/'src/stencil.metal');(out/'assets/wrong.json').write_bytes((out/'assets/partial_dual.json').read_bytes()+b'\n')
 run=commands(out)
 for name in ('wrong_barrier','stencil'):run(name+'-metal',['xcrun','metal','-std=macos-metal2.4','-c',out/'src'/f'{name}.metal','-o',out/f'{name}.air'])
 run('wrong-metallib',['xcrun','metallib',out/'wrong_barrier.air',out/'stencil.air','-o',out/'assets/wrong.metallib']);assert sha(out/'assets/wrong.metallib')!=LIB and sha(out/'assets/wrong.json')!=MANIFEST
 run('client',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'src/client.mm','-framework','Metal','-framework','Foundation','-o',out/'application']);run('client-symbols',['nm','-u',out/'application']);symbols=(out/'client-symbols.stdout').read_text();assert 'Kepler' not in symbols and 'KPCPU' not in symbols
 run('client-sign',['codesign','--force','--sign','-',out/'application']);run('client-sign-check',['codesign','--verify','--strict',out/'application']);app=sha(out/'application');data=(out/'application').read_bytes();assert data.count(b'no device\n')==1
 wrong=out/'assets/wrong-application';wrong.write_bytes(data.replace(b'no device\n',b'No device\n'));wrong.chmod(0o755);run('wrong-client-sign',['codesign','--force','--sign','-',wrong]);assert sha(wrong)!=app
 run('bootstrap',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-I',out/'library-src',f'-DKM_APPROVED_APP_SHA256="{app}"',out/'src/bootstrap.mm',out/'runtime_archive.a','-Wl,-all_load','-framework','Metal','-framework','Foundation','-o',out/'assets/bootstrap.dylib']);run('bootstrap-sign',['codesign','--force','--sign','-',out/'assets/bootstrap.dylib']);run('bootstrap-sign-check',['codesign','--verify','--strict',out/'assets/bootstrap.dylib'])
 frozen={str(p.relative_to(out)):sha(p) for folder in ('src','assets','runtime','library-src') for p in (out/folder).iterdir() if p.is_file()};frozen['archive-manifest.json']=sha(out/'archive-manifest.json')
 write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':app,'static_library_SHA256':m['static_library_SHA256'],'GPU_execution':False,'client_imports_project_symbols':False})

def run(a):
 build=a.build.resolve();out=a.out.resolve();i=read(build/'inputs.json');assert not out.exists() and out.parent.is_dir() and a.registry_id>0
 for name,digest in i['frozen'].items():assert sha(build/name)==digest,name
 assert sha(build/'application')==i['executable_SHA256'] and sha(build/'runtime_archive.a')==i['static_library_SHA256'];driver=check_driver_profile();out.mkdir()
 for folder in ('src','assets','runtime','library-src'):shutil.copytree(build/folder,out/folder)
 for name in ('runtime_archive.a','archive-manifest.json'):shutil.copyfile(build/name,out/name)
 shutil.copyfile(build/('assets/wrong-application' if a.mode=='wrong-client' else 'application'),out/'application');(out/'application').chmod(0o755);(out/'outputs').mkdir()
 write(out/'inputs.json',dict(i,mode=a.mode,scenario=a.scenario,route=a.route,registry_id=a.registry_id,driver_SHA256=driver,build_inputs_SHA256=sha(build/'inputs.json'),run_executable_SHA256=sha(out/'application')))
 env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_'))}
 if a.mode!='native':env.update(DYLD_INSERT_LIBRARIES=str(out/'assets/bootstrap.dylib'),KM_CARRIER_PATH=str(out/'assets/partial_dual.metallib'),KM_MANIFEST_PATH=str(out/'assets'/('wrong.json' if a.mode=='wrong-manifest' else 'partial_dual.json')),KM_EVENT_PATH=str(out/'events.json'))
 expected=3 if a.mode in ('wrong-client','wrong-manifest') else 7 if a.mode in ('native','wrong-library') else 0;library='wrong.metallib' if a.mode=='wrong-library' else 'partial_dual.metallib'
 sys.path.insert(0,str(out/'runtime'));from run_host import run_host
 run_host(out/'application',out/'execution',[str(out/'assets'/library),str(out/'outputs'),str(a.scenario),a.route],a.reservation_root.resolve(),child_env=env,expected_exit=expected)
 check=subprocess.run([sys.executable,'-I',str(out/'src/verify.py'),str(out)],capture_output=True,text=True,timeout=60);(out/'verification.stdout').write_text(check.stdout);(out/'verification.stderr').write_text(check.stderr);write(out/'verification-execution.json',{'exit_code':check.returncode,'isolated_interpreter':True})
 if check.returncode:raise RuntimeError('Independent oracle failed; inspect '+str(out/'verification.stderr'))
 print(check.stdout.strip(),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build')
 for name in ('out','library','metallib'):b.add_argument('--'+name,type=Path,required=True)
 b.set_defaults(func=build);r=sub.add_parser('run')
 for name in ('out','build','reservation-root'):r.add_argument('--'+name,type=Path,required=True)
 r.add_argument('--mode',choices=('auto','native','wrong-client','wrong-manifest','wrong-library'),required=True);r.add_argument('--scenario',type=int,choices=(0,3),required=True);r.add_argument('--route',choices=('same','separate'),required=True);r.add_argument('--registry-id',type=int,required=True);r.set_defaults(func=run);args=p.parse_args();args.func(args)
