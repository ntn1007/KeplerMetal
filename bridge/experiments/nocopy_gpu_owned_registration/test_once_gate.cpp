// SPDX-License-Identifier: MIT
#include "once_gate.h"
#include <atomic>
#include <cassert>
#include <thread>
#include <vector>
using namespace kepler_witness;
int main(){
 OnceGate g(0x1000,4096);assert(g.accept(0x1001,4096)==OnceResult::invalid);assert(g.accept(0x1000,4095)==OnceResult::invalid);assert(g.accept(0x1000,4096)==OnceResult::accepted);assert(g.accept(0x1000,4096)==OnceResult::duplicate);
 OnceGate bad(0,4096);assert(bad.accept(0,4096)==OnceResult::invalid);
 for(unsigned i=0;i<300;i++){
  OnceGate race(0x2000,4096);std::atomic<bool> start{false};std::atomic<unsigned> win{0},dup{0};std::vector<std::thread> threads;
  for(unsigned j=0;j<8;j++)threads.emplace_back([&]{while(!start.load(std::memory_order_acquire))std::this_thread::yield();auto v=race.accept(0x2000,4096);if(v==OnceResult::accepted)win++;else if(v==OnceResult::duplicate)dup++;else assert(false);});
  start.store(true,std::memory_order_release);for(auto &t:threads)t.join();assert(win==1&&dup==7);
 }
}
