// SPDX-License-Identifier: MIT
// Bounded same-process type-3/type-6 association witness; no selector or GPU command.
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
    if(argc!=3 || (strcmp(argv[1],"inventory") && strcmp(argv[1],"pair") &&
                    strcmp(argv[1],"attach"))) return 2;
    if(!argv[2][0] || strspn(argv[2],"0123456789")!=strlen(argv[2])) return 2;
    errno=0;char *end=nullptr;uint64_t target=strtoull(argv[2],&end,10);
    bool inventory=!strcmp(argv[1],"inventory");
    bool metal=!inventory;
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
      @"context_open_attempts":@0,@"context_returned":@NO,@"context_close_attempts":@0,
      @"shared_open_attempts":@0,@"shared_returned":@NO,@"shared_close_attempts":@0,
      @"association_attempts":@0,@"handles_distinct":@NO,@"explicit_selector_calls":@0,
      @"explicit_GPU_commands":@0,@"hardware_video_execution_proved":@NO,
      @"status":inventory?@"INVENTORY_ONLY":@"TARGET_NOT_QUALIFIED"}];
    NSArray<id<MTLDevice>> *devices=nil;id<MTLDevice> device=nil;
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

        }
        if(ready){
            io_connect_t context=IO_OBJECT_NULL,shared=IO_OBJECT_NULL;
            r[@"context_open_attempts"]=@1;
            kern_return_t ck=IOServiceOpen(selected,mach_task_self(),3,&context);
            r[@"context_open_status"]=@(ck);r[@"context_returned"]=@(context!=IO_OBJECT_NULL);
            if(!ck && context){
                r[@"shared_open_attempts"]=@1;
                kern_return_t sk=IOServiceOpen(selected,mach_task_self(),6,&shared);
                r[@"shared_open_status"]=@(sk);r[@"shared_returned"]=@(shared!=IO_OBJECT_NULL);
                if(!sk && shared && shared!=context){
                    r[@"handles_distinct"]=@YES;
                    r[@"status"]=@"PAIR_OPEN";
                    if(!strcmp(argv[1],"attach")) {
                        r[@"association_attempts"]=@1;
                        kern_return_t ak=IOConnectAddClient(context,shared);
                        r[@"association_status"]=@(ak);
                        r[@"status"]=ak?@"ASSOCIATION_REFUSED":@"ASSOCIATION_ACCEPTED";
                    }
                } else r[@"status"]=@"SHARED_OPEN_FAILED";
            } else r[@"status"]=@"CONTEXT_OPEN_FAILED";
            // Always release the context before the shared connection.
            if(context){r[@"context_close_attempts"]=@1;r[@"context_close_status"]=@(IOServiceClose(context));}
            if(shared){r[@"shared_close_attempts"]=@1;r[@"shared_close_status"]=@(IOServiceClose(shared));}
        }
    }
    // The Metal device remains alive until both connections close.
    if(devices)[devices release];
    if(selected)IOObjectRelease(selected);
    NSData *json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];
    if(!json)return 3;
    fwrite(json.bytes,1,json.length,stdout);puts("");
    return 0;
} }
