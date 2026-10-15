// Compile and inspect multiple native pipelines, capturing only uncommitted
// own-process command words. No GPU submission or command-memory modification.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
static NSData*readMemory(uintptr_t p,size_t bytes){if(!p||!bytes||bytes>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:bytes];mach_vm_size_t n=0;return mach_vm_read_overwrite(mach_task_self(),p,bytes,(mach_vm_address_t)d.mutableBytes,&n)==KERN_SUCCESS&&n==bytes?d:nil;}
static uint64_t u64(NSData*d,size_t o){uint64_t v=0;if(o+8<=d.length)memcpy(&v,(const char*)d.bytes+o,8);return v;}
static uint32_t u32(NSData*d,size_t o){uint32_t v=0;if(o+4<=d.length)memcpy(&v,(const char*)d.bytes+o,4);return v;}
static NSString*sha(NSData*d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458){d=x;break;}if(!d)return 2;
 NSError*error=nil;NSData*librarySnapshot=[NSData dataWithContentsOfFile:@(argv[1])];dispatch_data_t payload=dispatch_data_create(librarySnapshot.bytes,librarySnapshot.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)librarySnapshot.length;});id<MTLLibrary>lib=[d newLibraryWithData:payload error:&error];if(!lib)return 3;
 id<MTLCommandQueue>q=[d newCommandQueue];NSMutableArray*rows=[NSMutableArray new],*held=[NSMutableArray new];
 for(NSString*name in @[@"grid_coordinates"]){
  id<MTLFunction>fn=[lib newFunctionWithName:name];MTLComputePipelineReflection*reflection=nil;
  id<MTLComputePipelineState>pso=[d newComputePipelineStateWithFunction:fn options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:&error];
  if(!pso){fprintf(stderr,"pipeline %s: %s\n",name.UTF8String,error.localizedDescription.UTF8String);return 4;}
  id<MTLBuffer>output=[d newBufferWithLength:131584 options:MTLResourceStorageModePrivate],a=[d newBufferWithLength:131584 options:MTLResourceStorageModePrivate],b=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate],params=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];
  if(!output||!a||!b||!params)return 5;uint32_t count=1920,scale=0x1234;memcpy((char*)params.contents+256,&count,4);memcpy((char*)params.contents+260,&scale,4);
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>encoder=[cb computeCommandEncoder];[encoder setComputePipelineState:pso];[encoder setBuffer:output offset:128 atIndex:0];[encoder setBuffer:a offset:64 atIndex:1];[encoder setBuffer:b offset:64 atIndex:2];[encoder setBuffer:params offset:256 atIndex:3];
  Ivar iv=class_getInstanceVariable(object_getClass(encoder),"m_compute");if(!iv||ivar_getOffset(iv)!=120||class_getInstanceSize(object_getClass(encoder))!=128)return 6;
  uintptr_t impl=0;memcpy(&impl,(const char*)(__bridge const void*)encoder+120,8);uintptr_t push=u64(readMemory(impl,64),32);NSData*before=readMemory(push,144);uintptr_t begin=u64(before,0);
  [encoder dispatchThreadgroups:MTLSizeMake(3,5,2) threadsPerThreadgroup:MTLSizeMake(8,4,2)];NSData*after=readMemory(push,144);uintptr_t end=u64(after,0);NSData*commands=end>=begin&&end<=u64(before,136)?readMemory(begin,end-begin):nil;if(!commands.length||commands.length>4096){[encoder endEncoding];return 7;}
  NSString*file=[@(argv[2])stringByAppendingPathComponent:[name stringByAppendingString:@".commands.bin"]];[commands writeToFile:file atomically:YES];
  NSMutableArray*arguments=[NSMutableArray new];for(MTLArgument*a in reflection.arguments){NSMutableDictionary*r=[@{@"name":a.name?:@"",@"index":@(a.index),@"type":@(a.type),@"access":@(a.access),@"active":@(a.active)}mutableCopy];if(a.type==MTLArgumentTypeBuffer){r[@"alignment"]=@(a.bufferAlignment);r[@"data_size"]=@(a.bufferDataSize);r[@"data_type"]=@(a.bufferDataType);}else if(a.type==MTLArgumentTypeThreadgroupMemory){r[@"alignment"]=@(a.threadgroupMemoryAlignment);r[@"data_size"]=@(a.threadgroupMemoryDataSize);}[arguments addObject:r];}
  BOOL hasStatic=[pso respondsToSelector:@selector(staticThreadgroupMemoryLength)];
  [rows addObject:@{@"function":fn.name,@"command_file":file,@"command_SHA256":sha(commands),@"command_bytes":@(commands.length),@"pipeline_class":NSStringFromClass(object_getClass(pso)),@"reflection_available":@(reflection!=nil),@"arguments":arguments,@"static_memory_selector":@(hasStatic),@"static_threadgroup_bytes":@(hasStatic?pso.staticThreadgroupMemoryLength:0),@"max_threads":@(pso.maxTotalThreadsPerThreadgroup),@"execution_width":@(pso.threadExecutionWidth),@"GPU_dispatch":@NO,@"committed":@NO}];
  [encoder endEncoding];[held addObject:@[cb,pso,output,a,b,params]];
 }
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"library_SHA256":sha([NSData dataWithContentsOfFile:@(argv[1])]),@"records":rows,@"GPU_dispatch":@NO,@"committed":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
