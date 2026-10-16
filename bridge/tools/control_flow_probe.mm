// SPDX-License-Identifier: MIT
// Native-only reference. No constructor replacement or program import.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#import <objc/runtime.h>
#ifndef KP_CONTROL_IMPORT
#define KP_CONTROL_IMPORT 0
#endif
#if KP_NATIVE_RESERVE_EXPERIMENT
extern "C" id<MTLComputePipelineState> KPExperimentalCreateNativeReservePipeline(id<MTLDevice>,NSURL*,NSString*,NSData*,NSString*,uint32_t,NSError**,NSDictionary**) NS_RETURNS_RETAINED;
#endif
#if KP_CONTROL_IMPORT
extern "C" id<MTLComputePipelineState> KPInternalCASCreatePreservingNativeCASPipeline(
 id<MTLDevice>,NSURL*,NSString*,NSData*,NSData*,NSError**,NSDictionary**) NS_RETURNS_RETAINED;
#endif
struct Params {uint32_t seed,count,stride,reserved;};
static NSString *sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 BOOL imported=[mode hasPrefix:@"nak:"];NSString*selection=imported?[mode substringFromIndex:4]:mode;
 BOOL dispatch=![selection hasPrefix:@"no_dispatch:"];NSString*name=dispatch?selection:[selection substringFromIndex:12];
 if(![name hasPrefix:@"depth"]||name.length<6)return 1;NSString*digits=[name substringFromIndex:5];if([digits rangeOfCharacterFromSet:NSCharacterSet.decimalDigitCharacterSet.invertedSet].location!=NSNotFound||digits.intValue>120)return 1;
 unsigned depth=[[name substringFromIndex:5]intValue];id<MTLDevice>d=nil;
 NSData*configuration=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"control_flow_config.json"]];NSDictionary*config=configuration?[NSJSONSerialization JSONObjectWithData:configuration options:0 error:nil]:@{};NSString*variant=config[@"variant"]?:@"nested";
 if(![@[@"nested",@"reload_bounds",@"serial",@"pressure"]containsObject:variant])return 1;
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458&&[x.name isEqual:@"NVIDIA GeForce GTX 880M"])d=x;
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(!d||![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSError*error=nil;NSDictionary*proof=@{},*profile=@{};id<MTLComputePipelineState>pso=nil;
 NSURL*libraryURL=[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"control_flow.metallib"]];
 if(imported){
#if KP_CONTROL_IMPORT
  profile=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".json"]]]options:0 error:&error];
  NSDictionary*info=profile[@"program_info"],*carrier=profile[@"carrier"];NSArray*w=carrier[@"metadata_words"],*v=carrier[@"variant_words_0_128"];
  if(w.count!=58||v.count!=32||![info[@"semantic"]isEqual:name]||[info[@"sm"]unsignedIntValue]!=30||[info[@"shared_bytes"]unsignedIntValue]||[w[35]unsignedIntValue])return 8;
  uint32_t scratch=[info[@"scratch_bytes"]unsignedIntValue],crs=[info[@"crs_bytes"]unsignedIntValue],registers=[info[@"registers"]unsignedIntValue];
  uint32_t frame=[w[12]unsignedIntValue],control=[w[11]unsignedIntValue],capacity=(control+511u)&~511u;
  if(registers<24||registers>[w[7]unsignedIntValue]||scratch>frame||crs>capacity||[w[13]unsignedIntValue]!=frame||[w[9]unsignedIntValue]!=64u*frame+control)return 8;
  NSMutableData*original=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[carrier[@"function"]stringByAppendingString:@"-native.sass"]]]mutableCopy];
  NSMutableData*code=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".sass"]]]mutableCopy];
  if(![sha(original)isEqual:carrier[@"code_SHA256"]]||![sha(code)isEqual:profile[@"code_SHA256"]]||code.length!=[info[@"code_bytes"]unsignedIntValue])return 8;
  Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));if(!method)return 8;IMP before=method_getImplementation(method);
  pso=KPInternalCASCreatePreservingNativeCASPipeline(d,libraryURL,carrier[@"function"],original,code,&error,&proof);
  if(method_getImplementation(method)!=before)return 8;
  BOOL valid=pso&&[proof[@"contract_verified"]boolValue]&&![proof[@"rejected_import"]boolValue];unsigned matched=0;
  for(NSDictionary*e in proof[@"events"])if([e[@"code_replaced"]boolValue]){
   matched++;valid=valid&&[e[@"imported_code_identical"]boolValue]&&[e[@"native_metadata_preserved_except_instruction_count"]boolValue]&&[e[@"code_input_unchanged_after_constructor"]boolValue];
   valid=valid&&[e[@"decoded_code_bytes"]unsignedIntValue]==code.length&&[e[@"decoded_registers"]unsignedIntValue]==[w[7]unsignedIntValue]&&[e[@"decoded_instruction_count"]unsignedIntValue]==code.length/8-1;
   valid=valid&&[e[@"decoded_allocation_word_40"]unsignedIntValue]==[v[10]unsignedIntValue]&&[e[@"decoded_spill_bytes_56"]unsignedIntValue]==[v[14]unsignedIntValue]&&[e[@"launch_words_9_11"]isEqual:@[w[9],w[11]]];
  }
  if(!valid||!matched)return 8;
  [original resetBytesInRange:NSMakeRange(0,original.length)];[code resetBytesInRange:NSMakeRange(0,code.length)];
#else
  return 8;
