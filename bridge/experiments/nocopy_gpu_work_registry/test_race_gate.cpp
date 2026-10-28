// SPDX-License-Identifier: MIT
#include "race_gate.h"
#include <atomic>
#include <cassert>
#include <thread>
using namespace kepler_witness;
int main(){
 RaceGate a;auto x=a.register_work(),y=a.register_work();assert(x && y && x!=y);assert(a.complete(999,true)==Decision::rejected);
 assert(a.seal()==Decision::waiting && a.register_work()==0);assert(a.root()==Decision::waiting);assert(a.result(true)==Decision::waiting);
 assert(a.complete(x,true)==Decision::waiting);assert(a.complete(x,true)==Decision::duplicate);assert(a.root_returned()==Decision::waiting);assert(a.complete(y,true)==Decision::deliver);assert(a.complete(y,true)==Decision::duplicate);
 RaceGate bad;auto t=bad.register_work();assert(t);assert(bad.seal()==Decision::waiting);assert(bad.complete(t,false)==Decision::rejected);assert(bad.root()==Decision::rejected && bad.result(true)==Decision::rejected && bad.root_returned()==Decision::rejected);
 RaceGate absent;assert(absent.root()==Decision::waiting && absent.register_work()==0);assert(absent.seal()==Decision::waiting);assert(absent.result(false)==Decision::rejected);
 // Exercise dynamically sized registered sets and refuse until the last token.
 for(unsigned count=1;count<=32;count++){
  RaceGate g;uint64_t ids[32]{};for(unsigned i=0;i<count;i++){ids[i]=g.register_work();assert(ids[i]);}
  assert(g.seal()==Decision::waiting);assert(g.result(true)==Decision::waiting);assert(g.root()==Decision::waiting);assert(g.root_returned()==Decision::waiting);
  for(unsigned i=count;i>0;i--)assert(g.complete(ids[i-1],true)==(i==1?Decision::deliver:Decision::waiting));
 }
 for(unsigned i=0;i<500;i++){
  RaceGate g;auto p=g.register_work(),q=g.register_work();assert(p&&q);assert(g.seal()==Decision::waiting);std::atomic<bool> start{false};std::atomic<unsigned> delivered{0};
  auto run=[&](auto operation){while(!start.load(std::memory_order_acquire))std::this_thread::yield();if(operation()==Decision::deliver)delivered++;};
  std::thread r([&]{run([&]{return g.root();});});std::thread s([&]{run([&]{return g.root_returned();});});std::thread v([&]{run([&]{return g.result(true);});});std::thread u([&]{run([&]{return g.complete(p,true);});});std::thread w([&]{run([&]{return g.complete(q,true);});});
  start.store(true,std::memory_order_release);r.join();s.join();v.join();u.join();w.join();assert(delivered==1);
 }
}
