// SPDX-License-Identifier: MIT
// CPU-only client-block contract checks; no Metal or GPU dispatch.
#import <Foundation/Foundation.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <atomic>
#include <cassert>
#include "client_state.h"
static std::atomic<bool> freed{false};
static int covers(uintptr_t,size_t) { return freed.load()?0:1; }
int main(){@autoreleasepool {
 mach_vm_address_t address=0;assert(mach_vm_allocate(mach_task_self(),&address,4096,VM_FLAGS_ANYWHERE)==KERN_SUCCESS);
 std::atomic<unsigned> calls{0},bad{0},attempts{0},duplicates{0},unapproved{0};
 std::atomic<int> before{-1},after{-1},status{-1};std::atomic<bool> authorized{false},completed{true};
 KMClientState s{(uintptr_t)address,4096,&covers,&calls,&bad,&attempts,&duplicates,&unapproved,&before,&after,&status,&authorized,&freed,&completed};
 KMClientBlock b=KMClientMakeBlock(&s);assert(b);
 b((void*)(uintptr_t)address,4096);assert(unapproved==1 && !freed && KMClientCalls()==0);
 authorized=true;b((void*)(uintptr_t)(address+1),4096);assert(bad==1 && !freed && KMClientCalls()==0);
 b((void*)(uintptr_t)address,4096);assert(freed && calls==1 && KMClientCalls()==1 && status==KERN_SUCCESS && before==1 && after==0);
 authorized=false;b((void*)(uintptr_t)address,4096);assert(duplicates==1 && calls==1 && KMClientCalls()==1 && attempts==4 && KMClientRejected()==2);
 }}
