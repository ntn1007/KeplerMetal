// SPDX-License-Identifier: MIT
// Public Metal factories only. No experimental transport or user dispatch.
#import <Metal/Metal.h>
#include <cstdio>
#import <objc/runtime.h>
#include <dlfcn.h>
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=4)return 1;id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d)return 2;
 NSError*error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:[@(argv[1])stringByAppendingPathComponent:@"limits.metallib"]]error:&error];if(!lib){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 NSMutableArray*rows=[NSMutableArray new];
 if([@(argv[3])isEqual:@"encode"]){
  id<MTLFunction>f=[lib newFunctionWithName:@"limit_32"];MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.maxTotalThreadsPerThreadgroup=32;
  id<MTLComputePipelineState>state=[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOptionNone reflection:nil error:&error];if(!state)return 5;
  id<MTLCommandQueue>q=[d newCommandQueue];id<MTLBuffer>b=[d newBufferWithLength:8192 options:MTLResourceStorageModeShared];
  for(NSNumber*n in @[@32,@33,@1024]){id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];NSString*exception=nil;
   @try{[e setComputePipelineState:state];[e setBuffer:b offset:0 atIndex:0];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(n.unsignedIntegerValue,1,1)];}@catch(NSException*x){exception=x.reason?:x.name;}[e endEncoding];
   [rows addObject:@{@"function":@"limit_32",@"requested":@32,@"reported":@(state.maxTotalThreadsPerThreadgroup),@"local_threads":n,@"encoded":@(!exception),@"exception":exception?:@"",@"committed":@NO}];
  }
 }else{
 for(NSString*name in @[@"limit_auto",@"limit_32",@"limit_64",@"limit_128",@"limit_256",@"limit_1024"]){
  id<MTLFunction>f=[lib newFunctionWithName:name];if(!f)return 4;
  for(unsigned pass=0;pass<2;pass++)for(NSNumber*n in @[@0,@32,@64,@128,@256,@1024]){
   MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.maxTotalThreadsPerThreadgroup=n.unsignedIntegerValue;p.label=[NSString stringWithFormat:@"%@-%@-%u",name,n,pass];
   NSError*err=nil;id<MTLComputePipelineState>state=nil;NSString*exception=nil;
   @try{state=[d newComputePipelineStateWithDescriptor:p options:MTLPipelineOptionNone reflection:nil error:&err];}@catch(NSException*x){exception=x.reason?:x.name;}
   [rows addObject:@{@"function":name,@"pass":@(pass),@"requested":n,@"pipeline":@(state!=nil),@"reported":@(state?state.maxTotalThreadsPerThreadgroup:0),@"execution_width":@(state?state.threadExecutionWidth:0),@"label_preserved":@(!state||[state.label isEqual:p.label]),@"error":err.description?:@"",@"exception":exception?:@""}];
  }
 }
 }
 NSMutableArray*methods=[NSMutableArray new];id<MTLFunction>diagnostic=[lib newFunctionWithName:@"limit_auto"];id<MTLComputePipelineState>pso=[d newComputePipelineStateWithFunction:diagnostic error:&error];
 if(pso){Class c=object_getClass(pso);for(Class k=c;k;k=class_getSuperclass(k)){unsigned count=0;Ivar*vars=class_copyIvarList(k,&count);NSMutableArray*ivars=[NSMutableArray new];for(unsigned i=0;i<count;i++){const char*n=ivar_getName(vars[i]);[ivars addObject:@{@"name":@(n?:""),@"offset":@(ivar_getOffset(vars[i])),@"type":@(ivar_getTypeEncoding(vars[i])?:"")}];}free(vars);[methods addObject:@{@"class":NSStringFromClass(k),@"instance_bytes":@(class_getInstanceSize(k)),@"ivars":ivars}];}
  Method m=class_getInstanceMethod(c,@selector(maxTotalThreadsPerThreadgroup));IMP fn=method_getImplementation(m);Dl_info image={};dladdr((void*)fn,&image);NSData*bytes=[NSData dataWithBytes:(void*)fn length:32];NSMutableString*hex=[NSMutableString new];for(NSUInteger i=0;i<bytes.length;i++)[hex appendFormat:@"%02x",((const unsigned char*)bytes.bytes)[i]];
  [methods addObject:@{@"selector":@"maxTotalThreadsPerThreadgroup",@"image":@(image.dli_fname?:""),@"image_offset":@((uintptr_t)fn-(uintptr_t)image.dli_fbase),@"first32_bytes_hex":hex}];
 }
 NSDictionary*r=@{@"runtime_observation":methods,@"device":d.name,@"registry_id":@(d.registryID),@"runs":rows,@"user_GPU_command_buffers":@0,@"experimental_transport":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
