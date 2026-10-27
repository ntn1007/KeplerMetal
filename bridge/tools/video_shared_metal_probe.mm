// SPDX-License-Identifier: MIT
// Bounded same-process Metal initialization / shared-client open witness.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

static uint32_t pciValue(io_registry_entry_t entry, CFStringRef key) {
    CFTypeRef v=IORegistryEntryCreateCFProperty(entry,key,kCFAllocatorDefault,0);
    uint32_t n=0;
    if (v && CFGetTypeID(v)==CFDataGetTypeID() && CFDataGetLength((CFDataRef)v)==4) {
        const UInt8 *p=CFDataGetBytePtr((CFDataRef)v);
        n=(uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
    }
    if(v) CFRelease(v);
    return n;
}

// Nearest PCI ancestor, checked by registry identity rather than marketing name.
static bool gpuAncestor(io_registry_entry_t entry, uint64_t *id) {
    if(!entry || IOObjectRetain(entry)!=KERN_SUCCESS) return false;
    io_registry_entry_t current=entry;
    bool found=false;
    for(unsigned depth=0;depth<32 && current;depth++) {
        if(IOObjectConformsTo(current,"IOPCIDevice")) {
            uint64_t rid=0;
            found=pciValue(current,CFSTR("vendor-id"))==0x10de &&
                  pciValue(current,CFSTR("device-id"))==0x1198 &&
                  IORegistryEntryGetRegistryEntryID(current,&rid)==KERN_SUCCESS && rid;
            if(found)*id=rid;
            break;
        }
        io_registry_entry_t parent=IO_OBJECT_NULL;
        kern_return_t kr=IORegistryEntryGetParentEntry(current,kIOServicePlane,&parent);
        IOObjectRelease(current);current=IO_OBJECT_NULL;
        if(kr!=KERN_SUCCESS) break;
        current=parent;
    }
    if(current) IOObjectRelease(current);
    return found;
}

int main(int argc,char **argv) { @autoreleasepool {
    if(argc!=3 || (strcmp(argv[1],"inventory") && strcmp(argv[1],"direct") &&
                    strcmp(argv[1],"device") && strcmp(argv[1],"queue"))) return 2;
    if(!argv[2][0] || strspn(argv[2],"0123456789")!=strlen(argv[2])) return 2;
    errno=0;char *end=nullptr;uint64_t target=strtoull(argv[2],&end,10);
    bool inventory=!strcmp(argv[1],"inventory");
    bool metal=!strcmp(argv[1],"device") || !strcmp(argv[1],"queue");
    bool wantQueue=!strcmp(argv[1],"queue");
    if(errno || !end || *end || (!inventory && !target)) return 2;
    io_iterator_t it=IO_OBJECT_NULL;io_service_t selected=IO_OBJECT_NULL;
    kern_return_t match=IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("nvAccelerator"),&it);
    NSMutableArray *rows=[NSMutableArray array];unsigned count=0,inspected=0;uint64_t pci=0;bool truncated=false;
    if(match==KERN_SUCCESS) {
        io_service_t svc;
        while((svc=IOIteratorNext(it))) {
            if(++inspected>16){truncated=true;IOObjectRelease(svc);break;}
            io_name_t cls={};uint64_t rid=0,prid=0;
            kern_return_t cs=IOObjectGetClass(svc,cls),rs=IORegistryEntryGetRegistryEntryID(svc,&rid);
            bool gpu=gpuAncestor(svc,&prid);
            bool candidate=!cs && !rs && !strcmp(cls,"nvAccelerator") && gpu && rid==target;
            [rows addObject:@{@"class":@(cls),@"class_status":@(cs),@"registry_status":@(rs),
                              @"registry_ID":@(rid),@"gpu_ancestor":@(gpu),@"pci_registry_ID":@(prid),@"candidate":@(candidate)}];
            if(candidate){count++;if(!selected){IOObjectRetain(svc);selected=svc;pci=prid;}}
            IOObjectRelease(svc);
        }
        IOObjectRelease(it);
    }
    NSMutableDictionary *r=[NSMutableDictionary dictionaryWithDictionary:@{
      @"mode":@(argv[1]),@"pid":@(getpid()),@"uid":@(getuid()),@"euid":@(geteuid()),
      @"matching_status":@(match),@"truncated":@(truncated),@"services":rows,
      @"target":@(target),@"candidate_count":@(count),@"pci_registry_ID":@(pci),
      @"metal_enumeration_attempted":@NO,@"metal_candidates":@0,@"metal_registry_ID":@0,@"metal_pci_registry_ID":@0,
      @"queue_attempted":@NO,@"queue_created":@NO,@"open_attempts":@0,
      @"connection_returned":@NO,@"close_attempts":@0,@"explicit_IOConnect_calls":@0,
      @"explicit_GPU_commands":@0,@"hardware_video_execution_proved":@NO,
      @"status":inventory?@"INVENTORY_ONLY":@"TARGET_NOT_QUALIFIED"}];
    NSArray<id<MTLDevice>> *devices=nil;id<MTLDevice> device=nil;id<MTLCommandQueue> queue=nil;
    if(!inventory && !match && !truncated && count==1 && selected) {
        bool ready=true;
        if(metal) {
            r[@"metal_enumeration_attempted"]=@YES;
            devices=MTLCopyAllDevices();unsigned hits=0;
            for(id<MTLDevice> d in devices) {
                uint64_t mpci=0;
                io_service_t m=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(d.registryID));
                bool same=m && gpuAncestor(m,&mpci) && mpci==pci;
                if(m)IOObjectRelease(m);
                if(same){hits++;device=d;r[@"metal_registry_ID"]=@(d.registryID);r[@"metal_pci_registry_ID"]=@(mpci);r[@"metal_name"]=d.name ?: @"";}
            }
            r[@"metal_candidates"]=@(hits);
            if(hits!=1){ready=false;r[@"status"]=@"METAL_DEVICE_NOT_QUALIFIED";}
            if(ready && wantQueue){
                r[@"queue_attempted"]=@YES;queue=[device newCommandQueue];r[@"queue_created"]=@(queue!=nil);
                if(!queue){ready=false;r[@"status"]=@"METAL_QUEUE_FAILED";}
            }
        }
        if(ready){
            io_connect_t conn=IO_OBJECT_NULL;r[@"open_attempts"]=@1;
            kern_return_t status=IOServiceOpen(selected,mach_task_self(),6,&conn);
            r[@"open_status"]=@(status);r[@"connection_returned"]=@(conn!=IO_OBJECT_NULL);
            if(conn){r[@"close_attempts"]=@1;kern_return_t close=IOServiceClose(conn);r[@"close_status"]=@(close);
                r[@"status"]=!status&&!close?@"OPEN_CLOSED":@"OPEN_OR_CLOSE_FAILED";
            } else r[@"status"]=status?@"OPEN_REFUSED":@"INVALID_OPEN_RESULT";
        }
    }
    // Queue and its device remain alive until the connection is closed or refused.
    if(queue)[queue release];
    if(devices)[devices release];
    if(selected)IOObjectRelease(selected);
    NSData *json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];
    if(!json)return 3;
    fwrite(json.bytes,1,json.length,stdout);puts("");
    return [r[@"status"] isEqual:@"OPEN_OR_CLOSE_FAILED"] || [r[@"status"] isEqual:@"INVALID_OPEN_RESULT"] ? 4 : 0;
} }
