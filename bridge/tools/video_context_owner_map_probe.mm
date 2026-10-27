// SPDX-License-Identifier: MIT
// Own-process context/registry witness. Explicitly maps types 2 and 1 but never
// calls IOConnectUnmapMemory, IOConnectCall* or submits a GPU command.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <mach/vm_region.h>
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

// 1: currently covered, 0: no region covers the queried address, -1: query error.
// This observes address coverage, not IOMemoryMap identity or object lifetime.
static int vmCovers(mach_vm_address_t target) {
    mach_vm_address_t start=target;mach_vm_size_t size=0;
    vm_region_basic_info_data_64_t info={};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object=MACH_PORT_NULL;
    kern_return_t k=mach_vm_region(mach_task_self(),&start,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);
    if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
    if(k==KERN_INVALID_ADDRESS)return 0;
    if(k!=KERN_SUCCESS)return -1;
    return start<=target && target-start<size ? 1 : 0;
}

// Enumerate only video-context IDs under the selected accelerator.
// Only report whether the creator value encodes this process; do not log names.
static bool creatorIsPID(NSString *value,pid_t pid) {
    return value && [value hasPrefix:[NSString stringWithFormat:@"pid %d,",(int)pid]];
}
static NSDictionary *videoChildren(io_service_t service) {
    io_iterator_t it=IO_OBJECT_NULL;
    kern_return_t kr=IORegistryEntryCreateIterator(service,kIOServicePlane,kIORegistryIterateRecursively,&it);
    NSMutableArray *ids=[NSMutableArray array];unsigned inspected=0,attempts=0;bool truncated=false,valid=false;
    if(kr==KERN_SUCCESS){
        for(unsigned attempt=0;attempt<3;attempt++){
            if(attempt)IOIteratorReset(it);[ids removeAllObjects];inspected=0;truncated=false;attempts++;
            io_registry_entry_t item;
            while((item=IOIteratorNext(it))){
                if(++inspected>2048){truncated=true;IOObjectRelease(item);break;}
                if(IOObjectConformsTo(item,"nvVideoContext")){uint64_t rid=0;io_name_t cls={};
                    kern_return_t idStatus=IORegistryEntryGetRegistryEntryID(item,&rid),classStatus=IOObjectGetClass(item,cls);
                    CFTypeRef creator=IORegistryEntryCreateCFProperty(item,CFSTR("IOUserClientCreator"),kCFAllocatorDefault,0);
                    bool creatorString=creator&&CFGetTypeID(creator)==CFStringGetTypeID();
                    bool own=creatorString&&creatorIsPID((NSString*)creator,getpid());
                    [ids addObject:@{@"id":@(rid),@"id_status":@(idStatus),@"class_status":@(classStatus),@"class":@(cls),@"creator_present":@(creator!=nullptr),@"creator_is_string":@(creatorString),@"creator_matches_self_pid":@(own)}];
                    if(creator)CFRelease(creator);}
                IOObjectRelease(item);
            }
            valid=IOIteratorIsValid(it);
            if(valid&&!truncated)break;
        }
        IOObjectRelease(it);
    }
    return @{@"status":@(kr),@"truncated":@(truncated),@"iterator_valid":@(valid),@"attempts":@(attempts),@"inspected":@(inspected),@"contexts":ids};
}


