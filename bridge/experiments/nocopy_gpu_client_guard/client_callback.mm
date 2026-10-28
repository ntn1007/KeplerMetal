// SPDX-License-Identifier: MIT
// Independent test client: knows its allocation, not the lab's GPU or gate state.
#import <Foundation/Foundation.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <atomic>
#include <cstdint>
#include "client_state.h"
static std::atomic<unsigned> calls{0},rejected{0};
static std::atomic<int> status{-1};
extern "C" KMClientBlock KMClientMakeBlock(void* allocation,size_t length) {
 if(!allocation || length!=4096)return nil;
 return [^(void* p,size_t n){
  calls++;
  if(p!=allocation||n!=length){rejected++;return;}
  status.store(mach_vm_deallocate(mach_task_self(),(mach_vm_address_t)(uintptr_t)p,n));
 } copy];
}
extern "C" unsigned KMClientCalls(){return calls.load();}
extern "C" unsigned KMClientRejected(){return rejected.load();}
extern "C" int KMClientStatus(){return status.load();}
