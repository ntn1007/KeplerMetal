// SPDX-License-Identifier: MIT
#include "KeplerFragmentTransitionPlan.h"
#include <cassert>
#include <iostream>
using namespace KPFragmentTransition;

int main(){
 State a={};a.identity=1;a.pipeline=9;a.slot=0;a.vertexCount=3;a.instances=1;
 a.vertices.push_back({0,101,0x10000,0,512});a.fragments.push_back({0,201,0x20000,256,1024});
 State b=a;b.identity=2;b.fragments[0]={0,202,0x30000,256,1024};
 std::vector<Row>rows;assert(KPFragmentTransition::makeRows({a,b},rows));assert(rows.size()==4);
 auto select=[&](uint64_t id,uint64_t p,uint32_t slot,uint32_t binding){for(const auto&r:rows)if(r.source==id&&r.pointer==p&&r.slot==slot&&r.binding==binding)return r.destination;return uint64_t(0);};
 assert(select(1,0x30100,0,0)==2&&select(2,0x20100,0,0)==1);
 assert(!select(1,0x30101,0,0)&&!select(1,0x30100,1,0)&&!select(1,0x30100,0,1));
 for(unsigned i=0;i<8;i++){
  State c=b;switch(i){case 0:c.pipeline++;break;case 1:c.slot++;break;case 2:c.kind++;break;
   case 3:c.indexObject++;break;case 4:c.vertexCount++;break;case 5:c.baseInstance++;break;
   case 6:c.vertices[0].object++;break;case 7:c.vertices[0].length++;break;}
  assert(KPFragmentTransition::makeRows({a,c},rows));for(const auto&r:rows)assert(!(r.source==a.identity&&r.destination==c.identity));
 }
 auto refused=[&](std::vector<State>states){rows={{1,2,3,4,5}};assert(!KPFragmentTransition::makeRows(states,rows));assert(rows.empty());};
 State c=b;c.fragments[0].offset=1;refused({a,c});c=b;c.fragments[0].address++;refused({a,c});
 c=b;c.fragments[0].offset=1024;refused({a,c});c=b;c.identity=1;refused({a,c});
 c=b;c.identity=3;c.fragments[0].object=203;refused({a,b,c});
 std::vector<State>dense;for(uint64_t i=0;i<9;i++){State x=a;x.identity=i+1;x.fragments[0].object=300+i;x.fragments[0].address=0x40000+i*0x10000;dense.push_back(x);}refused(dense);
 std::cout<<"FRAGMENT_TRANSITION_PLANNER_PASS\n";
}
