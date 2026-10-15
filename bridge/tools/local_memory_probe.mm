// SPDX-License-Identifier: MIT
// Native reference: private buffers, no program replacement or expected answers.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#ifndef KP_LOCAL_IMPORT
#define KP_LOCAL_IMPORT 0
#endif
#ifndef KP_LOCAL_EXTENDED
#define KP_LOCAL_EXTENDED 0
#endif
#if KP_LOCAL_IMPORT
#import "KeplerProgramImport.h"
#endif
struct Params { uint32_t seed, count, stride, reserved; };
static NSString *sha(NSData *data) {
 unsigned char d[32]; CC_SHA256(data.bytes,(CC_LONG)data.length,d);
 NSMutableString *s=[NSMutableString new];for(unsigned char b:d)[s appendFormat:@"%02x",b];return s;
}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=4)return 1;NSString *assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 BOOL imported=[mode hasPrefix:@"nak:"];NSString*selection=imported?[mode substringFromIndex:4]:mode;
 BOOL dispatch=![selection hasPrefix:@"no_dispatch:"];NSString *program=dispatch?selection:[selection substringFromIndex:12];NSString*name=[program stringByReplacingOccurrencesOfString:@"_forced_spill" withString:@""];
 if(![@[@"local_control",@"local32",@"local256",@"local1024",@"pressure32",@"pressure64",@"pressure96"]containsObject:name])return 1;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458&&[x.name isEqual:@"NVIDIA GeForce GTX 880M"])d=x;if(!d)return 2;
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSError*error=nil;NSDictionary*proof=@{},*info=@{};id<MTLComputePipelineState>pipeline=nil;NSString*carrierName=name;
 if(imported){
#if KP_LOCAL_IMPORT
  info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[program stringByAppendingString:@".json"]]]options:0 error:&error];
  if(![info[@"semantic"]isEqual:name]||[info[@"sm"]unsignedIntValue]!=30||[info[@"crs_bytes"]unsignedIntValue])return 3;
  BOOL pressure=[name hasPrefix:@"pressure"];if(pressure)carrierName=@"pressure96";unsigned frame=pressure?224:([name isEqual:@"local_control"]?0:[name substringFromIndex:5].intValue*4);
  KeplerLocalMemoryConfig config={[info[@"registers"]unsignedIntValue],[info[@"scratch_bytes"]unsignedIntValue],frame,pressure?224u:0u,pressure?1u:0u};
  if([info[@"control_barriers"]unsignedIntValue]!=config.carrier_control_barriers)return 3;
  NSMutableData*libraryBytes=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"local_memory.metallib"]]mutableCopy],*code=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[program stringByAppendingString:@".sass"]]]mutableCopy];
  pipeline=KPCreateLocalMemoryPipeline(d,libraryBytes,carrierName,code,config,&error,&proof);
  if(pipeline){[libraryBytes resetBytesInRange:NSMakeRange(0,libraryBytes.length)];[code resetBytesInRange:NSMakeRange(0,code.length)];}
#else
  return 3;
#endif
 }else{
  id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"local_memory.metallib"]]error:&error];id<MTLFunction>function=[library newFunctionWithName:name];pipeline=function?[d newComputePipelineStateWithFunction:function error:&error]:nil;
 }
 if(!pipeline){NSDictionary*r=@{@"failure":@"pipeline",@"error":error.description?:@"",@"import":proof?:@{},@"runs":@[]};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 3;}
 id<MTLCommandQueue>queue=[d newCommandQueue];NSMutableArray*runs=[NSMutableArray new];
#if KP_LOCAL_EXTENDED
 const unsigned counts[]={1,31,32,33,64,128,256,512,1024,99,256,2048};
 const unsigned locals[]={1,31,32,33,64,128,256,512,1024,33,64,1024};
#else
 const unsigned counts[]={32,64,256},locals[]={32,32,64};
