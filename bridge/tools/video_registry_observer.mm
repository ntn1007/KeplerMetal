// SPDX-License-Identifier: MIT
// Existing framework calls only; no private signature is invented or invoked.
#import <Foundation/Foundation.h>
#include "video_registry_observer.h"
#include "video_registry_layout.h"
#include <dlfcn.h>
#include <atomic>
#include <algorithm>
#include <chrono>
#include <sched.h>
#ifndef KPREG_CALIBRATION
#define KPREG_CALIBRATION 0
#endif
#ifndef KPREG_INTERPOSE
#define KPREG_INTERPOSE 1
#endif
#if KPREG_CALIBRATION && KPREG_INTERPOSE
#error Calibration must never interpose a framework call.
#endif
extern "C" {
// Address references only. Framework callers retain their actual private ABI.
void FigSignalErrorAtGM();
void FigRegistryItemCopyMatchingInfo();
void FigRegistryItemGetFactory();
void FigRegistryItemCopyDescription();
void FigRegistryItemRequiresRosetta();
void FigRegistryItemRequiresMissingRosetta();
void KPRegistryTail0();void KPRegistryTail1();void KPRegistryTail2();
void KPRegistryTail3();void KPRegistryTail4();void KPRegistryTail5();
#pragma GCC visibility push(hidden)
alignas(8) uint64_t KPRegistryActive=0,KPRegistryInflight=0,KPRegistryCount=0,KPRegistryDropped=0;
alignas(64) KPRegistryRecord KPRegistryRecords[KPREG_CAPACITY]{};
#if KPREG_CALIBRATION
void *KPRegistryO0=nullptr,*KPRegistryO1=nullptr,*KPRegistryO2=nullptr;
void *KPRegistryO3=nullptr,*KPRegistryO4=nullptr,*KPRegistryO5=nullptr;
#else
void *KPRegistryO0=(void*)&FigSignalErrorAtGM,*KPRegistryO1=(void*)&FigRegistryItemCopyMatchingInfo;
void *KPRegistryO2=(void*)&FigRegistryItemGetFactory,*KPRegistryO3=(void*)&FigRegistryItemCopyDescription;
void *KPRegistryO4=(void*)&FigRegistryItemRequiresRosetta,*KPRegistryO5=(void*)&FigRegistryItemRequiresMissingRosetta;
#endif
#pragma GCC visibility pop
}
namespace {
std::atomic<bool> targetsSet{false},begun{false};
void **slots[]={&KPRegistryO0,&KPRegistryO1,&KPRegistryO2,&KPRegistryO3,&KPRegistryO4,&KPRegistryO5};
void *tails[]={(void*)KPRegistryTail0,(void*)KPRegistryTail1,(void*)KPRegistryTail2,
    (void*)KPRegistryTail3,(void*)KPRegistryTail4,(void*)KPRegistryTail5};
const char *names[]={"FigSignalErrorAtGM","FigRegistryItemCopyMatchingInfo","FigRegistryItemGetFactory",
    "FigRegistryItemCopyDescription","FigRegistryItemRequiresRosetta","FigRegistryItemRequiresMissingRosetta"};
#if KPREG_INTERPOSE
#define KPREG_PAIR(number,symbol) \
    __attribute__((used)) static const struct{const void *new_,*old_;} pair_##number \
    __attribute__((section("__DATA,__interpose")))={(void*)&KPRegistryTail##number,(void*)&symbol};
KPREG_PAIR(0,FigSignalErrorAtGM)
KPREG_PAIR(1,FigRegistryItemCopyMatchingInfo)
KPREG_PAIR(2,FigRegistryItemGetFactory)
KPREG_PAIR(3,FigRegistryItemCopyDescription)
KPREG_PAIR(4,FigRegistryItemRequiresRosetta)
KPREG_PAIR(5,FigRegistryItemRequiresMissingRosetta)
#endif
}
extern "C" NSString *KPRegistryLibraryKind(){
    return KPREG_CALIBRATION?@"calibration":(KPREG_INTERPOSE?@"observer":@"plain");
}
extern "C" void *KPRegistryOriginal(unsigned index){return index<6?*slots[index]:nullptr;}
extern "C" void *KPRegistryTail(unsigned index){return index<6?tails[index]:nullptr;}
extern "C" bool KPRegistrySetSyntheticTarget(void *target){
#if KPREG_CALIBRATION
    if(!target||targetsSet.exchange(true)||begun.load())return false;
    for(auto slot:slots)*slot=target;return true;
#else
    (void)target;return false;
#endif
}
extern "C" bool KPRegistryEnable(bool enable){
    if(begun.exchange(true))return false;
    for(auto slot:slots)if(!*slot)return false;
    __atomic_store_n(&KPRegistryActive,enable?1:0,__ATOMIC_SEQ_CST);return true;
}
extern "C" NSDictionary *KPRegistrySnapshot(){
    __atomic_store_n(&KPRegistryActive,0,__ATOMIC_SEQ_CST);
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(__atomic_load_n(&KPRegistryInflight,__ATOMIC_ACQUIRE)&&std::chrono::steady_clock::now()<deadline)sched_yield();
    bool drained=__atomic_load_n(&KPRegistryInflight,__ATOMIC_ACQUIRE)==0;
    uint64_t count=__atomic_load_n(&KPRegistryCount,__ATOMIC_ACQUIRE),pending=0;
    NSMutableArray *events=[NSMutableArray array];uint64_t perSymbol[6]{};
    if(drained)for(uint64_t i=0;i<std::min<uint64_t>(count,KPREG_CAPACITY);i++){
        const auto &e=KPRegistryRecords[i];
        if(!__atomic_load_n(&e.ready,__ATOMIC_ACQUIRE)){pending++;continue;}
        if(e.index>=6){pending++;continue;}perSymbol[e.index]++;
        Dl_info info{};bool mapped=dladdr((void*)e.caller,&info);
        NSMutableArray *arguments=[NSMutableArray array];for(auto v:e.arguments)[arguments addObject:@(v)];
        [events addObject:@{@"ordinal":@(i),@"index":@(e.index),@"symbol":@(names[e.index]),
            @"raw_integer_arguments":arguments,@"caller_PC":@(e.caller),
            @"caller_image":@(mapped&&info.dli_fname?info.dli_fname:""),
            @"caller_offset":@(mapped&&info.dli_fbase?e.caller-(uintptr_t)info.dli_fbase:0),
            @"incoming_RAX":@(e.incomingRAX),@"incoming_R10":@(e.incomingR10),@"incoming_R11":@(e.incomingR11),
            @"arithmetic_flags":@(e.flags&0x8d5),@"entry_stack":@(e.stack)}];
    }
    NSMutableDictionary *counts=[NSMutableDictionary dictionary];for(unsigned i=0;i<6;i++)counts[@(names[i])]=@(perSymbol[i]);
    return @{@"library_kind":KPRegistryLibraryKind(),@"recorders_drained":@(drained),
        @"disabled_before_snapshot":@YES,@"calls":@(count),@"capacity":@(KPREG_CAPACITY),
        @"dropped":@(__atomic_load_n(&KPRegistryDropped,__ATOMIC_ACQUIRE)),@"pending":@(pending),
        @"counts":counts,@"events":events,@"arguments_modified":@NO,@"original_instructions_modified":@NO,
        @"opaque_argument_pointers_dereferenced":@NO,@"original_return_address_replaced":@NO,
        @"thread_ids_recorded":@NO,@"scope":@"Own process, linked observer, existing calls only"};
}
