// SPDX-License-Identifier: MIT
// Capture metadata in public dyld callbacks, before an image can be unmapped.
#import <Foundation/Foundation.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <dlfcn.h>
#include <atomic>
#include <algorithm>
#include <cstdint>
#include <cstring>

namespace {
constexpr unsigned capacity=2048;
struct Entry {
    std::atomic<bool> ready{false}, alive{false};
    const mach_header *header=nullptr;
    char identifier[1024]{};
    uint8_t uuid[16]{};
    uint32_t current=0, compatibility=0, platform=0, minOS=0, sdk=0;
    struct Build {uint32_t platform,minOS,sdk,command;};
    Build builds[8]{};unsigned buildCount=0;
    bool valid=false, hasUUID=false, hasID=false, idTruncated=false;
};
Entry entries[capacity];
std::atomic<unsigned> added{0}, removed{0}, dropped{0}, invalid{0};

void onAdd(const mach_header *mh,intptr_t) {
    unsigned i=added.fetch_add(1,std::memory_order_relaxed);
    if(i>=capacity){dropped.fetch_add(1);return;}
    Entry &e=entries[i];e.header=mh;
    if(mh && mh->magic==MH_MAGIC_64) {
        const auto *h=reinterpret_cast<const mach_header_64 *>(mh);
        if(h->ncmds<=4096 && h->sizeofcmds<=1024*1024) {
            const uint8_t *begin=reinterpret_cast<const uint8_t *>(h+1);
            size_t offset=0;bool ok=true;
            for(uint32_t j=0;j<h->ncmds;j++) {
                if(offset+sizeof(load_command)>h->sizeofcmds){ok=false;break;}
                const auto *c=reinterpret_cast<const load_command *>(begin+offset);
                if(c->cmdsize<sizeof(load_command)||c->cmdsize>h->sizeofcmds-offset){ok=false;break;}
                if(c->cmd==LC_UUID && c->cmdsize>=sizeof(uuid_command)) {
                    memcpy(e.uuid,reinterpret_cast<const uuid_command *>(c)->uuid,16);e.hasUUID=true;
                } else if(c->cmd==LC_ID_DYLIB && c->cmdsize>=sizeof(dylib_command)) {
                    const auto *d=reinterpret_cast<const dylib_command *>(c);
                    if(d->dylib.name.offset>=sizeof(dylib_command)&&d->dylib.name.offset<c->cmdsize) {
                        const char *s=reinterpret_cast<const char *>(c)+d->dylib.name.offset;
                        size_t limit=c->cmdsize-d->dylib.name.offset,n=strnlen(s,limit);
                        if(n==limit){ok=false;break;}
                        e.idTruncated=n>=sizeof(e.identifier);
                        memcpy(e.identifier,s,std::min(n,sizeof(e.identifier)-1));e.hasID=true;
                        e.current=d->dylib.current_version;e.compatibility=d->dylib.compatibility_version;
                    } else {ok=false;break;}
                } else if(c->cmd==LC_BUILD_VERSION && c->cmdsize>=sizeof(build_version_command)) {
                    const auto *b=reinterpret_cast<const build_version_command *>(c);
                    e.platform=b->platform;e.minOS=b->minos;e.sdk=b->sdk;
                    if(e.buildCount>=8){ok=false;break;}
                    e.builds[e.buildCount++]={b->platform,b->minos,b->sdk,c->cmd};
                } else if(c->cmd==LC_VERSION_MIN_MACOSX && c->cmdsize>=sizeof(version_min_command)) {
                    const auto *b=reinterpret_cast<const version_min_command *>(c);
                    if(e.buildCount>=8){ok=false;break;}
                    e.builds[e.buildCount++]={1,b->version,b->sdk,c->cmd};
                }
                offset+=c->cmdsize;
            }
            e.valid=ok && offset==h->sizeofcmds && !e.idTruncated;
        }
    }
    if(!e.valid)invalid.fetch_add(1);
    e.alive.store(true,std::memory_order_relaxed);e.ready.store(true,std::memory_order_release);
}
void onRemove(const mach_header *mh,intptr_t) {
    removed.fetch_add(1,std::memory_order_relaxed);
    for(unsigned i=0;i<std::min(added.load(std::memory_order_acquire),capacity);i++) {
        Entry &e=entries[i];
        if(e.ready.load(std::memory_order_acquire)&&e.header==mh)e.alive.store(false,std::memory_order_release);
    }
}
NSString *version(uint32_t v){return [NSString stringWithFormat:@"%u.%u.%u",v>>16,(v>>8)&255,v&255];}
bool relevant(const char *s) {
    for(const char *needle:{"AppleGVA","VideoToolbox","VideoDecodeAcceleration","GeForce",
                           "MetalOld","/Metal.framework/","VideoImageFixture"})
        if(strstr(s,needle))return true;
    return false;
}
}

