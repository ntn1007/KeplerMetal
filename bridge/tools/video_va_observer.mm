// SPDX-License-Identifier: MIT
// Own-process lookup observation. No original instruction or argument changes.
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <atomic>
#include <algorithm>
#include <cstring>
#include <cstdint>
#include <execinfo.h>

extern "C" {
alignas(8) void *KPVideoVAOriginalCreate = nullptr;
alignas(8) void *KPVideoVAOriginalDestroy = nullptr;
alignas(8) uint64_t KPVideoVACreateCalls = 0;
alignas(8) uint64_t KPVideoVADestroyCalls = 0;
// Tail calls preserve register/stack arguments and all return conventions.
__attribute__((naked)) void KPVideoVACreateTail() {
    __asm__ volatile("pushfq\n\tlock incq _KPVideoVACreateCalls(%rip)\n\tpopfq\n\tjmpq *_KPVideoVAOriginalCreate(%rip)");
}
__attribute__((naked)) void KPVideoVADestroyTail() {
    __asm__ volatile("pushfq\n\tlock incq _KPVideoVADestroyCalls(%rip)\n\tpopfq\n\tjmpq *_KPVideoVAOriginalDestroy(%rip)");
}
}

namespace {
std::atomic<bool> enabled{false}, synthetic{false};
std::atomic<unsigned> count{0}, dropped{0};
std::atomic<unsigned> dlsymCalls{0}, bundleCalls{0};
struct Event {
    std::atomic<bool> ready{false};
    char name[128]{}, image[1024]{}, api[16]{};
    uintptr_t original = 0;
    bool substituted = false;
};
Event events[128];
struct IOEvent {
    std::atomic<bool> ready{false};
    char operation[16]{}, name[128]{}, cls[128]{}, image[1024]{}, symbol[256]{};
    uintptr_t caller = 0, imageOffset = 0;
    uint32_t connection = 0, selector = 0, status = 0, inputScalars = 0;
    uint64_t inputBytes = 0, outputBytes = 0;
    void *stack[12]{};
    unsigned stackCount = 0;
};
IOEvent ioEvents[128];
std::atomic<unsigned> ioCount{0}, ioDropped{0};

void recordIO(const char *operation, void *caller, uint32_t connection, uint32_t selector,
              kern_return_t status, uint32_t inputScalars=0, uint64_t inputBytes=0,
              uint64_t outputBytes=0, io_service_t service=0) {
    if (!enabled.load(std::memory_order_acquire)) return;
    unsigned i=ioCount.fetch_add(1,std::memory_order_relaxed);
    if (i>=128) {ioDropped.fetch_add(1);return;}
    IOEvent &e=ioEvents[i]; Dl_info info{}; dladdr(caller,&info);
    strlcpy(e.operation,operation,sizeof(e.operation));
    strlcpy(e.image,info.dli_fname ?: "",sizeof(e.image));
    strlcpy(e.symbol,info.dli_sname ?: "",sizeof(e.symbol));
    e.caller=(uintptr_t)caller; e.imageOffset=info.dli_fbase ? (uintptr_t)caller-(uintptr_t)info.dli_fbase : 0;
    e.connection=connection;e.selector=selector;e.status=(uint32_t)status;
    e.inputScalars=inputScalars;e.inputBytes=inputBytes;e.outputBytes=outputBytes;
    e.stackCount=(unsigned)backtrace(e.stack,12);
    if (service) {IORegistryEntryGetName(service,e.name);IOObjectGetClass(service,e.cls);}
    e.ready.store(true,std::memory_order_release);
}

kern_return_t observed_open(io_service_t service,task_port_t task,uint32_t type,io_connect_t *connection) {
    void *caller=__builtin_return_address(0);
    kern_return_t r=IOServiceOpen(service,task,type,connection);
    recordIO("open",caller,r==0?*connection:0,type,r,0,0,0,service);return r;
}
kern_return_t observed_close(io_connect_t connection) {
    void *caller=__builtin_return_address(0);kern_return_t r=IOServiceClose(connection);
    recordIO("close",caller,connection,0,r);return r;
}
kern_return_t observed_method(mach_port_t connection,uint32_t selector,const uint64_t *input,
    uint32_t inputCount,const void *inputStruct,size_t inputSize,uint64_t *output,
    uint32_t *outputCount,void *outputStruct,size_t *outputSize) {
    void *caller=__builtin_return_address(0);
    kern_return_t r=IOConnectCallMethod(connection,selector,input,inputCount,inputStruct,inputSize,
                                       output,outputCount,outputStruct,outputSize);
    recordIO("method",caller,connection,selector,r,inputCount,inputSize,outputSize?*outputSize:0);return r;
}

void *observe(void *pointer, const char *name, const char *api) {
    if (!enabled.load(std::memory_order_acquire) || !name ||
        (strncmp(name, "AVD_", 4) && strncmp(name, "AVF", 3) && strncmp(name, "KPVideoSelf", 11))) return pointer;
    Dl_info info{};
    if (pointer) dladdr(pointer, &info);
    bool control = synthetic.load(std::memory_order_acquire);
    bool create = !strcmp(name, control ? "KPVideoSelfCreate" : "AVD_CreateAVDAccelerator");
    bool destroy = !strcmp(name, control ? "KPVideoSelfDestroy" : "AVD_DestroyAVDAccelerator");
    bool origin = pointer && info.dli_fname && (control || !strcmp(info.dli_fname,
        "/System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver"));
    bool replaced = false;
    void *answer = pointer;
    if (origin && (create || destroy)) {
        void **slot = create ? &KPVideoVAOriginalCreate : &KPVideoVAOriginalDestroy;
        void *expected = nullptr;
        if (__atomic_compare_exchange_n(slot, &expected, pointer, false, __ATOMIC_RELEASE, __ATOMIC_ACQUIRE)
            || expected == pointer) {
            answer = (void *)(create ? KPVideoVACreateTail : KPVideoVADestroyTail);
            replaced = true;
        }
    }
    unsigned i = count.fetch_add(1, std::memory_order_relaxed);
    if (i < 128) {
        Event &e = events[i];
        strlcpy(e.name, name, sizeof(e.name));
        strlcpy(e.image, info.dli_fname ?: "", sizeof(e.image));
        strlcpy(e.api, api, sizeof(e.api));
        e.original = (uintptr_t)pointer; e.substituted = replaced;
        e.ready.store(true, std::memory_order_release);
    } else dropped.fetch_add(1, std::memory_order_relaxed);
    return answer;
}

void *observed_dlsym(void *handle, const char *name) {
    if (enabled.load(std::memory_order_acquire)) dlsymCalls.fetch_add(1, std::memory_order_relaxed);
    return observe(dlsym(handle, name), name, "dlsym");
}
void *observed_bundle(CFBundleRef bundle, CFStringRef name) {
    if (enabled.load(std::memory_order_acquire)) bundleCalls.fetch_add(1, std::memory_order_relaxed);
    void *pointer = CFBundleGetFunctionPointerForName(bundle, name);
    char text[128]{};
    if (name && CFStringGetCString(name, text, sizeof(text), kCFStringEncodingUTF8))
        return observe(pointer, text, "CFBundle");
    return pointer;
}
#define INTERPOSE(replacement, original) \
    __attribute__((used)) static const struct {const void *new_, *old_;} pair_##original \
    __attribute__((section("__DATA,__interpose"))) = {(void *)&replacement, (void *)&original};
INTERPOSE(observed_dlsym, dlsym)
INTERPOSE(observed_bundle, CFBundleGetFunctionPointerForName)
INTERPOSE(observed_open, IOServiceOpen)
INTERPOSE(observed_close, IOServiceClose)
INTERPOSE(observed_method, IOConnectCallMethod)
}

