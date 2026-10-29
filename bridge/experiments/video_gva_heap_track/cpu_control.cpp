// SPDX-License-Identifier: MIT
#include <cstdlib>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <malloc/malloc.h>
extern "C" bool KPHeapWatchArm(void *);
extern "C" bool KPHeapWatchDisarm();
extern "C" unsigned KPHeapWatchFreeHits();
extern "C" unsigned KPHeapWatchZoneHits();
extern "C" void KPForeignFree(void *);
extern "C" void KPTraceHeapTarget(void *);
int main(int argc,char **argv){
    if(argc!=2||(std::strcmp(argv[1],"match")&&std::strcmp(argv[1],"different")))return 1;
    bool match=!std::strcmp(argv[1],"match");
    void *target=malloc_type_malloc(1128,0),*other=malloc_type_malloc(1128,0);
    if(!target||!other||!KPHeapWatchArm(reinterpret_cast<void*>(1)))return 2;
    KPTraceHeapTarget(match?target:other);
    KPForeignFree(target);
    unsigned first=KPHeapWatchFreeHits();
    KPForeignFree(other);
    unsigned second=KPHeapWatchFreeHits();
    if(!KPHeapWatchDisarm()||KPHeapWatchZoneHits()!=0)return 3;
    if(first!=(match?1u:0u)||second!=1)return 4;
    std::puts(match?"PASS matched free then unrelated free":"PASS unrelated free then matched free");return 0;
}