extern "C" void KPVideoImagesStart() {
    // Callbacks use bounded static storage and C operations; no Foundation or loader calls.
    _dyld_register_func_for_remove_image(onRemove);
    _dyld_register_func_for_add_image(onAdd);
}
extern "C" NSDictionary *KPVideoImagesSnapshot() {
    NSMutableArray *rows=[NSMutableArray array];unsigned active=0,pending=0;
    unsigned n=std::min(added.load(std::memory_order_acquire),capacity);
    for(unsigned i=0;i<n;i++) {
        Entry &e=entries[i];if(!e.ready.load(std::memory_order_acquire)){pending++;continue;}
        bool live=e.alive.load(std::memory_order_acquire);active+=live;
        Dl_info info{};if(live)dladdr(e.header,&info);
        // dladdr uses only the address key. Recheck removal before trusting its current path.
        bool stable=live&&e.alive.load(std::memory_order_acquire);
        const char *path=stable&&info.dli_fname?info.dli_fname:"";
        NSMutableString *uuid=[NSMutableString string];
        if(e.hasUUID)for(uint8_t x:e.uuid)[uuid appendFormat:@"%02x",x];
        NSMutableArray *builds=[NSMutableArray array];
        for(unsigned j=0;j<e.buildCount;j++) {
            const auto &b=e.builds[j];[builds addObject:@{@"platform":@(b.platform),
                @"minimum_OS":version(b.minOS),@"SDK":version(b.sdk),
                @"command":b.command==LC_BUILD_VERSION?@"LC_BUILD_VERSION":@"LC_VERSION_MIN_MACOSX"}];
        }
        [rows addObject:@{@"event_index":@(i),@"alive":@(live),@"path_mapping_stable":@(stable),
            @"path":@(path),@"install_name":@(e.identifier),@"has_install_name":@(e.hasID),
            @"UUID":uuid,@"current_version":version(e.current),@"compatibility_version":version(e.compatibility),
            @"platform":@(e.platform),@"minimum_OS":version(e.minOS),@"build_SDK":version(e.sdk),
            @"build_versions":builds,@"build_summary_is_last_LC_BUILD_VERSION":@YES,
            @"header_metadata_valid":@(e.valid),@"relevant":@(relevant(path)||relevant(e.identifier))}];
    }
    return @{@"added":@(added.load()),@"removed":@(removed.load()),@"active":@(active),
        @"dropped":@(dropped.load()),@"invalid":@(invalid.load()),@"not_ready":@(pending),@"images":rows,
        @"source":@"public dyld add/remove callbacks; load commands copied at add time",
        @"UUID_is_file_SHA256":@NO,@"image_count_iteration_used":@NO,@"program_bytes_captured":@NO};
}
extern "C" NSArray *KPVideoExistingGVASymbols() {
    NSMutableArray *rows=[NSMutableArray array];
    const char *image="/System/Library/PrivateFrameworks/AppleGVA.framework/Versions/A/AppleGVA";
    // RTLD_NOLOAD cannot load a previously absent image; no private factory is invoked.
    dlerror();void *handle=dlopen(image,RTLD_LAZY|RTLD_LOCAL|RTLD_NOLOAD);
    const char *error=dlerror();NSString *message=error?@(error):@"";
    for(const char *name:{"AVF_CreateMediaAcceleratorInterface","AVFQTX_CreateMediaAcceleratorInterface",
        "AVFQTXENC_CreateMediaAcceleratorInterface","AVFCODEC_CreateMediaAcceleratorInterface",
        "AVD_CreateAVDAccelerator"}) {
        void *symbol=handle?dlsym(handle,name):nullptr;Dl_info info{};if(symbol)dladdr(symbol,&info);
        [rows addObject:@{@"name":@(name),@"existing_GVA_handle":@(handle!=nullptr),@"found":@(symbol!=nullptr),
            @"image":@(info.dli_fname?:""),@"image_offset":@(info.dli_fbase?(uintptr_t)symbol-(uintptr_t)info.dli_fbase:0),
            @"lookup_error":message,@"invoked":@NO}];
    }
    if(handle)dlclose(handle);
    return rows;
}
