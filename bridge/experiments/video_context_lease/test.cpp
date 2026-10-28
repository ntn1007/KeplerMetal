// SPDX-License-Identifier: MIT
#include "VideoContextLease.h"
#include <cassert>
#include <vector>
using namespace kepler_video;
struct Mock {int first=0, second=0, attach=0, closeContext=0, closeShared=0; Handle firstHandle=101,secondHandle=202; std::vector<int> calls;};
static int open(void *u,Handle s,uint32_t t,Handle *h){auto&m=*(Mock*)u;assert(s==42);m.calls.push_back((int)t);*h=t==3?m.firstHandle:m.secondHandle;return t==3?m.first:m.second;}
static int attach(void *u,Handle a,Handle b){auto&m=*(Mock*)u;assert(a==101&&b==202);m.calls.push_back(9);return m.attach;}
static int close(void *u,Handle h){auto&m=*(Mock*)u;m.calls.push_back((int)h);return h==101?m.closeContext:m.closeShared;}
static Backend backend(Mock&m){return Backend{&m,open,attach,close};}
int main(){
 {Mock m;Lease l(backend(m));assert(l.start(42,true));assert(l.close());assert(l.close());assert((m.calls==std::vector<int>{3,6,9,101,202}));assert(!l.start(42,true));}
 {Mock m;Lease l(backend(m));assert(l.start(42,false));assert(l.close());assert((m.calls==std::vector<int>{3,101}));}
 {Mock m;m.first=7;Lease l(backend(m));assert(!l.start(42,true));assert(l.report().context_close==0);assert((m.calls==std::vector<int>{3,101}));}
 {Mock m;m.firstHandle=0;Lease l(backend(m));assert(!l.start(42,true));assert((m.calls==std::vector<int>{3}));}
 {Mock m;m.second=8;Lease l(backend(m));assert(!l.start(42,true));assert((m.calls==std::vector<int>{3,6,101,202}));}
 {Mock m;m.secondHandle=101;Lease l(backend(m));assert(!l.start(42,true));assert((m.calls==std::vector<int>{3,6,101}));}
 {Mock m;m.attach=9;Lease l(backend(m));assert(!l.start(42,true));assert((m.calls==std::vector<int>{3,6,9,101,202}));}
 {Mock m;m.closeContext=10;Lease l(backend(m));assert(l.start(42,true));assert(!l.close());assert(!l.close());assert((m.calls==std::vector<int>{3,6,9,101,202}));}
 {Mock m;{Lease l(backend(m));assert(l.start(42,true));}assert((m.calls==std::vector<int>{3,6,9,101,202}));}
 {Mock m;Lease l(backend(m));assert(!l.start(0,true));assert(m.calls.empty());}
}
