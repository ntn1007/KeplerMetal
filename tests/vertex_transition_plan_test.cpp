// SPDX-License-Identifier: MIT
// CPU-only contract checks for the production transition planner.
#include "KeplerVertexTransitionPlan.h"
#include <cassert>
#include <cstdio>
using namespace KPVertexTransition;

static State state(uint64_t id,Binding first,Binding second){
 State s={};s.identity=id;s.pipeline=7;s.slot=1;s.kind=0;s.vertexStart=0;
 s.vertexCount=3;s.instances=1;s.baseInstance=0;s.baseVertex=0;s.vertices={first,second};
 s.fragments={{0,99,0,256,512}};return s;
}
static uint64_t find(const std::vector<Row>&rows,uint64_t source,uint64_t pointer,uint32_t slot,uint32_t binding){
 uint64_t result=0;for(const auto&r:rows)if(r.source==source&&r.pointer==pointer&&r.slot==slot&&r.binding==binding){assert(!result);result=r.destination;}return result;
}
int main(){
 Binding a={0,11,0x10000,64,4096},b={0,12,0x20000,64,4096};
 Binding c={1,13,0x30000,128,4096},d={1,14,0x40000,128,4096};
 State one=state(101,a,c),two=state(102,b,c),three=state(103,a,d),four=state(104,b,d);
 std::vector<Row> rows;
 assert(makeRows({one,two,three,four},rows));
 assert(find(rows,101,b.address+b.offset,1,0)==102);
 assert(find(rows,102,d.address+d.offset,1,1)==104);
 assert(find(rows,101,d.address+d.offset,1,1)==103);
 assert(find(rows,103,b.address+b.offset,1,0)==104);
 assert(!find(rows,101,b.address+b.offset+16,1,0));
 assert(!find(rows,101,b.address+b.offset,0,0));
 assert(!find(rows,101,b.address+b.offset,1,1));
 State different=two;different.pipeline=8;assert(makeRows({one,different},rows));assert(!find(rows,101,b.address+b.offset,1,0));
 different=two;different.fragments[0].object++;assert(makeRows({one,different},rows));assert(!find(rows,101,b.address+b.offset,1,0));
 different=two;different.vertexCount++;assert(makeRows({one,different},rows));assert(!find(rows,101,b.address+b.offset,1,0));
 different=two;different.indexObject=99;assert(makeRows({one,different},rows));assert(!find(rows,101,b.address+b.offset,1,0));
 different=two;different.vertices[1]=d;assert(makeRows({one,different},rows));assert(!find(rows,101,b.address+b.offset,1,0));
 State alias=two;alias.identity=105;alias.vertices[0].object=20;assert(!makeRows({one,two,alias},rows));assert(rows.empty());
 assert(!makeRows({one,one},rows));assert(rows.empty());
 different=one;different.vertices[0].offset=1;assert(!makeRows({different},rows));assert(rows.empty());
 different=one;different.vertices[0].address=AddressLimit-16;different.vertices[0].length=16;different.vertices[0].offset=16;
 assert(!makeRows({different},rows));assert(rows.empty());
 std::vector<State> many;for(int i=0;i<9;i++){State x=one;x.identity=i+1;x.vertices={Binding{0,uint64_t(i+1),uint64_t(i+1)*0x10000,64,4096}};many.push_back(x);}
 assert(!makeRows(many,rows));assert(rows.empty());
 puts("VERTEX_TRANSITION_PLANNER_PASS");
}
