// SPDX-License-Identifier: MIT
// Process-local observation of public IOKit imports. Calls are forwarded.
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <pthread.h>
#include <stdint.h>
#include <string.h>
#include "observer.h"
#define SLOTS 256
static uint64_t counters[4+SLOTS*3];
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static struct KMDetails details;
static io_connect_t ports[KM_MAX_SERVICES];
static void count(unsigned base,uint32_t key,io_connect_t port) {
    __atomic_fetch_add(&counters[base],1,__ATOMIC_RELAXED);
    if(key<SLOTS) __atomic_fetch_add(&counters[4+(base-1)*SLOTS+key],1,__ATOMIC_RELAXED);
    pthread_mutex_lock(&mutex);
    uint32_t service=KM_UNKNOWN_SERVICE;
    if(port) for(uint32_t i=details.service_count;i>0;i--) if(ports[i-1]==port) { service=i-1; break; }
    if(details.event_count<KM_MAX_EVENTS) details.events[details.event_count++]=(struct KMEvent){base,key,service};
    else details.dropped++;
    pthread_mutex_unlock(&mutex);
}
__attribute__((visibility("default"))) void km_observer_snapshot(uint64_t* out) {
    for(unsigned i=0;i<4+SLOTS*3;i++) out[i]=__atomic_load_n(&counters[i],__ATOMIC_RELAXED);
}
__attribute__((visibility("default"))) void km_observer_details(struct KMDetails* out) {
    pthread_mutex_lock(&mutex); memcpy(out,&details,sizeof details); pthread_mutex_unlock(&mutex);
}
static kern_return_t observed_open(io_service_t s,task_port_t t,uint32_t type,io_connect_t* c) {
    __atomic_fetch_add(&counters[0],1,__ATOMIC_RELAXED); kern_return_t r=IOServiceOpen(s,t,type,c);
    if(r==KERN_SUCCESS && c && *c) {
        io_name_t cls={0},name={0}; kern_return_t cr=IOObjectGetClass(s,cls), nr=IORegistryEntryGetName(s,name);
        pthread_mutex_lock(&mutex);
        if(details.service_count<KM_MAX_SERVICES) {
            uint32_t i=details.service_count++; ports[i]=*c; details.services[i].type=type;
            if(cr==KERN_SUCCESS) memcpy(details.services[i].class_name,cls,sizeof cls);
            if(nr==KERN_SUCCESS) memcpy(details.services[i].registry_name,name,sizeof name);
            details.services[i].class_name[sizeof details.services[i].class_name-1]=0;
            details.services[i].registry_name[sizeof details.services[i].registry_name-1]=0;
        } else details.dropped++;
        pthread_mutex_unlock(&mutex);
    }
    return r;
}
static kern_return_t observed_method(io_connect_t c,uint32_t sel,const uint64_t* in,uint32_t ni,
    const void* in_struct,size_t in_size,uint64_t* out,uint32_t* no,void* out_struct,size_t* out_size) {
    count(1,sel,c); return IOConnectCallMethod(c,sel,in,ni,in_struct,in_size,out,no,out_struct,out_size);
}
static kern_return_t observed_struct(io_connect_t c,uint32_t sel,const void* in,size_t ni,void* out,size_t* no) {
    count(2,sel,c); return IOConnectCallStructMethod(c,sel,in,ni,out,no);
}
static kern_return_t observed_scalar(io_connect_t c,uint32_t sel,const uint64_t* in,uint32_t ni,uint64_t* out,uint32_t* no) {
    count(3,sel,c); return IOConnectCallScalarMethod(c,sel,in,ni,out,no);
}
#define INTERPOSE(replacement, original) \
  __attribute__((used)) static struct { const void* replacement_ptr; const void* original_ptr; } \
  entry_##replacement __attribute__((section("__DATA,__interpose"))) = {(const void*)(replacement),(const void*)(original)}
INTERPOSE(observed_open,IOServiceOpen);
INTERPOSE(observed_method,IOConnectCallMethod);
INTERPOSE(observed_struct,IOConnectCallStructMethod);
INTERPOSE(observed_scalar,IOConnectCallScalarMethod);
