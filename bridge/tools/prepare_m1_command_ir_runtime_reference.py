#!/usr/bin/env python3
"""Prepare a native M1 client for the SAME public-MSL runtime producer source."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK'
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--consumer-profile',choices=['combined','manifest'],default='combined');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
s=(SDK/'examples/gpu_command_bindings_client.mm').read_text()
def replace(before,after):
 global s
 assert s.count(before)==1,before[:120];s=s.replace(before,after,1)
def block(start,end,body):
 global s
 assert s.count(start)==1 and s.count(end)==1
 a=s.index(start)+len(start);b=s.index(end,a);s=s[:a]+body+s[b:]
replace('@[@"prepare",@"select",@"range",@"split",@"completed",@"copy",@"no_producer",@"no_selector"]','@[@"basic",@"barrier",@"clear",@"copy",@"reset",@"no_producer",@"split"]')
replace(' BOOL prepare=[mode isEqual:@"prepare"],split=[mode isEqual:@"split"],completed=[mode isEqual:@"completed"],copy=[mode isEqual:@"copy"],producer=![mode isEqual:@"no_producer"],selector=![mode isEqual:@"no_selector"];',' BOOL prepare=NO,split=[mode isEqual:@"split"],completed=NO,copy=NO,producer=![mode isEqual:@"no_producer"],selector=YES;')
replace(' NSUInteger rows=[mode isEqual:@"range"]?2:1,candidates=3,slots=candidates+rows*(copy?2:1);',' NSUInteger rows=[mode isEqual:@"copy"]?2:1,candidates=3,slots=candidates+rows;')
block('#if KP_SELECT_NATIVE\n id<MTLLibrary>library=', '\n#else\n KPCPUICBScope*scope=', '''load(d,[assets stringByAppendingPathComponent:@"combined_shared.metallib"],&error),producerLibrary=load(d,[assets stringByAppendingPathComponent:@"runtime_producer.metallib"],&error);if(!library||!producerLibrary)return 3;
 for(NSString*n in names){MTLComputePipelineDescriptor*x=[MTLComputePipelineDescriptor new];x.computeFunction=[library newFunctionWithName:n];x.supportIndirectCommandBuffers=YES;id<MTLComputePipelineState>p=[d newComputePipelineStateWithDescriptor:x options:MTLPipelineOptionNone reflection:nil error:&error];if(!p)return 3;pipelines[n]=p;}
 NSString*semantic=([mode isEqual:@"no_producer"]||[mode isEqual:@"split"])?@"basic":mode;
 id<MTLFunction>producerFunction=[producerLibrary newFunctionWithName:[@"encode_runtime_"stringByAppendingString:semantic]];
 id<MTLComputePipelineState>producerPSO=[d newComputePipelineStateWithFunction:producerFunction error:&error];if(!producerPSO)return 3;
'''.replace('@"encode_runtime_"string','@"encode_runtime_" string'))
block('#if KP_SELECT_NATIVE\n  geometry=', '\n#else\n  if(![scope prepareResidentComputeCommands:', '''[d newBufferWithLength:128+rows*32 options:MTLResourceStorageModePrivate];choices=[d newBufferWithLength:128+rows*16 options:MTLResourceStorageModePrivate];counts=[d newBufferWithLength:128+rows*8 options:MTLResourceStorageModePrivate];
  init=[q commandBuffer];b=[init blitCommandEncoder];for(id<MTLBuffer>r in @[geometry,choices,counts])[b fillBuffer:r range:NSMakeRange(0,r.length)value:0xa5];[b fillBuffer:geometry range:NSMakeRange(64,rows*32)value:0];[b fillBuffer:choices range:NSMakeRange(64,rows*16)value:0];[b fillBuffer:counts range:NSMakeRange(64,rows*8)value:0];[b endEncoding];if(!done(init))return 7;
  id<MTLIndirectCommandBuffer>nativeTarget=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:rows options:MTLResourceStorageModeShared];[nativeTarget resetWithRange:NSMakeRange(0,rows)];
  id<MTLArgumentEncoder>argumentEncoder=[producerFunction newArgumentEncoderWithBufferIndex:0],resourceEncoder=nil;id<MTLBuffer>argument=[d newBufferWithLength:argumentEncoder.encodedLength options:MTLResourceStorageModeShared];[argumentEncoder setArgumentBuffer:argument offset:0];
  unsigned candidate=(t+1)%3,resource=(t+2)%3;NSDictionary*entry=resourceEntries[resource];[argumentEncoder setIndirectCommandBuffer:nativeTarget atIndex:0];[argumentEncoder setComputePipelineState:pipelines[specs[candidate][@"function"]]atIndex:1];[argumentEncoder setBuffer:entry[@"output"]offset:[entry[@"outputOffset"]unsignedIntegerValue]atIndex:2];[argumentEncoder setBuffer:entry[@"counter"]offset:[entry[@"counterOffset"]unsignedIntegerValue]atIndex:3];[argumentEncoder setBuffer:params[candidate]offset:1024 atIndex:4];
''')
replace('   id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:producerPSO];[e setBuffer:input offset:128 atIndex:0];[e setBuffer:choices offset:64 atIndex:1];[e setBuffer:counts offset:64 atIndex:2];[e setBuffer:producerConfig offset:0 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(rows,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];', '''   id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:producerPSO];[e setBuffer:argument offset:0 atIndex:0];[e useResource:nativeTarget usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(NSDictionary*x in resourceEntries){[e useResource:x[@"output"]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e useResource:x[@"counter"]usage:MTLResourceUsageRead|MTLResourceUsageWrite];}for(id<MTLBuffer>p in params)[e useResource:p usage:MTLResourceUsageRead];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(rows,1,1)];[e endEncoding];''')
block('#if KP_SELECT_NATIVE\n   for(unsigned row=0;row<rows;row++){id<MTLComputeCommandEncoder>e=', '\n#else\n   if(![plan encodeSelectionInCommandBuffer:', '''[sbuf computeCommandEncoder];[e endEncoding];}
''')
replace('[e executeCommandsInBuffer:icb withRange:NSMakeRange(executeIndex,rows)]','[e executeCommandsInBuffer:nativeTarget withRange:NSMakeRange(0,rows)]')
replace('NSArray*keep=@[icb,[pipelines.allValues copy],[params copy],argument,producerConfig,[selectorConfigs copy],limits,geometry,resourceArgument,[resourceEntries copy]]','NSArray*keep=@[icb,nativeTarget,[pipelines.allValues copy],[params copy],argument,geometry,[resourceEntries copy],producerPSO]')
if a.consumer_profile=='manifest':
 replace('NSArray*names=@[@"shared_mix_s128",@"shared_mix_s1024",@"shared_mix_s4096"]','NSArray*names=@[@"manifest_mix",@"manifest_dynamic",@"manifest_dynamic"]')
 replace('const unsigned statics[3]={512,4096,16384}','const unsigned statics[3]={0,0,0}')
 replace('db=k<3?49152-sb:1024*(k+1)','db=index==0?0u:(k<3?49152u:1024u*(k+1))')
 replace('[c setThreadgroupMemoryLength:[s[@"dynamic_bytes"]unsignedIntegerValue]atIndex:0];','if([s[@"dynamic_bytes"]unsignedIntValue])[c setThreadgroupMemoryLength:[s[@"dynamic_bytes"]unsignedIntegerValue]atIndex:0];')
(out/'gpu_command_bindings_client.mm').write_text(s)
for path in [ROOT/'src/gpu_command_frontend_runtime.metal',ROOT/'src/cpu_icb_combined_shared.metal',ROOT/'src/cpu_icb_combined_shared_manifest.json',ROOT/'src/KeplerCPUICB.h',SDK/'runtime/run_sdk_host.py',SDK/'runtime/lab_gpu_reservation.py']:shutil.copyfile(path,out/path.name)
if a.consumer_profile=='manifest':
 shutil.copyfile(ROOT/'src/gpu_command_frontend_general.metal',out/'gpu_command_frontend_runtime.metal')
 shutil.copyfile(ROOT/'src/cpu_icb_manifest.metal',out/'cpu_icb_combined_shared.metal')
 shutil.copyfile(ROOT/'src/cpu_icb_dynamic_resident_manifest.json',out/'cpu_icb_combined_shared_manifest.json')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
(out/'FILE_MANIFEST.json').write_text(json.dumps({'files':[{'path':p.name,'SHA256':sha(p),'bytes':p.stat().st_size}for p in sorted(out.iterdir())]},indent=2)+'\n')
print(json.dumps({'status':'PASS','source':str(out),'public_MSL_SHA256':sha(out/'gpu_command_frontend_runtime.metal')}))