int main(int argc,char **argv) { @autoreleasepool {
    if(argc!=3 || (strcmp(argv[1],"inventory") && strcmp(argv[1],"pair") &&
                    strcmp(argv[1],"attach") && strcmp(argv[1],"owner-map-close"))) return 2;
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
      @"creator_parser_calibrated":@(creatorIsPID(@"pid 123, example",123)&&!creatorIsPID(@"pid 1234, example",123)&&!creatorIsPID(@"other pid 123, example",123)&&!creatorIsPID(nil,123)),@"status":inventory?@"INVENTORY_ONLY":@"TARGET_NOT_QUALIFIED"}];
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
            mach_vm_address_t map2=0,map1=0;mach_vm_size_t size2=0,size1=0;bool has2=false,has1=false;
            if(!strcmp(argv[1],"owner-map-close"))r[@"registry_before"]=videoChildren(selected);
            r[@"context_open_attempts"]=@1;
            kern_return_t ck=IOServiceOpen(selected,mach_task_self(),3,&context);
            r[@"context_open_status"]=@(ck);r[@"context_returned"]=@(context!=IO_OBJECT_NULL);
            if(!ck && context){
                if(!strcmp(argv[1],"owner-map-close"))r[@"registry_after_open"]=videoChildren(selected);
                r[@"shared_open_attempts"]=@1;
                kern_return_t sk=IOServiceOpen(selected,mach_task_self(),6,&shared);
                r[@"shared_open_status"]=@(sk);r[@"shared_returned"]=@(shared!=IO_OBJECT_NULL);
                if(!sk && shared && shared!=context){
                    r[@"handles_distinct"]=@YES;
                    r[@"status"]=@"PAIR_OPEN";
                    if(!strcmp(argv[1],"attach") || !strcmp(argv[1],"owner-map-close")) {
                        r[@"association_attempts"]=@1;
                        kern_return_t ak=IOConnectAddClient(context,shared);
                        r[@"association_status"]=@(ak);
                        r[@"status"]=ak?@"ASSOCIATION_REFUSED":@"ASSOCIATION_ACCEPTED";
                        if(!ak && !strcmp(argv[1],"owner-map-close")) {
                            r[@"registry_after_associate"]=videoChildren(selected);
                            NSDictionary *before=r[@"registry_before"],*opened=r[@"registry_after_open"],*associated=r[@"registry_after_associate"];
                            bool good=true;for(NSDictionary *snap in @[before,opened,associated]){good &= [snap[@"status"]intValue]==0&&[snap[@"iterator_valid"]boolValue]&&![snap[@"truncated"]boolValue];for(NSDictionary *item in snap[@"contexts"])good &= [item[@"id_status"]intValue]==0&&[item[@"class_status"]intValue]==0&&[item[@"id"]unsignedLongLongValue]!=0&&[item[@"class"]isEqual:@"nvVideoContext"];}
                            NSMutableSet *beforeIDs=[NSMutableSet set];for(NSDictionary*item in before[@"contexts"]) [beforeIDs addObject:item[@"id"]];
                            NSMutableArray *matches=[NSMutableArray array];for(NSDictionary *item in opened[@"contexts"])if([item[@"creator_matches_self_pid"]boolValue]&&![beforeIDs containsObject:item[@"id"]]){
                              for(NSDictionary *later in associated[@"contexts"])if([later[@"id"]isEqual:item[@"id"]]&&[later[@"creator_matches_self_pid"]boolValue])[matches addObject:item[@"id"]];}
                            bool ownerQualified=good&&matches.count==1;r[@"owner_qualified"]=@(ownerQualified);if(ownerQualified)r[@"owner_registry_ID"]=matches[0];
                            if(ownerQualified){r[@"map2_attempts"]=@1;
                            kern_return_t k2=IOConnectMapMemory(context,2,mach_task_self(),&map2,&size2,kIOMapAnywhere);
                            has2=!k2&&map2&&size2;r[@"map2_status"]=@(k2);r[@"map2_returned"]=@(has2);r[@"map2_bytes"]=@(size2);
                            if(has2&&size2==4096&&vmCovers(map2)==1){
                                r[@"map1_attempts"]=@1;
                                kern_return_t k1=IOConnectMapMemory(context,1,mach_task_self(),&map1,&size1,kIOMapAnywhere);
                                has1=!k1&&map1&&size1;r[@"map1_status"]=@(k1);r[@"map1_returned"]=@(has1);r[@"map1_bytes"]=@(size1);
                            }
                            if(has2)r[@"type2_before_close"]=@(vmCovers(map2));
                            if(has1)r[@"type1_before_close"]=@(vmCovers(map1));
                            bool disjoint=has1&&has2&&size1==4096&&size2==4096&&map1<=UINT64_MAX-size1&&map2<=UINT64_MAX-size2&&map1!=map2&&(map1+size1<=map2||map2+size2<=map1);
                            r[@"mapping_ranges_disjoint"]=@(disjoint);
                            r[@"status"]=(has2&&has1&&disjoint)?@"OWNER_MAP_COVERAGE_RECORDED":@"MAP_REFUSED_OR_INVALID";
                            r[@"mapping_contents_read_or_written"]=@NO;
                            r[@"explicit_unmap_calls"]=@0;
                            }else r[@"status"]=@"OWNER_NOT_QUALIFIED";
                        }
                    }
                } else r[@"status"]=@"SHARED_OPEN_FAILED";
            } else r[@"status"]=@"CONTEXT_OPEN_FAILED";
            // Always release the context before the shared connection.
            if(context){r[@"context_close_attempts"]=@1;r[@"context_close_status"]=@(IOServiceClose(context));}
            if(has2)r[@"type2_after_context_close"]=@(vmCovers(map2));
            if(has1)r[@"type1_after_context_close"]=@(vmCovers(map1));
            if(!strcmp(argv[1],"owner-map-close"))r[@"registry_after_context_close"]=videoChildren(selected);
            if(shared){r[@"shared_close_attempts"]=@1;r[@"shared_close_status"]=@(IOServiceClose(shared));}
            if(has2)r[@"type2_after_shared_close"]=@(vmCovers(map2));
            if(has1)r[@"type1_after_shared_close"]=@(vmCovers(map1));
            if(!strcmp(argv[1],"owner-map-close"))r[@"registry_after_shared_close"]=videoChildren(selected);
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
