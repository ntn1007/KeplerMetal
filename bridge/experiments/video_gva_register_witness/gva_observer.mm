// SPDX-License-Identifier: MIT
// Own-process experiment. Observes the allocator only after exact live-image
// validation; it never calls AppleGVA or changes its code or the allocation.
#import <Foundation/Foundation.h>
#include "witness.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/mach_vm.h>
#include <new>
#include <sched.h>
#include <unistd.h>
#include <cstring>
#include <cstdio>

using Allocator=void*(*)(std::size_t,const std::nothrow_t&) noexcept;
extern "C" {
#pragma GCC visibility push(hidden)
alignas(8) uint64_t KPAllocActive=0,KPAllocExpected=0,KPAllocCount=0,KPAllocDropped=0,KPAllocInflight=0;
alignas(128) KPAllocRecord KPAllocRecords[KPAllocCapacity]{};
void *KPAllocOriginal=reinterpret_cast<void*>(static_cast<Allocator>(::operator new));
#pragma GCC visibility pop
}
__attribute__((used,section("__DATA,__interpose"))) static const struct {const void *replacement,*original;} pair=
    {(const void*)&KPAllocTail,reinterpret_cast<const void*>(static_cast<Allocator>(::operator new))};

namespace {
constexpr uint8_t wantedUUID[16]={0xca,0x54,0x14,0xf3,0x69,0x37,0x3c,0x05,0x9e,0xa2,0xd8,0x2b,0x35,0xaf,0xd4,0xf0};
constexpr uint8_t wantedSHA[32]={0xcb,0x8e,0x85,0x19,0x7a,0x4b,0x37,0x27,0x0c,0xed,0x86,0xa0,0x70,0xfe,0xcb,0x85,0xbb,0x61,0xea,0x56,0xaa,0x98,0x89,0x29,0x96,0x65,0x8a,0x30,0x45,0x44,0xdb,0x0c};
uint64_t matchedImages=0,validRegion=0,allocatorMatched=0,removed=0;
const mach_header *matchedHeader=nullptr;

bool readable(uintptr_t address,size_t length){
    mach_vm_address_t begin=address;mach_vm_size_t span=0;vm_region_basic_info_data_64_t info{};
    mach_msg_type_number_t n=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=0;
    kern_return_t k=mach_vm_region(mach_task_self(),&begin,&span,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&n,&object);
    if(object)mach_port_deallocate(mach_task_self(),object);
    return k==KERN_SUCCESS && (info.protection&VM_PROT_READ) && address>=begin && length<=span && address-begin<=span-length;
}
void imageAdded(const mach_header *header,intptr_t){
    if(!allocatorMatched||!header||header->magic!=MH_MAGIC_64)return;
    auto h=reinterpret_cast<const mach_header_64*>(header);
    if(h->ncmds>4096||h->sizeofcmds>16*1024*1024||!readable((uintptr_t)(h+1),h->sizeofcmds))return;
    const uint8_t *cursor=reinterpret_cast<const uint8_t*>(h+1),*end=cursor+h->sizeofcmds;bool found=false;
    for(uint32_t i=0;i<h->ncmds;i++){
        if(size_t(end-cursor)<sizeof(load_command))return;
        auto lc=reinterpret_cast<const load_command*>(cursor);
        if(lc->cmdsize<sizeof(load_command)||lc->cmdsize>size_t(end-cursor))return;
        if(lc->cmd==LC_UUID && lc->cmdsize>=sizeof(uuid_command)){
            auto uuid=reinterpret_cast<const uuid_command*>(lc);if(!std::memcmp(uuid->uuid,wantedUUID,16))found=true;
        }
        cursor+=lc->cmdsize;
    }
    if(!found||cursor!=end)return;
    __atomic_add_fetch(&matchedImages,1,__ATOMIC_RELAXED);
    uintptr_t base=(uintptr_t)header;if(base>UINTPTR_MAX-115359||!readable(base+115359,719))return;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256((const void*)(base+115359),719,digest);
    if(std::memcmp(digest,wantedSHA,sizeof(wantedSHA)))return;
    if(__atomic_load_n(&validRegion,__ATOMIC_ACQUIRE))return;
    matchedHeader=header;KPAllocExpected=base+115466;
    __atomic_store_n(&validRegion,1,__ATOMIC_RELEASE);
    __atomic_store_n(&KPAllocActive,1,__ATOMIC_RELEASE);
}
void imageRemoved(const mach_header *header,intptr_t){
    if(header==matchedHeader){__atomic_store_n(&KPAllocActive,0,__ATOMIC_RELEASE);__atomic_store_n(&removed,1,__ATOMIC_RELEASE);}
}
__attribute__((constructor)) void setup(){
    Dl_info info{};
    if(KPAllocOriginal && KPAllocOriginal!=(void*)&KPAllocTail && dladdr(KPAllocOriginal,&info) && info.dli_fname && info.dli_fbase &&
       !std::strcmp(info.dli_fname,"/usr/lib/libc++abi.dylib") &&
       (uintptr_t)KPAllocOriginal-(uintptr_t)info.dli_fbase==80258)allocatorMatched=1;
    _dyld_register_func_for_remove_image(imageRemoved);
    _dyld_register_func_for_add_image(imageAdded);
}
__attribute__((destructor)) void finish(){
    __atomic_store_n(&KPAllocActive,0,__ATOMIC_RELEASE);
    for(unsigned i=0;i<100000 && __atomic_load_n(&KPAllocInflight,__ATOMIC_ACQUIRE);i++)sched_yield();
    uint64_t pending=__atomic_load_n(&KPAllocInflight,__ATOMIC_ACQUIRE),count=__atomic_load_n(&KPAllocCount,__ATOMIC_ACQUIRE);
    uint64_t drops=__atomic_load_n(&KPAllocDropped,__ATOMIC_ACQUIRE);
    char line[300];int n=std::snprintf(line,sizeof(line),"KM_GVA_REGISTER profile=%llu allocator=%llu images=%llu removed=%llu calls=%llu dropped=%llu pending=%llu\n",
       (unsigned long long)validRegion,(unsigned long long)allocatorMatched,(unsigned long long)matchedImages,(unsigned long long)removed,
       (unsigned long long)count,(unsigned long long)drops,(unsigned long long)pending);
    if(n>0&&n<(int)sizeof(line))write(STDERR_FILENO,line,(size_t)n);
    if(!pending)for(uint64_t i=0;i<count&&i<KPAllocCapacity;i++){
        const auto &r=KPAllocRecords[i];bool ready=__atomic_load_n(&r.ready,__ATOMIC_ACQUIRE);
        n=std::snprintf(line,sizeof(line),"KM_GVA_REGISTER_EVENT index=%llu ready=%d selector=%llu allocation_size=%llu caller_match=%d\n",
           (unsigned long long)i,ready?1:0,(unsigned long long)r.r14,(unsigned long long)r.args[0],r.caller==KPAllocExpected?1:0);
        if(n>0&&n<(int)sizeof(line))write(STDERR_FILENO,line,(size_t)n);
    }
}
}
