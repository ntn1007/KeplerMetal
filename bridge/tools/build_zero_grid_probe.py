#!/usr/bin/env python3
"""Probe zero-CTA semantics on known resident native QMDs, with the frozen SDK."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--grid',type=int,choices=[-1,0,1],required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir();commands=[]
def replace_once(s,before,after):assert s.count(before)==1,before;return s.replace(before,after,1)
source=(SDK/'examples/gpu_command_bindings_client.mm').read_text()
source=replace_once(source,' const unsigned statics[3]',
 ' id<MTLLibrary>gridLibrary=load(d,[assets stringByAppendingPathComponent:@"qmd_grid_probe.metallib"],&error);\n'
 ' id<MTLComputePipelineState>gridPSO=[d newComputePipelineStateWithFunction:[gridLibrary newFunctionWithName:@"set_resident_qmd_grid"]error:&error];if(!gridPSO)return 3;\n'
 ' const unsigned statics[3]')
anchor='  if(split)[sbuf commit];if(completed)'
insert='''  NSArray*nativeRecords=[plan valueForKey:@"targetRecords"];
  if(nativeRecords.count!=rows)return 20;
  NSMutableArray*qmdHosts=[NSMutableArray new];
  if(KP_QMD_GRID_OVERRIDE>=0){
   uint32_t requested=KP_QMD_GRID_OVERRIDE;
   for(unsigned row=0;row<rows;row++){
    id<MTLBuffer>qmd=[nativeRecords[row] valueForKey:@"descriptor"];
    if(!qmd||qmd.device!=d||qmd.storageMode!=MTLStorageModePrivate||qmd.length!=4096)return 20;
    id<MTLComputeCommandEncoder>patch=[sbuf computeCommandEncoder];[patch setComputePipelineState:gridPSO];[patch setBuffer:qmd offset:0 atIndex:0];[patch setBytes:&requested length:4 atIndex:1];[patch dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];[patch endEncoding];
   }
  }
  for(unsigned row=0;row<rows;row++)[qmdHosts addObject:[d newBufferWithLength:256 options:MTLResourceStorageModeShared]];
'''
source=replace_once(source,anchor,insert+anchor)
source=replace_once(source,'  icb=nil;[params removeAllObjects];',
 '  b=[main blitCommandEncoder];for(unsigned row=0;row<rows;row++){id<MTLBuffer>qmd=[nativeRecords[row]valueForKey:@"descriptor"];[b copyFromBuffer:qmd sourceOffset:0 toBuffer:qmdHosts[row]destinationOffset:0 size:256];}[b endEncoding];\n'
 '  icb=nil;[params removeAllObjects];')
source=replace_once(source,'  [runs addObject:@{@"trial":@(t)',
 '  NSMutableArray*qmdFiles=[NSMutableArray new];for(unsigned row=0;row<rows;row++){NSString*n=[NSString stringWithFormat:@"trial-%u-qmd-%u.bin",t,row];id<MTLBuffer>h=qmdHosts[row];[[NSData dataWithBytes:h.contents length:256]writeToFile:[out stringByAppendingPathComponent:n]atomically:YES];[qmdFiles addObject:n];}\n'
 '  [runs addObject:@{@"QMD_grid_override":@(KP_QMD_GRID_OVERRIDE),@"QMD_files":qmdFiles,@"trial":@(t)')
(out/'gpu_command_bindings_client.mm').write_text(source);shutil.copyfile(SDK/'include/KeplerCPUICB.h',out/'KeplerCPUICB.h');shutil.copyfile(ROOT/'src/qmd_grid_probe.metal',out/'qmd_grid_probe.metal')
def run(argv,label):
 r=subprocess.run([str(x)for x in argv],capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':[str(x)for x in argv],'label':label,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-3000:]
run(['xcrun','metal','-std=macos-metal2.0','-c',out/'qmd_grid_probe.metal','-o',out/'probe.air'],'metal')
run(['xcrun','metallib',out/'probe.air','-o',out/'assets/qmd_grid_probe.metallib'],'metallib')
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_QMD_GRID_OVERRIDE='+str(a.grid),'-I',SDK/'include',out/'gpu_command_bindings_client.mm','-L',SDK/'lib','-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
for n in ['combined_shared.metallib','cpu_icb_combined_shared_manifest.json','gpu_command_selector.metallib','gpu_command_geometry.metallib','gpu_command_bindings.metallib']:shutil.copyfile(SDK/'assets'/n,out/'assets'/n)
for n in ['run_sdk_host.py','lab_gpu_reservation.py']:shutil.copyfile(SDK/'runtime'/n,out/'runtime'/n)
inputs={'source_hashes':{n:sha(out/n)for n in ['gpu_command_bindings_client.mm','KeplerCPUICB.h','qmd_grid_probe.metal']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'executable_SHA256':sha(out/'application'),'runtime_SHA256':{n:sha(out/'runtime'/n)for n in ['run_sdk_host.py','lab_gpu_reservation.py']},'static_library_SHA256':sha(SDK/'lib/libKeplerMetal.a'),'QMD_grid_override':a.grid,'GPU_execution':False,'scope':'Laboratory access to owned plan records; this is not a public runtime API'}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps({'status':'PASS','grid':a.grid,'out':str(out)}))
