// SPDX-License-Identifier: MIT
// CPU laboratory interposer. It never dereferences or modifies an allocation.
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <malloc/malloc.h>
#include "repeat_gate.h"

extern "C" {
alignas(8) uint64_t KPHeapTarget=0;
alignas(4) uint32_t KPHeapFreeCount=0, KPHeapZoneCount=0;
}
namespace {
KPRepeatGate gate;
extern "C" __attribute__((noinline)) void observed_free(void *p) {
    const auto ticket=gate.ticket();
    if(!gate.enter(ticket)){::free(p);return;}
    if(p && __atomic_load_n(&KPHeapTarget,__ATOMIC_ACQUIRE)==reinterpret_cast<uintptr_t>(p))__atomic_fetch_add(&KPHeapFreeCount,1,__ATOMIC_RELAXED);
    ::free(p);gate.leave();
}
extern "C" __attribute__((noinline)) void observed_zone_free(malloc_zone_t *zone,void *p) {
    const auto ticket=gate.ticket();
    if(!gate.enter(ticket)){::malloc_zone_free(zone,p);return;}
    if(p && __atomic_load_n(&KPHeapTarget,__ATOMIC_ACQUIRE)==reinterpret_cast<uintptr_t>(p))__atomic_fetch_add(&KPHeapZoneCount,1,__ATOMIC_RELAXED);
    ::malloc_zone_free(zone,p);gate.leave();
}
__attribute__((used,section("__DATA,__interpose"))) static const struct{const void *replacement,*original;} freePair=
    {(const void*)&observed_free,(const void*)&::free};
__attribute__((used,section("__DATA,__interpose"))) static const struct{const void *replacement,*original;} zonePair=
    {(const void*)&observed_zone_free,(const void*)&::malloc_zone_free};
}
extern "C" bool KPHeapWatchArm(void *p){
    if(!p||!gate.reserve())return false;
    __atomic_store_n(&KPHeapFreeCount,0,__ATOMIC_RELAXED);__atomic_store_n(&KPHeapZoneCount,0,__ATOMIC_RELAXED);
    __atomic_store_n(&KPHeapTarget,reinterpret_cast<uintptr_t>(p),__ATOMIC_RELEASE);
    if(gate.activate())return true;
    __atomic_store_n(&KPHeapTarget,0,__ATOMIC_RELEASE);gate.release();return false;
}
extern "C" bool KPHeapWatchDisarm(){
    if(!gate.activeOwner()||!gate.close(std::chrono::milliseconds(1000)))return false;
    __atomic_store_n(&KPHeapTarget,0,__ATOMIC_RELEASE);return gate.release();
}
extern "C" unsigned KPHeapWatchFreeHits(){return __atomic_load_n(&KPHeapFreeCount,__ATOMIC_ACQUIRE);}
extern "C" unsigned KPHeapWatchZoneHits(){return __atomic_load_n(&KPHeapZoneCount,__ATOMIC_ACQUIRE);}