extern "C" void KPVideoTraceConfigure(bool active, bool selftest) {
    synthetic.store(selftest, std::memory_order_release);
    enabled.store(active, std::memory_order_release);
}
extern "C" NSDictionary *KPVideoTraceSnapshot() {
    bool wasEnabled=enabled.exchange(false,std::memory_order_acq_rel);
    NSMutableArray *rows = [NSMutableArray array];
    unsigned n = std::min(count.load(std::memory_order_acquire), 128u);
    for (unsigned i = 0; i < n; ++i) {
        Event &e = events[i]; if (!e.ready.load(std::memory_order_acquire)) continue;
        [rows addObject:@{@"name":@(e.name), @"API":@(e.api), @"image":@(e.image),
            @"original_pointer":@(e.original), @"tail_observer_installed":@(e.substituted)}];
    }
    NSMutableArray *io=[NSMutableArray array];
    for (unsigned i=0;i<std::min(ioCount.load(std::memory_order_acquire),128u);i++) {
        IOEvent &e=ioEvents[i];if(!e.ready.load(std::memory_order_acquire))continue;
        NSMutableArray *stack=[NSMutableArray array];
        for(unsigned j=0;j<e.stackCount;j++) {Dl_info d{};dladdr(e.stack[j],&d);
            [stack addObject:@{@"image":@(d.dli_fname ?: ""),@"symbol":@(d.dli_sname ?: ""),
                @"offset":@(d.dli_fbase ? (uintptr_t)e.stack[j]-(uintptr_t)d.dli_fbase : 0)}];}
        [io addObject:@{@"operation":@(e.operation),@"service":@(e.name),@"class":@(e.cls),
            @"connection":@(e.connection),@"type_or_selector":@(e.selector),@"status":@(e.status),
            @"input_scalar_count":@(e.inputScalars),@"input_struct_bytes":@(e.inputBytes),
            @"output_struct_bytes":@(e.outputBytes),@"caller_image":@(e.image),
            @"caller_symbol":@(e.symbol),@"caller_offset":@(e.imageOffset),@"stack":stack}];
    }
    return @{@"enabled":@(wasEnabled), @"disabled_before_snapshot":@YES, @"synthetic_control":@(synthetic.load()),
        @"events":rows, @"dropped":@(dropped.load()),
        @"dlsym_calls_observed":@(dlsymCalls.load()), @"bundle_calls_observed":@(bundleCalls.load()),
        @"IOKit_events":io,@"IOKit_dropped":@(ioDropped.load()),
        @"create_calls":@(__atomic_load_n(&KPVideoVACreateCalls, __ATOMIC_ACQUIRE)),
        @"destroy_calls":@(__atomic_load_n(&KPVideoVADestroyCalls, __ATOMIC_ACQUIRE)),
        @"native_instructions_modified":@NO, @"arguments_modified":@NO,
        @"direct_unknown_vendor_call":@NO, @"hardware_video_execution_proved":@NO};
}
