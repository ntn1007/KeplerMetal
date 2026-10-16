// SPDX-License-Identifier: MIT
// Read-only own-process command snapshots. Never commit, patch or replay packets.
#import "KeplerNativeAllocation.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <cstring>
#include <initializer_list>

static NSData *readMemory(uintptr_t address,size_t bytes) {
 if(!address||!bytes||bytes>65536||address+bytes<address)return nil;
 NSMutableData*data=[NSMutableData dataWithLength:bytes];mach_vm_size_t read=0;
 return mach_vm_read_overwrite(mach_task_self(),address,bytes,(mach_vm_address_t)data.mutableBytes,&read)==KERN_SUCCESS&&read==bytes?data:nil;
}
static uint32_t u32(NSData*d,size_t at){uint32_t v=0;if(at+4<=d.length)memcpy(&v,(const char*)d.bytes+at,4);return v;}
static uint64_t u64(NSData*d,size_t at){uint64_t v=0;if(at+8<=d.length)memcpy(&v,(const char*)d.bytes+at,8);return v;}
static NSString*sha(NSData*d){if(!d)return @"";unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString string];for(unsigned char x:h)[s appendFormat:@"%02x",x];return s;}
static id json(NSData*d){return d?[NSJSONSerialization JSONObjectWithData:d options:0 error:nil]:nil;}
static void emit(NSDictionary*d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
struct Cursor{uintptr_t implementation=0,push=0,current=0,end=0;bool valid=false;};
static Cursor cursor(id<MTLComputeCommandEncoder>encoder) {
 Cursor c;Ivar field=class_getInstanceVariable(object_getClass(encoder),"m_compute");
 if(!field||ivar_getOffset(field)!=120||class_getInstanceSize(object_getClass(encoder))!=128||!ivar_getTypeEncoding(field)||ivar_getTypeEncoding(field)[0]!='^')return c;
 memcpy(&c.implementation,(const char*)(__bridge const void*)encoder+120,8);
 NSData*impl=readMemory(c.implementation,64);if(impl.length!=64)return c;
 c.push=u64(impl,32);NSData*push=readMemory(c.push,144);if(push.length!=144)return c;
 c.current=u64(push,0);c.end=u64(push,136);c.valid=c.current&&c.current<=c.end&&c.end-c.current<=1024*1024;return c;
}
static NSDictionary*info(Cursor c){return @{@"implementation":@(c.implementation),@"push":@(c.push),@"current":@(c.current),@"end":@(c.end),@"valid":@(c.valid)};}
static NSData *variant(id<MTLComputePipelineState>pipeline) {
 if(![NSStringFromClass(object_getClass(pipeline))isEqual:@"NVMTLComputePipelineState"])return nil;
 Ivar field=class_getInstanceVariable(object_getClass(pipeline),"_computePipeline");
 if(!field||ivar_getOffset(field)!=72||!ivar_getTypeEncoding(field)||ivar_getTypeEncoding(field)[0]!='^')return nil;
 uintptr_t ptr=0;memcpy(&ptr,(const char*)(__bridge const void*)pipeline+72,8);NSData*state=readMemory(ptr,32);
 if(state.length!=32||u64(state,8)!=(uintptr_t)(__bridge const void*)pipeline||!u64(state,16))return nil;
 id owner=(__bridge id)(void*)(uintptr_t)u64(state,16);
 if(![NSStringFromClass(object_getClass(owner))isEqual:@"NVMTLFunctionVariant"])return nil;
 field=class_getInstanceVariable(object_getClass(owner),"_variant");
 if(!field||ivar_getOffset(field)!=32||!ivar_getTypeEncoding(field)||ivar_getTypeEncoding(field)[0]!='^')return nil;
 memcpy(&ptr,(const char*)(__bridge const void*)owner+32,8);return readMemory(ptr,128);
}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSArray*parts=[mode componentsSeparatedByString:@":"];
 if(parts.count!=2||![@[@"native",@"reserved"]containsObject:parts[0]])return 1;
 BOOL corrected=[parts[0]isEqual:@"reserved"];NSString*name=parts[1];
 NSDictionary*manifest=json([NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"native-allocation-manifest.json"]]);
 NSDictionary*entry=manifest[@"certificates"][name];if(![entry isKindOfClass:NSDictionary.class])return 1;
 NSData*libraryData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"control_flow.metallib"]];
 NSData*certificateData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:entry[@"file"]]];NSDictionary*cert=json(certificateData);
 if(![sha(libraryData)isEqual:manifest[@"library_sha256"]]||![sha(certificateData)isEqual:entry[@"SHA256"]]||![cert[@"function"]isEqual:name])return 2;
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(d.registryID==4294968458&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"])device=d;
 NSString*driverHash=sha([NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"]);
 if(!device||![driverHash isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSError*error=nil;NSDictionary*proof=@{};id<MTLComputePipelineState>pipeline=nil;
 if(corrected) pipeline=KPCreateCertifiedNativeAllocationPipeline(device,libraryData,manifest[@"library_sha256"],certificateData,entry[@"SHA256"],&error,&proof);
 else {
  dispatch_data_t data=dispatch_data_create(libraryData.bytes,libraryData.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)libraryData.length;});
  id<MTLLibrary>library=[device newLibraryWithData:data error:&error];id<MTLFunction>function=[library newFunctionWithName:name];
  if(function)pipeline=[device newComputePipelineStateWithFunction:function error:&error];
 }
 if(!pipeline){emit(@{@"status":@"PIPELINE_REFUSED",@"mode":mode,@"error":error.description?:@"",@"import":proof?:@{},@"runs":@[]});return 3;}
 NSData*fields=variant(pipeline);NSArray*w=cert[@"metadata_words"];
 if(fields.length!=128||u64(fields,24)!=[cert[@"code_bytes"]unsignedIntegerValue]||u32(fields,48)!=[w[7]unsignedIntValue]||u32(fields,56)!=[w[14]unsignedIntValue]){
  emit(@{@"status":@"VARIANT_REFUSED",@"mode":mode,@"field_bytes":@(fields.length),@"pipeline_class":NSStringFromClass(object_getClass(pipeline)),@"runs":@[]});return 3;
 }
 const uint32_t groups=3,local=33,count=groups*local;uint32_t params[4]={0x13579,count,129,2};
 id<MTLBuffer>input=[device newBufferWithLength:256+count*129*4 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>output=[device newBufferWithLength:256+count*16 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>parameters=[device newBufferWithLength:512 options:MTLResourceStorageModeShared];
 if(!input||!output||!parameters)return 4;memset(parameters.contents,0xa5,parameters.length);memcpy(parameters.contents,params,sizeof(params));
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];
 [encoder setComputePipelineState:pipeline];[encoder setBuffer:input offset:128 atIndex:0];[encoder setBuffer:output offset:128 atIndex:1];[encoder setBuffer:parameters offset:0 atIndex:2];
 NSMutableArray*records=[NSMutableArray array];BOOL complete=YES;
 for(unsigned step=0;step<3;step++){
  Cursor before=cursor(encoder);[encoder dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];Cursor after=cursor(encoder);
  BOOL valid=before.valid&&after.valid&&before.push==after.push&&before.current&&after.current>before.current&&after.current<=before.end&&after.current-before.current<=65536;
  NSData*bytes=valid?readMemory(before.current,after.current-before.current):nil;NSString*file=[NSString stringWithFormat:@"step-%u.commands.bin",step];
  BOOL saved=bytes.length&&[bytes writeToFile:[out stringByAppendingPathComponent:file]atomically:YES];complete=complete&&saved;
  [records addObject:@{@"step":@(step),@"before":info(before),@"after":info(after),@"range_comparable":@(valid),@"file":file,@"bytes":@(bytes.length),@"SHA256":sha(bytes),@"saved":@(saved)}];
 }
 [encoder endEncoding];BOOL uncommitted=command.status==MTLCommandBufferStatusNotEnqueued;
 NSData*fieldsAfter=variant(pipeline);complete=complete&&fieldsAfter.length==128;
 BOOL variantStable=fieldsAfter.length==128&&u64(fields,24)==u64(fieldsAfter,24);
 for(unsigned offset:{40u,44u,48u,56u})variantStable=variantStable&&u32(fields,offset)==u32(fieldsAfter,offset);
 NSMutableArray*variantWords=[NSMutableArray array],*afterWords=[NSMutableArray array];for(unsigned i=0;i<32;i++){[variantWords addObject:@(u32(fields,4*i))];[afterWords addObject:@(u32(fieldsAfter,4*i))];}
 emit(@{@"status":complete&&uncommitted?@"CAPTURED":@"CAPTURE_INCOMPLETE",@"mode":mode,@"function":name,@"device":device.name,@"registry_id":@(device.registryID),@"driver_SHA256":driverHash,
  @"library_SHA256":sha(libraryData),@"certificate_SHA256":sha(certificateData),@"import":proof?:@{},@"pipeline_class":NSStringFromClass(object_getClass(pipeline)),@"encoder_class":NSStringFromClass(object_getClass(encoder)),
  @"variant_words_0_128":variantWords,@"variant_SHA256":sha(fields),@"variant_after_words_0_128":afterWords,@"variant_after_SHA256":sha(fieldsAfter),@"variant_contract_stable_across_encoding":@(variantStable),@"decoded_allocation_word40":@(u32(fields,40)),@"decoded_allocation_after_word40":@(u32(fieldsAfter,40)),@"code_GPU_address":@(u64(fields,16)),@"code_after_GPU_address":@(u64(fieldsAfter,16)),@"native_code_bytes":@(u64(fields,24)),@"native_registers":@(u32(fields,48)),@"native_spill_bytes":@(u32(fields,56)),
  @"input_GPU_address":@(input.gpuAddress),@"output_GPU_address":@(output.gpuAddress),@"parameters_GPU_address":@(parameters.gpuAddress),@"buffer_offsets":@[@128,@128,@0],@"parameters_bytes":@(parameters.length),@"groups":@(groups),@"local":@(local),@"count":@(count),
  @"records":records,@"runs":@[],@"encoded_dispatch_calls":@3,@"created_command_buffers":@1,@"committed":@NO,@"command_status":@(command.status),@"user_GPU_command_buffers":@0,@"GPU_shader_execution_observed":@NO,
  @"native_memory_written_by_probe":@NO,@"packet_replay":@NO,@"system_modified":@NO,@"performance_benchmark":@NO});
 return complete&&uncommitted?0:3;
}}
