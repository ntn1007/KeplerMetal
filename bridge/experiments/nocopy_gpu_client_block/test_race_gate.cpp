// SPDX-License-Identifier: MIT
#include "race_gate.h"
#include <atomic>
#include <cassert>
#include <thread>
using namespace kepler_witness;
int main(){
 RaceGate a;assert(a.root()==Decision::waiting);assert(a.result(true)==Decision::waiting);assert(a.root_returned()==Decision::deliver);assert(a.root()==Decision::duplicate);assert(a.result(true)==Decision::duplicate);assert(a.root_returned()==Decision::duplicate);
 RaceGate b;assert(b.result(true)==Decision::waiting);assert(b.root_returned()==Decision::waiting);assert(b.root()==Decision::deliver);
 RaceGate c;assert(c.result(false)==Decision::rejected);assert(c.root()==Decision::rejected);assert(c.root_returned()==Decision::rejected);
 for(unsigned i=0;i<500;i++){
  RaceGate g;std::atomic<bool> start{false};std::atomic<unsigned> delivered{0};
  std::thread x([&]{while(!start.load(std::memory_order_acquire))std::this_thread::yield();if(g.root()==Decision::deliver)delivered++;});
  std::thread y([&]{while(!start.load(std::memory_order_acquire))std::this_thread::yield();if(g.result(true)==Decision::deliver)delivered++;});
  std::thread z([&]{while(!start.load(std::memory_order_acquire))std::this_thread::yield();if(g.root_returned()==Decision::deliver)delivered++;});
  start.store(true,std::memory_order_release);x.join();y.join();z.join();assert(delivered==1);
 }
}
