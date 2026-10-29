#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run a public-Metal-only mixed client through an explicit host scope."""
from pathlib import Path
import argparse,json,shutil,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,check_driver_profile,preflight,sha,write
C='7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911';R='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7';M='225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be'
def need(ok,msg):
 if not ok:raise ValueError(msg)
def command(label,cmd,out):
 x=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=120);(out/(label+'.stdout')).write_bytes(x.stdout);(out/(label+'.stderr')).write_bytes(x.stderr);need(x.returncode==0,label+' failed');return x

def build(a):
 out=a.out.resolve();lib=a.library.resolve();preflight(out);meta=check_library(lib)
 for path,digest in [(a.compute,C),(a.render,R),(BRIDGE/'src/cpu_icb_gpu_indices.json',M)]:need(sha(path)==digest,'asset mismatch')
 out.mkdir()
 for path,name in [(HERE/'client.mm','client.mm'),(HERE/'host.mm','host.mm'),(a.compute,'compute.metallib'),(a.render,'render.metallib'),(BRIDGE/'src/cpu_icb_gpu_indices.json','manifest.json')]:shutil.copyfile(path,out/name)
 (out/'runtime').mkdir();shutil.copyfile(BRIDGE/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py');shutil.copyfile(BRIDGE/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
 command('client',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-install_name','@rpath/PublicMixedClient.dylib',out/'client.mm','-framework','Metal','-framework','Foundation','-o',out/'client.dylib'],out)
 symbols=command('symbols',['nm','-u',out/'client.dylib'],out).stdout.decode();need('KPCPU' not in symbols and 'Kepler' not in symbols,'client imports project')
 command('client-sign',['codesign','--force','--sign','-',out/'client.dylib'],out);command('client-verify',['codesign','--verify','--strict',out/'client.dylib'],out)
 command('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',lib/'src',out/'host.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'host'],out)
 names=['client.mm','host.mm','compute.metallib','render.metallib','manifest.json','client.dylib','host','runtime/lab_gpu_reservation.py','runtime/run_sdk_host.py'];frozen={n:sha(out/n) for n in names}
 write(out/'inputs.json',{'frozen':frozen,'library_sha256':meta['static_library_SHA256'],'client_public_metal_imports_only_checked':True,'system_modified':False})
 print(json.dumps({'status':'BUILD_PASS','GPU_execution':False,'client_sha256':frozen['client.dylib']}))

def verify_pixels(out,mode):
 pix=(out/'outputs/pixels.bin').read_bytes();idx=(out/'outputs/indices.bin').read_bytes();count=(out/'outputs/counter.bin').read_bytes()
 need(len(pix)==49664 and len(idx)==128 and len(count)==132,'sizes')
 producer=mode!='no-producer';draw=mode in ('direct','icb');expectedidx=bytearray(b'\xa5'*128);expectedcounter=bytearray(b'\xa5'*132)
 struct.pack_into('<4I',expectedidx,64,*( (0,1,2,0x4521) if producer else (0,0,0,0x77777777)))
 struct.pack_into('<I',expectedcounter,64,32 if producer else 0);need(idx==expectedidx and count==expectedcounter,'indices/counter/guards')
 expected=bytearray(b'\xa5'*256);color=struct.pack('<4f',.75,.125,.25,1)
 for y in range(48):
  for x in range(64):expected.extend(color if draw and 3<=x<16 and 4<=y<13 else bytes(16))
 expected.extend(b'\xa5'*256);need(pix==bytes(expected),'pixel/guard mismatch')
 return {'channels':64*48*4,'colored_pixels':117 if draw else 0,'gpu_counter':32 if producer else 0,'pixel_sha256':sha(out/'outputs/pixels.bin'),'index_sha256':sha(out/'outputs/indices.bin'),'counter_sha256':sha(out/'outputs/counter.bin')}

def run(a):
 build=a.build.resolve();out=a.out.resolve();preflight(out);m=json.loads((build/'inputs.json').read_text());need(all(sha(build/n)==h for n,h in m['frozen'].items()),'frozen inputs differ');check_driver_profile();out.mkdir()
 for name in ('client.mm','host.mm','compute.metallib','render.metallib','manifest.json','client.dylib','host'):shutil.copyfile(build/name,out/name)
 shutil.copytree(build/'runtime',out/'runtime');(out/'outputs').mkdir();write(out/'inputs.json',m)
 command('client-verify',['codesign','--verify','--strict',out/'client.dylib'],out)
 sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
 execution=run_host(out/'host',out/'execution',[str(out/'compute.metallib'),str(out/'manifest.json'),str(out/'render.metallib'),str(out/'client.dylib'),str(out/'outputs'),a.mode],a.lab.resolve())
 need(sha(out/'host')==execution['original_binary_sha256'] and sha(out/'execution/application')==execution['signed_binary_sha256'],'host mismatch')
 d=json.loads((out/'execution/execution.stdout').read_text());write(out/'result.json',d)
 need(d['status']=='PASS' and d['mode']==a.mode and d['client']['command_status']==4 and d['device_queue_restored'] and d['shared_method_imps_unchanged'],'host result')
 identity=d['device_identity'];need(identity['PCI_vendor_id']==0x10de and identity['PCI_device_id']==0x1198 and identity['name']=='NVIDIA GeForce GTX 880M','GPU identity')
 events=d['scope_events'];n=lambda s:sum(x.get('operation')==s for x in events)
 need(n('automatic_compute_factories_enabled')==1 and n('automatic_render_factories_enabled')==1 and n('automatic_compute_encoder')>=1 and n('automatic_render_encoder')>=1,'automatic path missing')
 if a.mode!='direct':need(n('executeCommandsInBuffer')==1 and n('execute_CPU_render_ICB')==1,'ICB paths missing')
 proof=verify_pixels(out,a.mode);proof.update({'status':'PASS','mode':a.mode,'independent_client':True,'device_identity':identity,'signed_host_sha256':execution['signed_binary_sha256'],'client_sha256':sha(out/'client.dylib'),'GPU_reservation_id':execution['GPU_reservation']['reservation_id'],'system_modified':False,'GPU_video_execution':False});write(out/'verification.json',proof);print(json.dumps(proof,sort_keys=True))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True);b=s.add_parser('build')
 for n in ('library','compute','render','out'):b.add_argument('--'+n,type=Path,required=True)
 b.set_defaults(func=build);r=s.add_parser('run')
 for n in ('build','lab','out'):r.add_argument('--'+n,type=Path,required=True)
 r.add_argument('--mode',choices=['direct','icb','no-producer','no-render'],required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
