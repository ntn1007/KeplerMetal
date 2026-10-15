#!/usr/bin/env python3
"""Build public-MSL producer + GPU native-command materializer client."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library-build',type=Path,required=True);p.add_argument('--compiler-build',type=Path,required=True);p.add_argument('--materializer-build',type=Path,default=ROOT/'results/command-ir-materializer-shader-build-20261015');p.add_argument('--consumer-profile',choices=['combined','manifest'],default='combined');p.add_argument('--ir-version',type=int,choices=[1,2],default=1);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir();lib=a.library_build.resolve();compiler=a.compiler_build.resolve();commands=[]
assert sha(lib/'libKeplerMetal.a')==json.loads((lib/'manifest.json').read_text())['static_library_SHA256']
def run(argv,label):
 r=subprocess.run([str(x)for x in argv],capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':[str(x)for x in argv],'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-3500:];return r
source=(SDK/'examples/gpu_command_bindings_client.mm').read_text()
def replace(before,after):
 global source
 assert source.count(before)==1,before[:120];source=source.replace(before,after,1)
replace('#import "KeplerCPUICB.h"','#import "KeplerCPUICB.h"\n#import "KeplerProgramImport.h"\nstruct ImportABI{uint64_t root;uint32_t grid[3],local[3];};')
replace('@[@"prepare",@"select",@"range",@"split",@"completed",@"copy",@"no_producer",@"no_selector"]','@[@"basic",@"barrier",@"clear",@"copy",@"reset",@"no_producer",@"split",@"bad_flags",@"bad_tag",@"bad_pipeline",@"bad_address",@"bad_parameters",@"bad_local",@"bad_shared",@"bad_groups",@"bad_y",@"bad_threads",@"bad_stage",@"bad_error",@"bad_reserved"]')
replace(' BOOL prepare=[mode isEqual:@"prepare"],split=[mode isEqual:@"split"],completed=[mode isEqual:@"completed"],copy=[mode isEqual:@"copy"],producer=![mode isEqual:@"no_producer"],selector=![mode isEqual:@"no_selector"];',' BOOL prepare=NO,split=[mode isEqual:@"split"],completed=NO,copy=NO,producer=![mode isEqual:@"no_producer"],selector=YES;')
replace(' NSUInteger rows=[mode isEqual:@"range"]?2:1,candidates=3,slots=candidates+rows*(copy?2:1);',' NSUInteger rows=[mode isEqual:@"copy"]?2:1,candidates=3,slots=candidates+rows;')
anchor=' const unsigned statics[3]'
replace(anchor,''' NSData*IRdata=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"command_ir_materializer.metallib"]];
 if(![scope enableGPUCommandIRWithLibraryData:IRdata expectedSHA256:sha(IRdata)error:&error]){fprintf(stderr,"%s\\n",error.description.UTF8String);return 3;}
 id<MTLLibrary>fieldLibrary=load(d,[assets stringByAppendingPathComponent:@"command_ir_field_probe.metallib"],&error);id<MTLComputePipelineState>fieldPSO=[d newComputePipelineStateWithFunction:[fieldLibrary newFunctionWithName:@"mutate_command_ir_data"]error:&error];if(!fieldPSO)return 3;
 NSString*semantic=([mode isEqual:@"no_producer"]||[mode isEqual:@"split"]||[mode hasPrefix:@"bad_"])?@"basic":mode;
 NSDictionary*programInfo=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".json"]]]options:0 error:nil];
 if([programInfo[@"sm"]unsignedIntValue]!=30||[programInfo[@"buffer_slots"]unsignedIntValue]!=1||[programInfo[@"grid_offset"]unsignedIntValue]!=8||[programInfo[@"push_bytes"]unsignedIntValue]!=32||[programInfo[@"command_ir_version"]unsignedIntValue]!=1||[programInfo[@"scratch_bytes"]unsignedIntValue]||[programInfo[@"crs_bytes"]unsignedIntValue])return 3;
 NSDictionary*importProof=nil;id<MTLComputePipelineState>IRproducer=KPCreatePipeline(d,[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"command_ir_carrier.metallib"]],@"command_ir_carrier",[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".sass"]]],{[programInfo[@"registers"]unsignedIntValue],576,576},&error,&importProof);
 if(!IRproducer||![importProof[@"contract_verified"]boolValue]){fprintf(stderr,"%s\\n",error.description.UTF8String);return 3;}
''' + anchor)
replace('192+rows*128 options:MTLResourceStorageModePrivate','192+8*128 options:MTLResourceStorageModePrivate')
replace('  for(unsigned row=0;row<rows;row++)for(unsigned i=0;i<32;i++){uint32_t x=17*i+t*3+row*11+(i==31?(t==2?2:t+1):0);memcpy((char*)inputHost.contents+128+row*128+i*4,&x,4);}','  // Upload canaries only. The public-MSL GPU producer writes all command state.')
replace('KPGPUCommandSelection*plan=[scope newGPUCommandBindingsFromBuffer:icb sourceRange:NSMakeRange(0,candidates)destination:icb destinationRange:NSMakeRange(candidates,rows)resources:resourceEntries input:input inputOffset:128 nonce:nonce error:&error];','KPGPUCommandSelection*plan=[scope newGPUCommandIRFromBuffer:icb sourceRange:NSMakeRange(0,candidates)destination:icb destinationRange:NSMakeRange(candidates,rows)resources:resourceEntries records:input recordOffset:128 error:&error];')
replace('  KPGPUCommandSelection*plan=[scope newGPUCommandIRFromBuffer:', '''  // Refusal checks use real owned buffers; no invalid record producer runs.
  if(t==0&&[mode isEqual:@"basic"]){
   id command=[icb indirectComputeCommandAtIndex:0];id native=[command valueForKey:@"record"];NSArray*aliases=@[outputs[0],counters[0],[native valueForKey:@"descriptor"],[native valueForKey:@"constants"]];
   for(id<MTLBuffer>alias in aliases){NSError*rejection=nil;id invalid=[scope newGPUCommandIRFromBuffer:icb sourceRange:NSMakeRange(0,candidates)destination:icb destinationRange:NSMakeRange(candidates,rows)resources:resourceEntries records:alias recordOffset:0 error:&rejection];if(invalid||![rejection.localizedDescription containsString:@"alias"])return 21;}
  }
  KPGPUCommandSelection*plan=[scope newGPUCommandIRFromBuffer:''')
replace('   if(![plan encodeProducerInCommandBuffer:pbuf error:&error])return 9;', '''   id<MTLBuffer>root=[plan newCommandIRArgumentsForCandidateIndex:(t+1)%3 resourceIndex:(t+2)%3 error:&error];if(!root)return 9;
   ImportABI push={root.gpuAddress,{32,1,1},{32,1,1}};id<MTLBuffer>pushBuffer=[d newBufferWithBytes:&push length:sizeof push options:MTLResourceStorageModeShared];
   id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:IRproducer];[e setBuffer:pushBuffer offset:0 atIndex:0];[e setBuffer:input offset:128 atIndex:1];[e useResource:root usage:MTLResourceUsageRead];for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
   NSArray*keep=@[root,pushBuffer,IRproducer,plan.commandIRProducerResources];[pbuf addCompletedHandler:^(id<MTLCommandBuffer>c){(void)keep.count;}];''')
replace('if(![plan encodeSelectionInCommandBuffer:sbuf error:&error])','if(![plan encodeCommandIRInCommandBuffer:sbuf afterProducer:producer?pbuf:nil error:&error])')
replace('  if(split)[pbuf commit];','''  if([mode hasPrefix:@"bad_"]){
   NSDictionary*mutations=@{@"bad_flags":@[@1,@0x177],@"bad_tag":@[@3,@0x4b504951],@"bad_pipeline":@[@2,@8],@"bad_address":@[@12,@1],@"bad_parameters":@[@16,@1],@"bad_local":@[@8,@0],@"bad_shared":@[@18,@49152],@"bad_groups":@[@4,@8],@"bad_y":@[@5,@2],@"bad_threads":@[@7,@1],@"bad_stage":@[@1,@0xf7],@"bad_error":@[@19,@1],@"bad_reserved":@[@20,@1]};NSArray*change=mutations[mode];uint32_t v[2]={[change[0]unsignedIntValue],[change[1]unsignedIntValue]};
   id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:fieldPSO];[e setBuffer:input offset:128 atIndex:0];[e setBytes:v length:8 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];[e endEncoding];
  }
  if(split)[pbuf commit];''')
replace('@"mode":mode,@"device":d.name','@"public_MSL_command_IR_consumed":@YES,@"producer_info":programInfo,@"producer_import":importProof,@"mode":mode,@"device":d.name')
if a.consumer_profile=='manifest':
 replace('NSArray*names=@[@"shared_mix_s128",@"shared_mix_s1024",@"shared_mix_s4096"]','NSArray*names=@[@"manifest_mix",@"manifest_dynamic",@"manifest_dynamic"]')
 replace('const unsigned statics[3]={512,4096,16384}','const unsigned statics[3]={0,0,0}')
 replace('db=k<3?49152-sb:1024*(k+1)','db=index==0?0u:(k<3?49152u:1024u*(k+1))')
 replace('[c setThreadgroupMemoryLength:[s[@"dynamic_bytes"]unsignedIntegerValue]atIndex:0];','if([s[@"dynamic_bytes"]unsignedIntValue])[c setThreadgroupMemoryLength:[s[@"dynamic_bytes"]unsignedIntegerValue]atIndex:0];')
 replace('uint32_t v[2]={[change[0]unsignedIntValue],[change[1]unsignedIntValue]};','uint32_t v[2]={[change[0]unsignedIntValue],[change[1]unsignedIntValue]};if([mode isEqual:@"bad_shared"])v[1]=[specs[(t+1)%3][@"dynamic_bytes"]unsignedIntValue]^16u;')
if a.ir_version==2:
 replace('enableGPUCommandIRWithLibraryData:IRdata','enableGPUCommandIRv2WithLibraryData:IRdata')
 source=source.replace('newGPUCommandIRFromBuffer:','newGPUCommandIRv2FromBuffer:')
 source=source.replace('resources:resourceEntries records:','resources:IRresources records:')
 replace('  // Refusal checks use real owned buffers;', '  NSMutableArray*IRresources=[NSMutableArray new];for(NSDictionary*x in resourceEntries)[IRresources addObject:@{@"bindings":@[@{@"buffer":x[@"output"],@"offset":x[@"outputOffset"]},@{@"buffer":x[@"counter"],@"offset":x[@"counterOffset"]}]}];\n  // Refusal checks use real owned buffers;')
 replace('[programInfo[@"command_ir_version"]unsignedIntValue]!=1','[programInfo[@"command_ir_version"]unsignedIntValue]!=2')
producerMSL=(compiler/'gpu_command_frontend.metal').read_text()
dispatchKind='threads' if 'C.concurrent_dispatch_threads('in producerMSL else 'threadgroups'
assert dispatchKind=='threads' or 'C.concurrent_dispatch_threadgroups('in producerMSL
if dispatchKind=='threads':
 replace('if([mode isEqual:@"bad_shared"])v[1]=[specs[(t+1)%3][@"dynamic_bytes"]unsignedIntValue]^16u;','if([mode isEqual:@"bad_shared"])v[1]=[specs[(t+1)%3][@"dynamic_bytes"]unsignedIntValue]^16u;if([mode isEqual:@"bad_threads"]){v[0]=4;v[1]=1u;}')
source=source.replace('@"public_MSL_command_IR_consumed":@YES','@"command_IR_version":@'+str(a.ir_version)+',@"consumer_profile":@"'+a.consumer_profile+'",@"dispatch_kind":@"'+dispatchKind+'",@"public_MSL_command_IR_consumed":@YES')
(out/'gpu_command_bindings_client.mm').write_text(source)
for n in ['KeplerCPUICB.h','KeplerProgramImport.h']:shutil.copyfile(ROOT/'src'/n,out/n)
shutil.copyfile(ROOT/'src/KeplerProgramImport.mm',out/'KeplerProgramImport.mm')
for name in ['basic','barrier','clear','copy','reset']:
 dest=out/('compiled-'+name);dest.mkdir();r=run([compiler/'air_command_compile',compiler/'producer.air',dest,'encode_runtime_'+name,'32','2',a.ir_version],'compile-'+name);info=json.loads(r.stdout);assert info['command_ir_version']==a.ir_version and info['registers']<=63 and not any(info[k]for k in ['scratch_bytes','crs_bytes','shared_bytes']);shutil.copyfile(dest/'program.sass',out/'assets'/(name+'.sass'));(out/'assets'/(name+'.json')).write_text(json.dumps(info,indent=2)+'\n')
shutil.copyfile(ROOT/'results/gpu-command-ir-host-build-20261015-04/command_ir_carrier.metallib',out/'assets/command_ir_carrier.metallib')
shutil.copyfile(a.materializer_build.resolve()/'command_ir_materializer.metallib',out/'assets/command_ir_materializer.metallib')
for n in ['combined_shared.metallib','cpu_icb_combined_shared_manifest.json','gpu_command_selector.metallib','gpu_command_geometry.metallib','gpu_command_bindings.metallib']:shutil.copyfile(SDK/'assets'/n,out/'assets'/n)
if a.consumer_profile=='manifest':
 shutil.copyfile(ROOT/'results/cpu-icb-manifest-gpu-qualified/cpu_icb_manifest.metallib',out/'assets/combined_shared.metallib')
 shutil.copyfile(ROOT/'src/cpu_icb_dynamic_resident_manifest.json',out/'assets/cpu_icb_combined_shared_manifest.json')
for n in ['run_sdk_host.py','lab_gpu_reservation.py']:shutil.copyfile(SDK/'runtime'/n,out/'runtime'/n)
shutil.copyfile(ROOT/'src/command_ir_field_probe.metal',out/'command_ir_field_probe.metal')
run(['xcrun','metal','-std=macos-metal2.0','-c',out/'command_ir_field_probe.metal','-o',out/'field.air'],'field-metal')
run(['xcrun','metallib',out/'field.air','-o',out/'assets/command_ir_field_probe.metallib'],'field-metallib')
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o'],'import-MRC')
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/'gpu_command_bindings_client.mm',out/'KeplerProgramImport.o','-L',lib,'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
(out/'inputs.json').write_text(json.dumps({'source_hashes':{n:sha(out/n)for n in ['gpu_command_bindings_client.mm','KeplerCPUICB.h','KeplerProgramImport.h','KeplerProgramImport.mm']},'assets_SHA256':{p.name:sha(p)for p in(out/'assets').iterdir()},'executable_SHA256':sha(out/'application'),'runtime_SHA256':{n:sha(out/'runtime'/n)for n in ['run_sdk_host.py','lab_gpu_reservation.py']},'static_library_SHA256':sha(lib/'libKeplerMetal.a'),'library_manifest_SHA256':sha(lib/'manifest.json'),'compiler_manifest_SHA256':sha(compiler/'manifest.json'),'GPU_execution':False},indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'GPU_execution':False}))
