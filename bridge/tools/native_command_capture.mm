// Capture bytes emitted by public dispatch APIs into our uncommitted encoder.
// Private memory is read through mach_vm_read; no cursor, resource or packet is modified.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstdint>
#include <cstring>
#include <cstdio>
static NSData *readMemory(uintptr_t address,size_t size){if(!address||!size||size>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:size];mach_vm_size_t n=0;kern_return_t s=mach_vm_read_overwrite(mach_task_self(),address,size,(mach_vm_address_t)d.mutableBytes,&n);return s==KERN_SUCCESS&&n==size?d:nil;}
static uint64_t word(NSData*d,size_t offset){uint64_t v=0;if(offset+8<=d.length)memcpy(&v,(const uint8_t*)d.bytes+offset,8);return v;}
static NSString *hash(NSData*d){if(!d)return @"";unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*r=[NSMutableString new];for(unsigned char b:digest)[r appendFormat:@"%02x",b];return r;}
struct Cursor {uintptr_t implementation,push,cursor,end;};
static Cursor state(id<MTLComputeCommandEncoder>e,NSString*directory,NSString*label){
 Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");Cursor r={};
 if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128||ivar_getTypeEncoding(v)[0]!='^')return r;
 memcpy(&r.implementation,(const char*)(__bridge const void*)e+120,8);NSData*impl=readMemory(r.implementation,64);r.push=word(impl,32);NSData*push=readMemory(r.push,144);r.cursor=word(push,0);r.end=word(push,136);
 if(impl)[impl writeToFile:[directory stringByAppendingPathComponent:[label stringByAppendingString:@".impl.bin"]] atomically:YES];
 if(push)[push writeToFile:[directory stringByAppendingPathComponent:[label stringByAppendingString:@".push.bin"]] atomically:YES];return r;
}
static NSDictionary *cursorInfo(Cursor c){return @{@"implementation":@(c.implementation),@"push":@(c.push),@"cursor":@(c.cursor),@"end":@(c.end)};}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;NSString*dir=@(argv[2]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];if(![hash(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 3;
 NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];id<MTLFunction>f=[library newFunctionWithName:@"consume_grid"];id<MTLComputePipelineState>pipe=f?[d newComputePipelineStateWithFunction:f error:&error]:nil;if(!pipe)return 4;
 uint32_t params[4]={0x1234,3,32,640};id<MTLBuffer>output=[d newBufferWithLength:640*16+128 options:MTLResourceStorageModePrivate],counter=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate],args=[d newBufferWithLength:140 options:MTLResourceStorageModePrivate],parameters=[d newBufferWithBytes:params length:sizeof params options:MTLResourceStorageModeShared];if(!output||!counter||!args||!parameters)return 5;
 id<MTLCommandQueue>q=[d newCommandQueue];NSMutableArray*records=[NSMutableArray new];
 for(NSString*mode in @[@"direct",@"indirect"]){id<MTLCommandBuffer>c=[q commandBuffer];id<MTLComputeCommandEncoder>e=[c computeCommandEncoder];[e setComputePipelineState:pipe];[e setBuffer:output offset:64 atIndex:0];[e setBuffer:counter offset:64 atIndex:1];[e setBuffer:parameters offset:0 atIndex:2];
  for(unsigned step=0;step<3;step++){
   NSString*label=[NSString stringWithFormat:@"%@-%u",mode,step];Cursor before=state(e,dir,[label stringByAppendingString:@"-before"]);
   if([mode isEqual:@"direct"])[e dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
   else [e dispatchThreadgroupsWithIndirectBuffer:args indirectBufferOffset:64 threadsPerThreadgroup:MTLSizeMake(32,1,1)];
   Cursor after=state(e,dir,[label stringByAppendingString:@"-after"]);bool comparable=before.push&&before.push==after.push&&before.cursor&&after.cursor>=before.cursor&&after.cursor<=before.end&&after.cursor-before.cursor<=65536;
   NSData*delta=comparable&&after.cursor>before.cursor?readMemory(before.cursor,after.cursor-before.cursor):nil;NSString*path=[dir stringByAppendingPathComponent:[label stringByAppendingString:@".commands.bin"]];BOOL saved=delta&&[delta writeToFile:path atomically:YES];
   [records addObject:@{@"mode":mode,@"step":@(step),@"before":cursorInfo(before),@"after":cursorInfo(after),@"range_comparable":@(comparable),@"bytes":@(delta.length),@"file":path,@"saved":@(saved),@"SHA256":hash(delta),@"GPU_dispatch":@NO}];
  }[e endEncoding];
 }
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":hash(driver),@"records":records,@"args_GPU_address":@(args.gpuAddress),@"output_GPU_address":@(output.gpuAddress),@"counter_GPU_address":@(counter.gpuAddress),@"parameters_GPU_address":@(parameters.gpuAddress),@"indirect_byte_offset":@64,@"committed":@NO,@"GPU_dispatch":@NO,@"ICB_created":@NO,
  @"scope":@"Own-process native packet capture, public encoding only, uncommitted command buffers. No native memory writes, packet injection, private calls or replay."};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
