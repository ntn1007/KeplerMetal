#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and observe the native render pipeline identity without GPU dispatch."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys
from public_large_scratch import ROOT,check_driver_profile,commands,preflight,read,sha,write


def build(a):
 out=a.out.resolve();preflight(out);out.mkdir()
 for group in ['src','assets','runtime','oracles']:(out/group).mkdir()
 for name in ['native_render_pipeline_probe.mm']:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
 for name in ['KeplerGPUIdentity.h','render_state_carrier.metal','air_render_pipeline_probe.metal','air_render_pipeline_plain_root.metal']:shutil.copyfile(ROOT/'src'/name,out/'src'/name)
 for name in ['verify_native_render_pipeline_probe.py','verify_local_memory.py','public_large_scratch.py']:shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
 shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py');shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
 run=commands(out)
 shader='air_render_pipeline_plain_root' if a.plain_root else 'air_render_pipeline_probe'
 for name,source,standard,flags in [('graphics','render_state_carrier','macos-metal2.4',[]),('probe',shader,'macos-metal2.3',['-fmodules=none'])]:
  run(name+'-metal',['xcrun','metal','-std='+standard,*flags,'-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')]);run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
 assert sha(out/'assets/graphics.metallib')=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
 run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src/native_render_pipeline_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
 frozen={str(p.relative_to(out)):sha(p)for group in ['src','assets','runtime','oracles']for p in(out/group).iterdir()if p.is_file()}
 write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'builder_SHA256':sha(__file__),'GPU_execution':False,'probe_source':shader})


def run(a):
 build,out=a.build.resolve(),a.out.resolve();m=read(build/'inputs.json');assert not out.exists() and out.parent.is_dir()
 for name,digest in m['frozen'].items():assert sha(build/name)==digest,name
 assert sha(build/'application')==m['executable_SHA256'];driver=check_driver_profile();out.mkdir()
 for folder in ['src','assets','runtime','oracles']:shutil.copytree(build/folder,out/folder)
 shutil.copyfile(build/'application',out/'application');(out/'application').chmod(0o755);write(out/'inputs.json',dict(m,driver_SHA256=driver,source_build_inputs_SHA256=sha(build/'inputs.json')))
 sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
 r=run_host(out/'application',out/'execution',[str(out/'assets/graphics.metallib'),str(out/'assets/probe.metallib')],a.reservation_root.resolve());write(out/'results.json',read(out/'execution/execution.stdout'))
 code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_native_render_pipeline_probe import verify;print(json.dumps(verify(sys.argv[2])))';p=subprocess.run([sys.executable,'-I','-c',code,str(out/'oracles'),str(out)],capture_output=True,text=True);(out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr);write(out/'verification-execution.json',{'exit_code':p.returncode,'isolated_interpreter':True})
 if p.returncode:raise RuntimeError('Frozen oracle failed: '+str(out/'verification.stderr'))
 proof=json.loads(p.stdout);write(out/'independent-verification.json',dict(proof,PID=r['pid']));print(json.dumps(proof),flush=True)


if __name__=='__main__':
 p=argparse.ArgumentParser();s=p.add_subparsers(required=True);b=s.add_parser('build');b.add_argument('--out',type=Path,required=True);b.add_argument('--plain-root',action='store_true');b.set_defaults(func=build);r=s.add_parser('run')
 for name in ['build','out','reservation-root']:r.add_argument('--'+name,type=Path,required=True)
 r.set_defaults(func=run);a=p.parse_args();a.func(a)
