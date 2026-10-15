// SPDX-License-Identifier: MIT
// Observe public native queue/buffer/compute factories; never commit a buffer.
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstdio>
static NSDictionary*identity(id x){return x?@{@"class":NSStringFromClass(object_getClass(x)),@"instance_bytes":@(class_getInstanceSize(object_getClass(x)))}:@{};}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;id<MTLDevice>d=MTLCreateSystemDefaultDevice();id<MTLCommandQueue>q=[d newCommandQueue];if(!q)return 2;NSMutableArray*runs=[NSMutableArray new];
 for(unsigned factory=0;factory<4;factory++)for(unsigned kind=0;kind<5;kind++){@autoreleasepool{
  id<MTLCommandBuffer>cb=nil;id<MTLComputeCommandEncoder>e=nil;NSString*exception=nil;NSString*stage=@"buffer";
  @try{
   if(factory==0)cb=[q commandBuffer];else if(factory==1)cb=[q commandBufferWithUnretainedReferences];else{MTLCommandBufferDescriptor*p=[MTLCommandBufferDescriptor new];p.retainedReferences=factory==2;cb=[q commandBufferWithDescriptor:p];}
   stage=@"encoder";
   if(kind==0)e=[cb computeCommandEncoder];else if(kind<3)e=[cb computeCommandEncoderWithDispatchType:kind==1?MTLDispatchTypeSerial:MTLDispatchTypeConcurrent];else{MTLComputePassDescriptor*p=[MTLComputePassDescriptor computePassDescriptor];p.dispatchType=kind==3?MTLDispatchTypeSerial:MTLDispatchTypeConcurrent;e=[cb computeCommandEncoderWithDescriptor:p];}
  }@catch(NSException*x){exception=x.reason?:x.name;}
  NSDictionary*ci=identity(cb),*ei=identity(e);if(e)[e endEncoding];
  [runs addObject:@{@"buffer_factory":@(factory),@"encoder_factory":@(kind),@"buffer":ci,@"encoder":ei,@"created":@(e!=nil),@"retained_references":@(cb?cb.retainedReferences:NO),@"stage":stage,@"exception":exception?:@"",@"committed":@NO}];
 }}
 NSMutableArray*selectors=[NSMutableArray new];for(id x in @[q,[q commandBuffer]])for(NSString*n in @[@"commandBuffer",@"commandBufferWithUnretainedReferences",@"commandBufferWithDescriptor:",@"computeCommandEncoder",@"computeCommandEncoderWithDispatchType:",@"computeCommandEncoderWithDescriptor:"]){SEL s=NSSelectorFromString(n);Method m=class_getInstanceMethod(object_getClass(x),s);if(m)[selectors addObject:@{@"class":NSStringFromClass(object_getClass(x)),@"selector":n,@"encoding":@(method_getTypeEncoding(m))}];}
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"queue":identity(q),@"selectors":selectors,@"runs":runs,@"user_GPU_command_buffers":@0,@"experimental_runtime":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
