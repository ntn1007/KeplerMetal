// Inspect only objects owned by this process and commands never committed.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstdint>
#include <cstring>
#include <cstdio>

static NSData *readMemory(uintptr_t address,size_t length) {
 if(!address||!length||length>262144)return nil;
 NSMutableData*d=[NSMutableData dataWithLength:length];mach_vm_size_t actual=0;
 kern_return_t s=mach_vm_read_overwrite(mach_task_self(),address,length,(mach_vm_address_t)d.mutableBytes,&actual);
 return s==KERN_SUCCESS&&actual==length?d:nil;
}
static NSString *hash(NSData*d) {
 if(!d)return @"";unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);
 NSMutableString*r=[NSMutableString new];for(unsigned char b:digest)[r appendFormat:@"%02x",b];return r;
}
static uint64_t word(NSData*d,size_t offset) {
 uint64_t n=0;if(offset+8<=d.length)memcpy(&n,(const char*)d.bytes+offset,8);return n;
}
static NSDictionary *saveMemory(uintptr_t address,size_t length,NSString*dir,NSString*label) {
 NSData*d=readMemory(address,length);NSString*p=[dir stringByAppendingPathComponent:[label stringByAppendingString:@".bin"]];
 bool saved=d&&[d writeToFile:p atomically:YES];
 return @{@"address":@(address),@"bytes_requested":@(length),@"bytes_read":@(d.length),@"saved":@(saved),@"path":p,@"SHA256":hash(d)};
}
static NSDictionary *layout(id object,NSString*directory,NSString*name) {
 Class c=object_getClass(object);size_t size=class_getInstanceSize(c);uintptr_t address=(uintptr_t)(__bridge const void*)object;
 NSMutableArray*ivars=[NSMutableArray new];
 for(Class owner=c;owner&&owner!=[NSObject class];owner=class_getSuperclass(owner)) {
  unsigned count=0;Ivar*vars=class_copyIvarList(owner,&count);
  for(unsigned i=0;i<count;i++) {
   Ivar v=vars[i];const char*t=ivar_getTypeEncoding(v);ptrdiff_t offset=ivar_getOffset(v);
   NSMutableDictionary*r=[@{@"name":@(ivar_getName(v)),@"owner":NSStringFromClass(owner),@"type":@(t),@"offset":@(offset)}mutableCopy];
   if(offset>=0&&(size_t)offset+8<=size) {
    uintptr_t p=0;memcpy(&p,(const char*)(__bridge const void*)object+offset,8);r[@"raw_first_word"]=@(p);
    if(t[0]=='@'&&p) {
     id value=object_getIvar(object,v);r[@"object_class"]=NSStringFromClass(object_getClass(value));
     r[@"object_address"]=@((uintptr_t)(__bridge const void*)value);
    }
    if(t[0]=='^'&&p&&[@[@"_cmdbuf",@"_storage",@"_queue",@"_computePipeline",@"m_compute"] containsObject:r[@"name"]]) {
     NSString*label=[NSString stringWithFormat:@"%@-%@-prefix",name,r[@"name"]];
     r[@"prefix"]=saveMemory(p,[r[@"name"] isEqual:@"m_compute"]?8192:1024,directory,label);
    }
   }[ivars addObject:r];
  }free(vars);
 }
 return @{@"class":NSStringFromClass(c),@"address":@(address),@"instance_bytes":@(size),@"ivars":ivars,
          @"object_snapshot":saveMemory(address,size,directory,[name stringByAppendingString:@"-object"])};
}

struct Cursor {uintptr_t implementation,push,cursor,end,state,device;};
static Cursor cursor(id<MTLComputeCommandEncoder>e) {
 Cursor c={};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");
 if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;
 memcpy(&c.implementation,(const char*)(__bridge const void*)e+120,8);
 NSData*impl=readMemory(c.implementation,64);c.push=word(impl,32);NSData*push=readMemory(c.push,144);
 c.cursor=word(push,0);c.end=word(push,136);c.state=word(push,40);c.device=word(readMemory(c.state,16),8);return c;
}
static NSDictionary *cursorInfo(Cursor c) {return @{@"implementation":@(c.implementation),@"push":@(c.push),@"cursor":@(c.cursor),@"end":@(c.end),@"state":@(c.state),@"device":@(c.device)};}
static NSDictionary *knownQueueObjects(id<MTLCommandQueue>q,NSString*dir) {
 Ivar v=class_getInstanceVariable(object_getClass(q),"_queue");if(!v||ivar_getOffset(v)!=680)return @{};
 uintptr_t cpp=0;memcpy(&cpp,(const char*)(__bridge const void*)q+680,8);NSData*data=readMemory(cpp,64);NSMutableArray*objects=[NSMutableArray new];
 // Runtime type: uint32 followed by InternalTextures five objects, then one object.
 for(unsigned offset=8;offset<=48;offset+=8) {
  uintptr_t address=word(data,offset);if(!address)continue;
  id object=(__bridge id)(void*)address;NSMutableDictionary*r=[@{@"cpp_offset":@(offset),@"address":@(address),@"class":NSStringFromClass(object_getClass(object))}mutableCopy];
  if([object isKindOfClass:objc_getClass("NVMTLBuffer")]) {
   id<MTLBuffer>b=object;r[@"GPU_address"]=@(b.gpuAddress);r[@"length"]=@(b.length);r[@"storage_mode"]=@(b.storageMode);
   r[@"layout"]=layout(object,dir,[NSString stringWithFormat:@"queue-owned-%u",offset]);
  }[objects addObject:r];
 }
 return @{@"cpp_address":@(cpp),@"runtime_type":@(ivar_getTypeEncoding(v)),@"fields":objects};
}

