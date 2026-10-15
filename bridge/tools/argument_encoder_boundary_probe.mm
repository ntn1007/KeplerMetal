#if KP_ARGUMENT_NATIVE
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#else
#import "KeplerCPUICB.h"
#endif
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(auto c:h)[s appendFormat:@"%02x",c];return s;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 if(![@[@"buffer",@"pipeline",@"icb",@"scope_icb",@"scope_identity"]containsObject:mode])return 1;
 id<MTLDevice>d=nil;
#if KP_ARGUMENT_NATIVE
 d=MTLCreateSystemDefaultDevice();if(![d.name isEqual:@"Apple M1 Max"]||[mode hasPrefix:@"scope_"])return 2;
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
 KPCPUICBScope*scope=nil;
#endif
 if(!d)return 2;Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 NSMutableDictionary*r=[@{@"mode":mode,@"stage":@"start",@"GPU_dispatch":@NO,@"command_buffers_submitted":@NO,@"root_files":@{},@"native_encoder_used":@NO}mutableCopy];
 @try{
  id<MTLIndirectCommandBuffer>icb=nil;
#if !KP_ARGUMENT_NATIVE
  if([mode hasPrefix:@"scope_"]){
   r[@"stage"]=@"scope_install";NSData*lib=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.json"]];
   if(![sha(lib)isEqual:@"7b415aef3f5feb660698dfa0816b11a62d35da9ccc71cd83be170fabd904349f"])return 3;
   scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:lib expectedSHA256:sha(lib)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error];
   if(!scope)return 3;
  }
#endif
  if([mode isEqual:@"scope_identity"]){
   MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
   r[@"stage"]=@"create_scoped_ICB";icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:4 options:MTLResourceStorageModeShared];r[@"ICB_class"]=NSStringFromClass(object_getClass(icb));
   r[@"stage"]=@"read_scoped_gpuResourceID";MTLResourceID identity=icb.gpuResourceID;r[@"resource_identity"]=@(identity._impl);r[@"status"]=@"ACCEPTED_CPU_ONLY";
  }else{
   MTLArgumentDescriptor*a=[MTLArgumentDescriptor argumentDescriptor];a.index=0;a.arrayLength=1;a.access=MTLArgumentAccessReadOnly;
   a.dataType=[mode isEqual:@"buffer"]?MTLDataTypePointer:[mode isEqual:@"pipeline"]?MTLDataTypeComputePipeline:MTLDataTypeIndirectCommandBuffer;r[@"argument_data_type"]=@(a.dataType);
   r[@"stage"]=@"newArgumentEncoderWithArguments";id<MTLArgumentEncoder>e=[d newArgumentEncoderWithArguments:@[a]];
   if(!e){r[@"status"]=@"NIL_ENCODER";}
   else{
    r[@"native_encoder_used"]=@YES;r[@"encoder_class"]=NSStringFromClass(object_getClass(e));r[@"encoded_length"]=@(e.encodedLength);r[@"alignment"]=@(e.alignment);
    if(!e.encodedLength||e.encodedLength>65536||!e.alignment||e.alignment>4096){r[@"status"]=@"UNSUPPORTED_ENCODER_LAYOUT";r[@"local_layout_guard"]=@YES;}
    else{
    NSUInteger offset=((64+e.alignment-1)/e.alignment)*e.alignment,total=offset+e.encodedLength+64;id<MTLBuffer>root=[d newBufferWithLength:total options:MTLResourceStorageModeShared];memset(root.contents,0xa5,total);
    r[@"root_offset"]=@(offset);r[@"stage"]=@"setArgumentBuffer";[e setArgumentBuffer:root offset:offset];
    if([mode isEqual:@"buffer"]){
     id<MTLBuffer>b=[d newBufferWithLength:512 options:MTLResourceStorageModeShared];r[@"stage"]=@"setBuffer";[e setBuffer:b offset:32 atIndex:0];
    }else if([mode isEqual:@"pipeline"]){
     r[@"binding_selector_available"]=@([e respondsToSelector:@selector(setComputePipelineState:atIndex:)]);
     if(![e respondsToSelector:@selector(setComputePipelineState:atIndex:)]){r[@"status"]=@"MISSING_BINDING_SELECTOR";}
     else{r[@"stage"]=@"native_pipeline";id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"consumer.metallib"]]error:&error];id<MTLComputePipelineState>p=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"dependency_seed"]error:&error];if(!p)return 5;r[@"stage"]=@"setComputePipelineState";[e setComputePipelineState:p atIndex:0];}
    }else{
     r[@"binding_selector_available"]=@([e respondsToSelector:@selector(setIndirectCommandBuffer:atIndex:)]);
     if(![e respondsToSelector:@selector(setIndirectCommandBuffer:atIndex:)]){r[@"status"]=@"MISSING_BINDING_SELECTOR";}
     else{MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;r[@"stage"]=@"newIndirectCommandBufferWithDescriptor";icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:4 options:MTLResourceStorageModeShared];r[@"ICB_class"]=NSStringFromClass(object_getClass(icb));r[@"stage"]=@"setIndirectCommandBuffer";[e setIndirectCommandBuffer:icb atIndex:0];}
    }
    if(!r[@"status"])r[@"status"]=@"ACCEPTED_CPU_ONLY";
    [[NSData dataWithBytes:root.contents length:root.length]writeToFile:[out stringByAppendingPathComponent:@"encoded-root.bin"]atomically:YES];r[@"root_files"]=@{@"encoded-root":@"encoded-root.bin"};
    }
   }
  }
 }@catch(NSException*x){r[@"status"]=@"EXCEPTION";r[@"exception_name"]=x.name;r[@"exception_reason"]=x.reason?:@"";}
 @finally{
#if !KP_ARGUMENT_NATIVE
  if(scope){[scope restore];r[@"scope_events"]=scope.events;}
#endif
  r[@"device_class_restored"]=@(object_getClass(d)==original);}
 NSDictionary*result=@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"runs":@[r],@"system_modified":@NO,@"performance_benchmark":@NO,@"GPU_execution":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
