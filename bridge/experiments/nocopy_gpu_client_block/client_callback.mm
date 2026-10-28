// SPDX-License-Identifier: MIT
// Controlled test client; do not use this block for unregistered allocations.
#import <Foundation/Foundation.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <memory>
#include "client_state.h"
#include "once_gate.h"
static std::atomic<unsigned> calls{0},rejected{0};
static std::atomic<int> status{-1};
extern "C" KMClientBlock KMClientMakeBlock(KMClientState* s) {
 if(!s || !s->expected || s->length!=4096 || !s->covers)return nil;
 auto gate=std::make_shared<kepler_witness::OnceGate>(s->expected,s->length);
 return [^(void* p,size_t n){
  (*s->attempts)++;
  if(!s->authorized->load()&&!s->freed->load()){(*s->unapproved)++;rejected++;return;}
  auto result=gate->accept((uintptr_t)p,n);
  if(result==kepler_witness::OnceResult::invalid){(*s->badArgs)++;rejected++;return;}
  if(result==kepler_witness::OnceResult::duplicate){(*s->duplicates)++;return;}
  (*s->calls)++;
  int before=s->covers((uintptr_t)p,n);s->before->store(before);
  if(before!=1||!s->gpuCompleted->load()){(*s->badArgs)++;rejected++;return;}
  calls++;int k=mach_vm_deallocate(mach_task_self(),(mach_vm_address_t)(uintptr_t)p,n);
  status.store(k);s->status->store(k);if(k==KERN_SUCCESS)s->freed->store(true);
  s->after->store(s->covers((uintptr_t)p,n));
 } copy];
}
extern "C" unsigned KMClientCalls(){return calls.load();}
extern "C" unsigned KMClientRejected(){return rejected.load();}
extern "C" int KMClientStatus(){return status.load();}
