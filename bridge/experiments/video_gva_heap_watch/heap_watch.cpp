// SPDX-License-Identifier: MIT
// CPU laboratory interposer. It never dereferences or modifies an allocation.
#include <atomic>
#include <cstdlib>
#include <malloc/malloc.h>
#include "repeat_gate.h"

namespace {
KPRepeatGate gate;
std::atomic<void *> watched{nullptr};
std::atomic<unsigned> freeHits{0}, zoneHits{0};
extern "C" __attribute__((noinline)) void observed_free(void *p) {
    const auto ticket=gate.ticket();
    if(!gate.enter(ticket)){::free(p);return;}
    if(p && watched.load(std::memory_order_acquire)==p)freeHits.fetch_add(1,std::memory_order_relaxed);
    ::free(p);gate.leave();
}
extern "C" __attribute__((noinline)) void observed_zone_free(malloc_zone_t *zone,void *p) {
    const auto ticket=gate.ticket();
    if(!gate.enter(ticket)){::malloc_zone_free(zone,p);return;}
    if(p && watched.load(std::memory_order_acquire)==p)zoneHits.fetch_add(1,std::memory_order_relaxed);
    ::malloc_zone_free(zone,p);gate.leave();
}
__attribute__((used,section("__DATA,__interpose"))) static const struct{const void *replacement,*original;} freePair=
    {(const void*)&observed_free,(const void*)&::free};
__attribute__((used,section("__DATA,__interpose"))) static const struct{const void *replacement,*original;} zonePair=
    {(const void*)&observed_zone_free,(const void*)&::malloc_zone_free};
}
extern "C" bool KPHeapWatchArm(void *p){
    if(!p||!gate.reserve())return false;
    freeHits.store(0,std::memory_order_relaxed);zoneHits.store(0,std::memory_order_relaxed);
    watched.store(p,std::memory_order_release);
    if(gate.activate())return true;
    watched.store(nullptr,std::memory_order_release);gate.release();return false;
}
extern "C" bool KPHeapWatchDisarm(){
    if(!gate.activeOwner()||!gate.close(std::chrono::milliseconds(1000)))return false;
    watched.store(nullptr,std::memory_order_release);return gate.release();
}
extern "C" unsigned KPHeapWatchFreeHits(){return freeHits.load(std::memory_order_acquire);}
extern "C" unsigned KPHeapWatchZoneHits(){return zoneHits.load(std::memory_order_acquire);}