#endif
 }else{
#if KP_NATIVE_RESERVE_EXPERIMENT
  NSDictionary*cert=config[@"certificates"][name];NSArray*w=cert[@"metadata_words"];if(w.count!=58)return 8;
  uint32_t reserve=[config[@"control_reserve"]isEqual:@"round"]?([w[11]unsignedIntValue]+511)&~511u:[config[@"control_reserve"]unsignedIntValue];
  NSMutableData*metadata=[NSMutableData dataWithLength:232];for(unsigned i=0;i<58;i++){uint32_t v=[w[i]unsignedIntValue];memcpy((char*)metadata.mutableBytes+4*i,&v,4);}
  pso=KPExperimentalCreateNativeReservePipeline(d,libraryURL,name,metadata,cert[@"code_SHA256"],reserve,&error,&proof);
#else
  id<MTLLibrary>lib=[d newLibraryWithURL:libraryURL error:&error];id<MTLFunction>f=[lib newFunctionWithName:name];pso=f?[d newComputePipelineStateWithFunction:f error:&error]:nil;
#endif
 }
 if(!pso){NSDictionary*failure=@{@"failure":@"pipeline",@"error":error.description?:@"",@"evidence":proof?:@{},@"runs":@[]};NSData*j=[NSJSONSerialization dataWithJSONObject:failure options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 id<MTLCommandQueue>q=[d newCommandQueue];NSMutableArray*runs=[NSMutableArray new];
 const unsigned counts[]={1,31,32,33,64,128,256,512,1024,99,256,2048};
 const unsigned locals[]={1,31,32,33,64,128,256,512,1024,33,64,1024};
 for(unsigned trial=0;trial<12;trial++){@autoreleasepool{
  Params p={0x13579+trial*971,counts[trial],129,trial%3};NSUInteger inBytes=256+p.count*p.stride*4,outBytes=256+p.count*16;
  id<MTLBuffer>input=[d newBufferWithLength:inBytes options:MTLResourceStorageModePrivate],output=[d newBufferWithLength:outBytes options:MTLResourceStorageModePrivate];
  id<MTLBuffer>hi=[d newBufferWithLength:inBytes options:MTLResourceStorageModeShared],ho=[d newBufferWithLength:outBytes options:MTLResourceStorageModeShared];
  id<MTLBuffer>params=[d newBufferWithBytes:&p length:sizeof(p) options:MTLResourceStorageModeShared];if(!input||!output||!hi||!ho||!params)return 4;
  memset(hi.contents,0xa5,inBytes);memset(ho.contents,0xa5,outBytes);uint32_t*v=(uint32_t*)((uint8_t*)hi.contents+128);
  for(unsigned i=0;i<p.count*p.stride;i++)v[i]=(i*1664525u+1013904223u)^p.seed;
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];
  [b copyFromBuffer:hi sourceOffset:0 toBuffer:input destinationOffset:0 size:inBytes];[b copyFromBuffer:ho sourceOffset:0 toBuffer:output destinationOffset:0 size:outBytes];[b endEncoding];
  if(dispatch){if(p.count%locals[trial]||pso.maxTotalThreadsPerThreadgroup<locals[trial])return 5;
   id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:pso];[e setBuffer:input offset:128 atIndex:0];[e setBuffer:output offset:128 atIndex:1];[e setBuffer:params offset:0 atIndex:2];
   [e dispatchThreadgroups:MTLSizeMake(p.count/locals[trial],1,1)threadsPerThreadgroup:MTLSizeMake(locals[trial],1,1)];[e endEncoding];}
  b=[cb blitCommandEncoder];[b copyFromBuffer:input sourceOffset:0 toBuffer:hi destinationOffset:0 size:inBytes];[b copyFromBuffer:output sourceOffset:0 toBuffer:ho destinationOffset:0 size:outBytes];[b endEncoding];[cb commit];[cb waitUntilCompleted];
  if(cb.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"%s\n",cb.error.description.UTF8String);return 6;}
  NSString*inf=[NSString stringWithFormat:@"trial-%u-input.bin",trial],*ouf=[NSString stringWithFormat:@"trial-%u-output.bin",trial];
  if(![[NSData dataWithBytes:hi.contents length:inBytes]writeToFile:[out stringByAppendingPathComponent:inf]atomically:YES]||![[NSData dataWithBytes:ho.contents length:outBytes]writeToFile:[out stringByAppendingPathComponent:ouf]atomically:YES])return 7;
  [runs addObject:@{@"trial":@(trial),@"threads":@(p.count),@"local":@(locals[trial]),@"groups":@(p.count/locals[trial]),@"seed":@(p.seed),@"stride":@(p.stride),@"reserved":@(p.reserved),@"input_bytes":@(inBytes),@"output_bytes":@(outBytes),@"input_file":inf,@"output_file":ouf,@"kernel_dispatches":@(dispatch?1:0),@"command_status":@(cb.status)}];
 }}
 NSDictionary*result=@{@"variant":variant,@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":sha(driver),@"mode":mode,@"function":name,@"depth":@(depth),@"native_reference":@(!imported),@"program_replaced":@(imported),@"caller_inputs_mutated_after_import":@(imported),@"import":proof,@"profile":profile,@"CPU_expected_answers_uploaded":@NO,@"performance_benchmark":@NO,@"system_modified":@NO,@"GPU_command_buffers":@12,@"thread_width":@(pso.threadExecutionWidth),@"max_threads":@(pso.maxTotalThreadsPerThreadgroup),@"runs":runs};
 NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