#endif
 const unsigned trials=sizeof(counts)/sizeof(counts[0]);
 for(unsigned trial=0;trial<trials;trial++){@autoreleasepool{
  Params p={uint32_t(0x13579+trial*971),counts[trial],129,0};NSUInteger inputBytes=256+p.count*p.stride*4,outputBytes=256+p.count*16;
  id<MTLBuffer>input=[d newBufferWithLength:inputBytes options:MTLResourceStorageModePrivate],output=[d newBufferWithLength:outputBytes options:MTLResourceStorageModePrivate];
  id<MTLBuffer>hostInput=[d newBufferWithLength:inputBytes options:MTLResourceStorageModeShared],hostOutput=[d newBufferWithLength:outputBytes options:MTLResourceStorageModeShared];
  id<MTLBuffer>params=[d newBufferWithBytes:&p length:sizeof(p) options:MTLResourceStorageModeShared];if(!input||!output||!hostInput||!hostOutput||!params)return 4;
  memset(hostInput.contents,0xa5,inputBytes);memset(hostOutput.contents,0xa5,outputBytes);
  uint32_t*values=(uint32_t*)((uint8_t*)hostInput.contents+128);for(uint32_t i=0;i<p.count*p.stride;i++)values[i]=(i*1664525u+1013904223u)^p.seed;
  id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];
  [blit copyFromBuffer:hostInput sourceOffset:0 toBuffer:input destinationOffset:0 size:inputBytes];
  [blit copyFromBuffer:hostOutput sourceOffset:0 toBuffer:output destinationOffset:0 size:outputBytes];[blit endEncoding];
  if(dispatch){if(p.count%locals[trial]||pipeline.maxTotalThreadsPerThreadgroup<locals[trial])return 5;
   id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:pipeline];[e setBuffer:input offset:128 atIndex:0];[e setBuffer:output offset:128 atIndex:1];[e setBuffer:params offset:0 atIndex:2];
   [e dispatchThreadgroups:MTLSizeMake(p.count/locals[trial],1,1)threadsPerThreadgroup:MTLSizeMake(locals[trial],1,1)];[e endEncoding];}
  blit=[cb blitCommandEncoder];[blit copyFromBuffer:input sourceOffset:0 toBuffer:hostInput destinationOffset:0 size:inputBytes];[blit copyFromBuffer:output sourceOffset:0 toBuffer:hostOutput destinationOffset:0 size:outputBytes];[blit endEncoding];
  [cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"%s\n",cb.error.description.UTF8String);return 6;}
  NSString*inputFile=[NSString stringWithFormat:@"trial-%u-input.bin",trial],*outputFile=[NSString stringWithFormat:@"trial-%u-output.bin",trial];
  if(![[NSData dataWithBytes:hostInput.contents length:inputBytes]writeToFile:[out stringByAppendingPathComponent:inputFile]atomically:YES]||![[NSData dataWithBytes:hostOutput.contents length:outputBytes]writeToFile:[out stringByAppendingPathComponent:outputFile]atomically:YES])return 7;
  [runs addObject:@{@"trial":@(trial),@"threads":@(p.count),@"local":@(locals[trial]),@"groups":@(p.count/locals[trial]),@"seed":@(p.seed),@"stride":@(p.stride),@"command_status":@(cb.status),@"kernel_dispatches":@(dispatch?1:0),@"input_file":inputFile,@"output_file":outputFile,@"input_bytes":@(inputBytes),@"output_bytes":@(outputBytes)}];
 }}
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":sha(driver),@"mode":mode,@"function":name,@"program":program,@"carrier_function":carrierName,@"native_reference":@(!imported),@"program_replaced":@(imported),@"caller_inputs_mutated_after_import":@(imported),@"import":proof,@"program_info":info,@"trial_profile":KP_LOCAL_EXTENDED?@"extended":@"baseline",@"GPU_command_buffers":@(trials),@"thread_width":@(pipeline.threadExecutionWidth),@"max_threads":@(pipeline.maxTotalThreadsPerThreadgroup),@"static_threadgroup_bytes":@(pipeline.staticThreadgroupMemoryLength),@"CPU_expected_answers_uploaded":@NO,@"performance_benchmark":@NO,@"system_modified":@NO,@"runs":runs};
 NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
