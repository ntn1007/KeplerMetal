#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and inspect a bounded builtin/barrier pipeline without GPU submission."""
import argparse,json,os,shutil,struct,sys
from pathlib import Path
from public_large_scratch import ROOT,commands,preflight,sha,write
from video_metal_resource_observer import check_profile

def build(a):
 out=a.out.resolve();preflight(out);profile=check_profile();out.mkdir()
 for folder in ('src','assets','runtime'):(out/folder).mkdir()
 for name in ('partial_dual_pipeline.py','partial_dual_pipeline_probe.mm','public_large_scratch.py','video_metal_resource_observer.py','decode_native_commands.py'):shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
 shutil.copyfile(ROOT/'src/partial_buffer_stencil.metal',out/'src/partial_buffer_stencil.metal');shutil.copyfile(ROOT/'src/partial_wide_barrier.metal',out/'src/partial_wide_barrier.metal')
 shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py');shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
 run=commands(out);run('metal-stencil',['xcrun','metal','-std=macos-metal2.3','-c',out/'src/partial_buffer_stencil.metal','-o',out/'assets/stencil.air']);run('metal-barrier',['xcrun','metal','-std=macos-metal2.3','-c',out/'src/partial_wide_barrier.metal','-o',out/'assets/barrier.air']);run('metallib',['xcrun','metallib',out/'assets/barrier.air',out/'assets/stencil.air','-o',out/'assets/shader.metallib']);run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'src/partial_dual_pipeline_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
 frozen={str(p.relative_to(out)):sha(p) for folder in ('src','assets','runtime') for p in (out/folder).iterdir() if p.is_file()};write(out/'inputs.json',{'frozen':frozen,'executable_SHA256':sha(out/'application'),'profile':profile,'user_UID':os.getuid(),'GPU_dispatch':False})

def run(a):
 b=a.build.resolve();o=a.out.resolve();i=json.loads((b/'inputs.json').read_text())
 if o.exists() or not o.parent.is_dir() or not 0<a.registry_id<2**64:raise ValueError('Fresh output and device registry ID required')
 for name,digest in i['frozen'].items():
  if sha(b/name)!=digest:raise ValueError('Frozen input changed: '+name)
 if sha(b/'application')!=i['executable_SHA256'] or sha(ROOT/'tools/partial_dual_pipeline.py')!=i['frozen']['src/partial_dual_pipeline.py'] or check_profile()!=i['profile'] or os.getuid()!=i['user_UID']:raise ValueError('Executable, coordinator, profile or user changed')
 o.mkdir();(o/'capture').mkdir()
 for folder in ('src','assets','runtime'):shutil.copytree(b/folder,o/folder)
 shutil.copyfile(b/'application',o/'application');(o/'application').chmod(0o755);write(o/'inputs.json',dict(i,registry_id=a.registry_id,build_inputs_SHA256=sha(b/'inputs.json')))
 sys.path.insert(0,str(o/'runtime'));from run_sdk_host import run_host
 m=run_host(o/'application',o/'execution',[str(o/'assets/shader.metallib'),str(o/'capture'),str(a.registry_id)],a.reservation_root.resolve())
 if check_profile()!=i['profile']:raise ValueError('Profile changed after host')
 d=json.loads((o/'execution/execution.stdout').read_text());rows=d['records'];checked=[]
 if d['GPU_dispatch'] or d['committed'] or d['registry_id']!=a.registry_id or [r['function'] for r in rows]!=['partial_builtin_barrier','partial_buffer_stencil']:raise ValueError('Pipeline inventory differs')
 for row in rows:
  data=(o/'capture'/(row['function']+'.commands.bin')).read_bytes();q=data[184:440];u=lambda offset:struct.unpack_from('<I',q,offset)[0]
  if row['GPU_dispatch'] or row['committed'] or len(data)!=464 or u(0x44)&0x3ffff!=row['static_threadgroup_bytes'] or not 1<=u(0xb8)>>24<=63 or u(0x50)&255!=6:raise ValueError('Unqualified native pipeline or QMD')
  checked.append({'function':row['function'],'static_threadgroup_bytes':row['static_threadgroup_bytes'],'register_count':u(0xb8)>>24,'native_command_SHA256':sha(o/'capture'/(row['function']+'.commands.bin'))})
 write(o/'results.json',d);print(json.dumps({'status':'PASS','GPU_dispatch':False,'library_SHA256':sha(o/'assets/shader.metallib'),'pipelines':checked}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(required=True);b=subs.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build);r=subs.add_parser('run')
 for name in ('build','out','reservation-root'):r.add_argument('--'+name,type=Path,required=True)
 r.add_argument('--registry-id',type=int,required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
