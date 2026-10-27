// SPDX-License-Identifier: MIT
#include "KeplerFragmentTransitionPlan.h"
#include <algorithm>
#include <cassert>
#include <iostream>
#include <vector>
using namespace KPVertexTransition;
int main(){
 std::vector<State> states;
 for(unsigned slot=0;slot<2;slot++)for(unsigned i=0;i<8;i++){
  State s={};s.identity=100+i;s.pipeline=1+((i>>2)&1);s.indexObject=30+slot;s.indexOffset=64;s.slot=slot;s.kind=slot+1;s.vertexCount=6;s.instances=1;s.baseInstance=slot;
  s.vertices={{0,10+(i&1),0x10000+uint64_t(i&1)*0x10000,64,512},{1,20,0x50000,64,160}};
  s.fragments={{0,40+((i>>1)&1),0x60000+uint64_t((i>>1)&1)*0x10000,256,1024}};states.push_back(s);
 }
 std::vector<Row> v,f;std::vector<KPPipelineTransition::Row> p;
 std::vector<KPPipelineTransition::PipelineToken> tokens={{1,0x80000},{2,0x90000}};
 assert(KPVertexTransition::makeRows(states,v)&&v.size()==48);
 assert(KPFragmentTransition::makeRows(states,f)&&f.size()==32);
 assert(KPPipelineTransition::makeRows(states,tokens,p)&&p.size()==32);
 auto vertex=[&](uint64_t id,unsigned slot,unsigned value){for(auto&r:v)if(r.source==id&&r.slot==slot&&r.binding==0&&r.pointer==0x10040+uint64_t(value)*0x10000)return r.destination;return uint64_t(0);};
 auto fragment=[&](uint64_t id,unsigned slot,unsigned value){for(auto&r:f)if(r.source==id&&r.slot==slot&&r.binding==0&&r.pointer==0x60100+uint64_t(value)*0x10000)return r.destination;return uint64_t(0);};
 auto pipeline=[&](uint64_t id,unsigned slot,unsigned value){for(auto&r:p)if(r.source==id&&r.slot==slot&&r.token==0x80000+uint64_t(value)*0x10000)return r.destination;return uint64_t(0);};
 for(unsigned slot=0;slot<2;slot++)for(unsigned start=0;start<8;start++)for(unsigned end=0;end<8;end++){
  int order[]={0,1,2};do{uint64_t id=100+start;for(int axis:order)id=axis==0?vertex(id,slot,end&1):axis==1?fragment(id,slot,(end>>1)&1):pipeline(id,slot,(end>>2)&1);assert(id==100+end);}while(std::next_permutation(order,order+3));
 }
 std::vector<State> incomplete;for(const auto&s:states)if(s.identity!=107)incomplete.push_back(s);
 assert(KPVertexTransition::makeRows(incomplete,v));assert(KPFragmentTransition::makeRows(incomplete,f));assert(KPPipelineTransition::makeRows(incomplete,tokens,p));
 assert(!vertex(106,0,1));assert(!fragment(105,0,1));assert(!pipeline(103,0,1));
 std::cout<<"MULTI_AXIS_PLAN_PASS\n";
}