int main(int argc,char**argv) {@autoreleasepool {
 if(argc!=3)return 1;NSString*dir=@(argv[2]);id<MTLDevice>d=nil;
 for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}
 if(!d)return 2;
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![hash(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 3;
 NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
 id<MTLFunction>f=[library newFunctionWithName:@"consume_grid"];id<MTLComputePipelineState>pipeline=f?[d newComputePipelineStateWithFunction:f error:&error]:nil;
 if(!pipeline)return 4;
 uint32_t params[4]={0x1234,3,32,640};id<MTLBuffer>output=[d newBufferWithLength:10496 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>counter=[d newBufferWithLength:512 options:MTLResourceStorageModePrivate],args=[d newBufferWithLength:512 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>parameters=[d newBufferWithBytes:params length:sizeof params options:MTLResourceStorageModeShared];
 id<MTLCommandQueue>queue=[d newCommandQueue];if(!output||!counter||!args||!parameters||!queue)return 5;
 NSMutableDictionary*objects=[NSMutableDictionary new];
 for(NSString*key in @[@"output",@"counter",@"args",@"parameters"]){
  id<MTLBuffer>b=[@{@"output":output,@"counter":counter,@"args":args,@"parameters":parameters}objectForKey:key];
  NSMutableDictionary*r=[layout(b,dir,key)mutableCopy];r[@"GPU_address"]=@(b.gpuAddress);r[@"length"]=@(b.length);r[@"storage_mode"]=@(b.storageMode);objects[key]=r;
 }
 objects[@"queue"]=layout(queue,dir,@"queue");objects[@"pipeline"]=layout(pipeline,dir,@"pipeline");objects[@"device"]=layout(d,dir,@"device");
 NSDictionary*queueObjects=knownQueueObjects(queue,dir);
 NSMutableArray*buffers=[NSMutableArray new],*records=[NSMutableArray new];
 for(unsigned index=0;index<3;index++) {
  id<MTLCommandBuffer>cb=[queue commandBuffer];[buffers addObject:cb];
  id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
  [e setComputePipelineState:pipeline];[e setBuffer:output offset:64 atIndex:0];[e setBuffer:counter offset:64 atIndex:1];[e setBuffer:parameters offset:0 atIndex:2];
  NSDictionary*before=layout(cb,dir,[NSString stringWithFormat:@"cb-%u-before",index]);
  Cursor start=cursor(e);
  if(index==1)[e dispatchThreadgroupsWithIndirectBuffer:args indirectBufferOffset:64 threadsPerThreadgroup:MTLSizeMake(32,1,1)];
  else [e dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
  Cursor finish=cursor(e);bool comparable=start.push&&start.push==finish.push&&start.cursor&&finish.cursor>=start.cursor&&finish.cursor<=start.end&&finish.cursor-start.cursor<=65536;
  NSString*mode=index==1?@"indirect":@"direct";NSString*streamLabel=[NSString stringWithFormat:@"%@-%u.commands",mode,index];
  NSDictionary*stream=comparable?saveMemory(start.cursor,finish.cursor-start.cursor,dir,streamLabel):@{};
  NSDictionary*deviceSnapshot=saveMemory(finish.device,0x1f100,dir,[NSString stringWithFormat:@"device-cpp-%u",index]);
  NSDictionary*pushSnapshot=saveMemory(finish.push,256,dir,[NSString stringWithFormat:@"push-%u",index]);
  NSDictionary*stateSnapshot=saveMemory(finish.state,256,dir,[NSString stringWithFormat:@"state-%u",index]);
  NSDictionary*encoded=layout(cb,dir,[NSString stringWithFormat:@"cb-%u-encoded",index]);
  NSDictionary*encoder=layout(e,dir,[NSString stringWithFormat:@"encoder-%u",index]);[e endEncoding];
  NSDictionary*ended=layout(cb,dir,[NSString stringWithFormat:@"cb-%u-ended",index]);
  [records addObject:@{@"index":@(index),@"step":@(index),@"mode":mode,@"before":before,@"encoded":encoded,@"ended":ended,@"encoder":encoder,@"status":@(cb.status),@"retained_references":@(cb.retainedReferences),
                     @"cursor_before":cursorInfo(start),@"cursor_after":cursorInfo(finish),@"range_comparable":@(comparable),@"stream":stream,@"device_cpp":deviceSnapshot,@"push":pushSnapshot,@"state":stateSnapshot}];
 }
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":hash(driver),@"objects":objects,@"queue_internal_objects":queueObjects,@"records":records,
                  @"GPU_dispatch":@NO,@"committed":@NO,@"private_calls":@NO,@"private_memory_writes":@NO,
                  @"scope":@"Own-process live objects, ivar types and bounded prefixes only. Three encoded command buffers retained together; none committed. No traversal after release, replay or ICB implementation."};
 NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
