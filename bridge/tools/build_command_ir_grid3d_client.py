#!/usr/bin/env python3
"""Build an exact native-consumer four-buffer/XYZ public-MSL IR fixture."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--compiler',type=Path,required=True);p.add_argument('--materializer',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir();commands=[];library=a.library.resolve();compiler=a.compiler.resolve();materializer=a.materializer.resolve()
assert sha(library/'libKeplerMetal.a')==json.loads((library/'manifest.json').read_text())['static_library_SHA256']
def run(args,label):
 args=[str(x)for x in args];r=subprocess.run(args,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':args,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:];return r
for n in ['basic','threads','barrier','copy','reset']:
 dest=out/('compiled-'+n);dest.mkdir();r=run([compiler/'air_command_compile',compiler/'producer.air',dest,'encode_grid_'+n,32,2,2],'compile-'+n);info=json.loads(r.stdout);assert info['command_ir_version']==2 and not any(info[k]for k in ['scratch_bytes','crs_bytes','shared_bytes']);shutil.copyfile(dest/'program.sass',out/'assets'/(n+'.sass'));(out/'assets'/(n+'.json')).write_text(json.dumps(info,indent=2)+'\n')
sdk=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK'
for n in ['gpu_command_selector.metallib','gpu_command_geometry.metallib','gpu_command_bindings.metallib']:shutil.copyfile(sdk/'assets'/n,out/'assets'/n)
for n in ['run_sdk_host.py','lab_gpu_reservation.py']:shutil.copyfile(sdk/'runtime'/n,out/'runtime'/n)
shutil.copyfile(ROOT/'results/cpu-icb-grid3d-gpu-qualified/cpu_icb_grid3d.metallib',out/'assets/consumer.metallib');shutil.copyfile(ROOT/'src/cpu_icb_grid3d.json',out/'assets/consumer.json');shutil.copyfile(materializer/'command_ir_materializer.metallib',out/'assets/materializer.metallib');shutil.copyfile(ROOT/'results/gpu-command-ir-host-build-20261015-04/command_ir_carrier.metallib',out/'assets/carrier.metallib')
for f in [ROOT/'tools/command_ir_grid3d_client.mm',ROOT/'src/KeplerCPUICB.h',ROOT/'src/KeplerProgramImport.h',ROOT/'src/KeplerProgramImport.mm',ROOT/'src/command_ir_field_probe.metal']:shutil.copyfile(f,out/f.name)
run(['xcrun','metal','-std=macos-metal2.0','-c',out/'command_ir_field_probe.metal','-o',out/'field.air'],'field-metal');run(['xcrun','metallib',out/'field.air','-o',out/'assets/field.metallib'],'field-metallib')
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o'],'import-MRC')
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_GRID_NATIVE=0','-I',out,out/'command_ir_grid3d_client.mm',out/'KeplerProgramImport.o','-L',library,'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
(out/'inputs.json').write_text(json.dumps({'source_hashes':{n:sha(out/n)for n in ['command_ir_grid3d_client.mm','KeplerCPUICB.h','KeplerProgramImport.h','KeplerProgramImport.mm','command_ir_field_probe.metal']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'runtime_SHA256':{p.name:sha(p)for p in(out/'runtime').iterdir()},'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(library/'libKeplerMetal.a'),'library_build_manifest_SHA256':sha(library/'manifest.json'),'compiler_build_manifest_SHA256':sha(compiler/'manifest.json'),'GPU_execution':False},indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'GPU_execution':False}))
