// SPDX-License-Identifier: MIT
// Public Metal GPU read and write after purge, with exact raw CPU readback.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

namespace {
uint32_t pciValue(io_registry_entry_t e,CFStringRef key){CFTypeRef v=IORegistryEntryCreateCFProperty(e,key,kCFAllocatorDefault,0);uint32_t n=0;if(v&&CFGetTypeID(v)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)v)==4){const UInt8 *p=CFDataGetBytePtr((CFDataRef)v);n=p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}if(v)CFRelease(v);return n;}
bool gpuAncestor(io_registry_entry_t e,uint64_t *id){if(!e||IOObjectRetain(e)!=KERN_SUCCESS)return false;io_registry_entry_t cur=e;bool found=false;for(unsigned i=0;i<32&&cur;i++){if(IOObjectConformsTo(cur,"IOPCIDevice")){uint64_t rid=0;found=pciValue(cur,CFSTR("vendor-id"))==0x10de&&pciValue(cur,CFSTR("device-id"))==0x1198&&IORegistryEntryGetRegistryEntryID(cur,&rid)==KERN_SUCCESS&&rid;if(found)*id=rid;break;}io_registry_entry_t parent=IO_OBJECT_NULL;kern_return_t k=IORegistryEntryGetParentEntry(cur,kIOServicePlane,&parent);IOObjectRelease(cur);cur=IO_OBJECT_NULL;if(k!=KERN_SUCCESS)break;cur=parent;}if(cur)IOObjectRelease(cur);return found;}
struct Params {uint32_t seed,n;};
}
int main(int argc,char **argv){@autoreleasepool {
    if(argc!=5 || (strcmp(argv[1],"native")&&strcmp(argv[1],"purge")&&strcmp(argv[1],"negative")))return 2;
    if(!argv[2][0]||strspn(argv[2],"0123456789")!=strlen(argv[2]))return 2;
    errno=0;char *end=nullptr;uint64_t rid=strtoull(argv[2],&end,10);if(errno||!end||*end||!rid||!getuid()||getuid()!=geteuid())return 2;
    io_service_t service=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(rid));io_name_t cls={};uint64_t pci=0;
    bool valid=service&&!IOObjectGetClass(service,cls)&&!strcmp(cls,"nvAccelerator")&&gpuAncestor(service,&pci);if(service)IOObjectRelease(service);if(!valid)return 3;
    NSArray<id<MTLDevice>> *devices=MTLCopyAllDevices();id<MTLDevice>d=nil;unsigned hits=0;
    for(id<MTLDevice>x in devices){uint64_t mpci=0;io_service_t s=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(x.registryID));bool match=s&&gpuAncestor(s,&mpci)&&mpci==pci&&x.registryID==rid;if(s)IOObjectRelease(s);if(match){d=x;hits++;}}
    if(hits!=1||!d)return 4;
    NSError *error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[3])] error:&error];if(!lib){fprintf(stderr,"library: %s\n",error.description.UTF8String?:"");return 5;}
    id<MTLFunction>readFn=[lib newFunctionWithName:@"consume"],writeFn=[lib newFunctionWithName:@"produce"];
    id<MTLComputePipelineState>readPSO=readFn?[d newComputePipelineStateWithFunction:readFn error:&error]:nil;
    id<MTLComputePipelineState>writePSO=writeFn?[d newComputePipelineStateWithFunction:writeFn error:&error]:nil;
    if(!readPSO||!writePSO||readPSO.maxTotalThreadsPerThreadgroup<32||writePSO.maxTotalThreadsPerThreadgroup<32){fprintf(stderr,"pipeline: %s\n",error.description.UTF8String?:"");return 6;}
    const uint32_t n=1024*1024,seed=0xfeed1234u;const size_t bytes=(size_t)n*4,guard=64;
    id<MTLBuffer>target=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];id<MTLBuffer>output=[d newBufferWithLength:bytes+2*guard options:MTLResourceStorageModeShared];
    if(!target||!output||!target.contents||!output.contents||target.length!=bytes||output.length!=bytes+2*guard)return 7;
    MTLPurgeableState initial=[target setPurgeableState:MTLPurgeableStateKeepCurrent],prevEmpty=(MTLPurgeableState)0,empty=(MTLPurgeableState)0,prevRestore=(MTLPurgeableState)0,restored=initial;
    if(!strcmp(argv[1],"purge")){
        prevEmpty=[target setPurgeableState:MTLPurgeableStateEmpty];empty=[target setPurgeableState:MTLPurgeableStateKeepCurrent];
        prevRestore=[target setPurgeableState:MTLPurgeableStateNonVolatile];restored=[target setPurgeableState:MTLPurgeableStateKeepCurrent];
        if(initial!=MTLPurgeableStateNonVolatile||prevEmpty!=initial||empty!=MTLPurgeableStateEmpty||prevRestore!=empty||restored!=MTLPurgeableStateNonVolatile)return 8;
    }
    if(restored!=MTLPurgeableStateNonVolatile)return 8;
    auto *in=(uint32_t*)target.contents;for(uint32_t i=0;i<n;i++)in[i]=i^0x5a39d117u;memset(output.contents,0xa5,bytes+2*guard);
    bool dispatch=strcmp(argv[1],"negative")!=0;NSUInteger status=0;
    if(dispatch){
        id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];if(!q||!cb)return 9;
        Params params{seed,n};id<MTLComputeCommandEncoder>read=[cb computeCommandEncoder];if(!read)return 9;
        [read setComputePipelineState:readPSO];[read setBuffer:target offset:0 atIndex:0];[read setBuffer:output offset:guard atIndex:1];[read setBytes:&params length:sizeof(params) atIndex:2];
        [read dispatchThreadgroups:MTLSizeMake(n/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[read endEncoding];
        id<MTLComputeCommandEncoder>write=[cb computeCommandEncoder];if(!write)return 9;
        [write setComputePipelineState:writePSO];[write setBuffer:target offset:0 atIndex:0];[write setBytes:&params length:sizeof(params) atIndex:2];
        [write dispatchThreadgroups:MTLSizeMake(n/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[write endEncoding];
        [cb commit];[cb waitUntilCompleted];status=cb.status;if(status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"command: %s\n",cb.error.description.UTF8String?:"");return 10;}
    }
    NSString *out=@(argv[4]);if(![[NSData dataWithBytes:target.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:@"target.bin"] options:0 error:&error])return 11;
    if(![[NSData dataWithBytes:output.contents length:bytes+2*guard]writeToFile:[out stringByAppendingPathComponent:@"output.bin"] options:0 error:&error])return 11;
    NSDictionary *r=@{@"mode":@(argv[1]),@"pid":@(getpid()),@"uid":@(getuid()),@"euid":@(geteuid()),@"gpu_registry_id":@(rid),@"pci_registry_id":@(pci),@"device_name":d.name?:@"",@"elements":@(n),@"seed":@(seed),@"guard_bytes_each":@(guard),@"command_submitted":@(dispatch),@"command_status":@(status),@"state_initial":@(initial),@"previous_empty":@(prevEmpty),@"state_empty":@(empty),@"previous_restore":@(prevRestore),@"state_restored":@(restored),@"target_length":@(target.length),@"output_length":@(output.length),@"threadgroup_size":@32,@"pipeline_read_max_threads":@(readPSO.maxTotalThreadsPerThreadgroup),@"pipeline_write_max_threads":@(writePSO.maxTotalThreadsPerThreadgroup)};
    NSData*json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];if(!json)return 12;fwrite(json.bytes,1,json.length,stdout);puts("");return 0;
} }
