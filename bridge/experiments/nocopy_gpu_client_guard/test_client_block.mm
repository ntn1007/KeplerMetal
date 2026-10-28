// SPDX-License-Identifier: MIT
// CPU-only guard and independent client block contract; no Metal or GPU dispatch.
#import <Foundation/Foundation.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <cassert>
#include "client_guard.h"
static std::atomic<bool> freed{false};
static int covers(uintptr_t,size_t) { return KMClientStatus()==KERN_SUCCESS?0:1; }
int main(){@autoreleasepool {
 // Incomplete GPU work must fail closed and cannot be retried through this guard.
 mach_vm_address_t unfinished=0;assert(mach_vm_allocate(mach_task_self(),&unfinished,4096,VM_FLAGS_ANYWHERE)==KERN_SUCCESS);
 std::atomic<unsigned> fcalls{0},fbad{0},fattempts{0},fduplicates{0},funapproved{0};
 std::atomic<int> fbefore{-1},fafter{-1};std::atomic<bool> fauth{true},ffreed{false},fcompleted{false};
 KMGuardState fs{(uintptr_t)unfinished,4096,&covers,&fcalls,&fbad,&fattempts,&fduplicates,&funapproved,&fbefore,&fafter,&fauth,&ffreed,&fcompleted};
 KMClientBlock client0=KMClientMakeBlock((void*)(uintptr_t)unfinished,4096);KMClientBlock guard0=KMMakeGuard(client0,&fs);assert(guard0);
 guard0((void*)(uintptr_t)unfinished,4096);assert(fbad==1 && !ffreed && KMClientCalls()==0);
 fcompleted=true;guard0((void*)(uintptr_t)unfinished,4096);assert(fduplicates==1 && KMClientCalls()==0);
 guard0=nil;client0=nil;assert(mach_vm_deallocate(mach_task_self(),unfinished,4096)==KERN_SUCCESS);
 mach_vm_address_t address=0;assert(mach_vm_allocate(mach_task_self(),&address,4096,VM_FLAGS_ANYWHERE)==KERN_SUCCESS);
 std::atomic<unsigned> calls{0},bad{0},attempts{0},duplicates{0},unapproved{0};
 std::atomic<int> before{-1},after{-1};std::atomic<bool> authorized{false},completed{true};
 KMGuardState s{(uintptr_t)address,4096,&covers,&calls,&bad,&attempts,&duplicates,&unapproved,&before,&after,&authorized,&freed,&completed};
 __weak id weakClient=nil;KMClientBlock wrapper=nil;
 @autoreleasepool {KMClientBlock client=KMClientMakeBlock((void*)(uintptr_t)address,4096);assert(client);weakClient=client;wrapper=KMMakeGuard(client,&s);assert(wrapper && wrapper!=client);client=nil;}
 assert(weakClient!=nil);
 wrapper((void*)(uintptr_t)address,4096);assert(unapproved==1 && !freed && KMClientCalls()==0);
 authorized=true;wrapper((void*)(uintptr_t)(address+1),4096);assert(bad==1 && !freed && KMClientCalls()==0);
 wrapper((void*)(uintptr_t)address,4096);assert(freed && calls==1 && KMClientCalls()==1 && KMClientStatus()==KERN_SUCCESS && before==1 && after==0);
 authorized=false;wrapper((void*)(uintptr_t)address,4096);assert(duplicates==1 && calls==1 && KMClientCalls()==1 && attempts==4 && KMClientRejected()==0);
 wrapper=nil;assert(weakClient==nil);
 }}
