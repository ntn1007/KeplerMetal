// SPDX-License-Identifier: MIT
// Experimental gate for one owned allocation and explicitly tracked GPU work.
#pragma once
#include <atomic>
#include <memory>
#include "client_state.h"
#include "once_gate.h"
struct KMGuardState {
 uintptr_t expected; size_t length; int (*covers)(uintptr_t,size_t);
 std::atomic<unsigned> *calls,*badArgs,*attempts,*duplicates,*unapproved;
 std::atomic<int> *before,*after;
 std::atomic<bool> *authorized,*freed,*gpuCompleted;
};
static KMClientBlock KMMakeGuard(KMClientBlock client,KMGuardState* s) {
 if(!client || !s || !s->expected || s->length!=4096 || !s->covers)return nil;
 auto gate=std::make_shared<kepler_witness::OnceGate>(s->expected,s->length);
 return [^(void* p,size_t n){
  (*s->attempts)++;
  if(!s->authorized->load()&&!s->freed->load()){(*s->unapproved)++;return;}
  auto r=gate->accept((uintptr_t)p,n);
  if(r==kepler_witness::OnceResult::invalid){(*s->badArgs)++;return;}
  if(r==kepler_witness::OnceResult::duplicate){(*s->duplicates)++;return;}
  (*s->calls)++;
  int before=s->covers((uintptr_t)p,n);s->before->store(before);
  if(before!=1||!s->gpuCompleted->load()){(*s->badArgs)++;return;}
  client(p,n);int after=s->covers((uintptr_t)p,n);s->after->store(after);
  if(after==0)s->freed->store(true);
 } copy];
}
