// SPDX-License-Identifier: MIT
#include <cstdlib>
#include <cstdio>
#include <atomic>
#include <thread>
#include <malloc/malloc.h>
extern "C" bool KPHeapWatchArm(void *);
extern "C" bool KPHeapWatchDisarm();
extern "C" unsigned KPHeapWatchFreeHits();
extern "C" unsigned KPHeapWatchZoneHits();
extern "C" void KPForeignFree(void *);
extern "C" void KPForeignZoneFree(malloc_zone_t *,void *);

int main(){
    if(KPHeapWatchArm(nullptr))return 1;
    void *p=malloc_type_malloc(1128,0);void *other=malloc_type_malloc(1128,0);
    if(!p||!other||!KPHeapWatchArm(p)||KPHeapWatchArm(other))return 2;
    std::atomic<bool> denied{false},disarmDenied{false};
    std::thread contender([&]{denied=!KPHeapWatchArm(other);disarmDenied=!KPHeapWatchDisarm();});
    contender.join();if(!denied||!disarmDenied)return 8;
    KPForeignFree(other);
    if(KPHeapWatchFreeHits()!=0||KPHeapWatchZoneHits()!=0)return 3;
    KPForeignFree(p);
    if(KPHeapWatchFreeHits()!=1)return 4;
    if(!KPHeapWatchDisarm())return 9;
    auto *zone=malloc_default_zone();p=malloc_zone_malloc(zone,1128);if(!p||!KPHeapWatchArm(p))return 5;
    KPForeignZoneFree(zone,p);
    if(KPHeapWatchZoneHits()!=1)return 6;
    if(!KPHeapWatchDisarm())return 9;
    p=malloc_type_malloc(1128,0);if(!p)return 7;KPForeignFree(p);
    std::puts("PASS cross-image free and zone-free watched-pointer controls");return 0;
}
