#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(auto c:h)[s appendFormat:@"%02x",c];return s;}
static id<MTLLibrary>load(id<MTLDevice>d,NSData*x,NSError**e){dispatch_data_t b=dispatch_data_create(x.bytes,x.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)x.length;});return[d newLibraryWithData:b error:e];}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;Class original=object_getClass(d);KPCPUICBScope*scope=nil;id<MTLBuffer>root=nil;
 NSMutableDictionary*r=[@{@"mode":mode,@"stage":@"function",@"GPU_dispatch":@NO,@"committed":@NO}mutableCopy];
 @try{
  NSError*e=nil;NSData*data=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"producer.metallib"]];id<MTLLibrary>library=load(d,data,&e);id<MTLFunction>f=[library newFunctionWithName:@"encode_dataflow_basic"];if(!f)return 3;
  MTLArgument*arg=nil;id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0 reflection:&arg];r[@"encoder_length"]=@(ae.encodedLength);r[@"encoder_alignment"]=@(ae.alignment);r[@"encoder_class"]=NSStringFromClass(object_getClass(ae));r[@"reflection_created"]=@(arg!=nil);
  if(arg){NSMutableArray*members=[NSMutableArray new];for(MTLStructMember*m in arg.bufferStructType.members)[members addObject:@{@"name":m.name,@"offset":@(m.offset),@"argument_index":@(m.argumentIndex),@"data_type":@(m.dataType)}];r[@"reflection"]=@{@"name":arg.name,@"index":@(arg.index),@"argument_type":@(arg.type),@"buffer_data_type":@(arg.bufferDataType),@"buffer_data_size":@(arg.bufferDataSize),@"buffer_alignment":@(arg.bufferAlignment),@"members":members};}
  if([mode isEqual:@"reflection"]){r[@"status"]=@"OBSERVED_CPU_ONLY";}
  else{
   if(ae.encodedLength!=48||ae.alignment!=8)return 4;root=[d newBufferWithLength:176 options:MTLResourceStorageModeShared];memset(root.contents,0xa5,root.length);[ae setArgumentBuffer:root offset:64];
   if([mode isEqual:@"icb"]){
    NSData*b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.json"]];id<MTLCommandQueue>q=[d newCommandQueue];scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:b expectedSHA256:sha(b)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&e];if(!scope)return 5;
    MTLIndirectCommandBufferDescriptor*p=[MTLIndirectCommandBufferDescriptor new];p.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;p.maxKernelBufferBindCount=4;p.inheritBuffers=NO;p.inheritPipelineState=NO;id<MTLIndirectCommandBuffer>ib=[d newIndirectCommandBufferWithDescriptor:p maxCommandCount:4 options:MTLResourceStorageModeShared];r[@"ICB_class"]=NSStringFromClass(object_getClass(ib));r[@"stage"]=@"native_setIndirectCommandBuffer";r[@"setter_available"]=@([ae respondsToSelector:@selector(setIndirectCommandBuffer:atIndex:)]);[ae setIndirectCommandBuffer:ib atIndex:0];
   }else if([mode isEqual:@"pipeline"]){
    NSData*b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]];id<MTLLibrary>l=load(d,b,&e);MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];pd.computeFunction=[l newFunctionWithName:@"dependency_seed"];pd.supportIndirectCommandBuffers=YES;r[@"stage"]=@"native_indirect_pipeline";id<MTLComputePipelineState>p=[d newComputePipelineStateWithDescriptor:pd options:MTLPipelineOptionNone reflection:nil error:&e];r[@"pipeline_created"]=@(p!=nil);r[@"pipeline_error"]=e.description?:@"";
    if(p){r[@"stage"]=@"native_setComputePipelineState";r[@"setter_available"]=@([ae respondsToSelector:@selector(setComputePipelineState:atIndex:)]);[ae setComputePipelineState:p atIndex:1];}
   }else if([mode isEqual:@"buffers"]){id<MTLBuffer>b=[d newBufferWithLength:32 options:MTLResourceStorageModeShared];r[@"stage"]=@"native_setBuffers";for(unsigned i=2;i<6;i++)[ae setBuffer:b offset:0 atIndex:i];}
   else return 1;
   r[@"status"]=@"OBSERVED_CPU_ONLY";
  }
 }@catch(NSException*x){r[@"status"]=@"EXCEPTION";r[@"exception_name"]=x.name;r[@"exception_reason"]=x.reason?:@"";}
 @finally{if(scope)[scope restore];r[@"device_class_restored"]=@(object_getClass(d)==original);if(root){[[NSData dataWithBytes:root.contents length:root.length]writeToFile:[out stringByAppendingPathComponent:@"root.bin"]atomically:YES];r[@"root_file"]=@"root.bin";}}
 NSDictionary*v=@{@"device":d.name,@"registry_id":@(d.registryID),@"mode":mode,@"runs":@[r],@"GPU_execution":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
