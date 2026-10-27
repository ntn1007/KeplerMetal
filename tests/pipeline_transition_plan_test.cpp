// SPDX-License-Identifier: MIT
#include "KeplerPipelineTransitionPlan.h"
#include <cassert>
#include <iostream>
#include <vector>
using namespace KPPipelineTransition;

int main() {
 State a={};a.identity=11;a.pipeline=101;a.slot=2;a.kind=1;
 a.vertexCount=3;a.instances=1;
 a.vertices.push_back({0,300,0x10000,0,128});
 a.fragments.push_back({1,400,0x20000,16,128});
 State b=a;b.identity=12;b.pipeline=102;
 std::vector<State> states={a,b};std::vector<PipelineToken> tokens={{101,0x1001},{102,0x1002}};
 std::vector<Row> rows;
 auto rejected=[&](const std::vector<State>& s,const std::vector<PipelineToken>& t){
  rows={{1,2,3,4,5}};assert(!makeRows(s,t,rows));assert(rows.empty());
 };
 assert(makeRows(states,tokens,rows));assert(rows.size()==4);
 bool found=false;for(const auto&r:rows)if(r.source==11 && r.destination==12 && r.token==0x1002 && r.slot==2 && !r.reserved)found=true;
 assert(found);
 // A pipeline change must never silently change resource bindings or draw state.
 for(unsigned i=0;i<11;i++) {
  State changed=b;
  switch(i) {
   case 0:changed.slot++;break;case 1:changed.kind++;break;
   case 2:changed.indexObject=7;break;case 3:changed.indexOffset=8;break;
   case 4:changed.vertexCount++;break;case 5:changed.baseVertex++;break;
   case 6:changed.vertices[0].object++;break;case 7:changed.vertices[0].offset+=16;break;
   case 8:changed.fragments[0].object++;break;
   case 9:changed.vertices[0].address+=16;break;
   case 10:changed.fragments[0].length++;break;
  }
  assert(makeRows({a,changed},tokens,rows));
  for(const auto&r:rows)assert(!(r.source==a.identity && r.destination==changed.identity));
 }
 rejected(states,{{101,1},{102,1}}); // no two pipelines may share a token
 rejected(states,{{101,1},{101,2}}); // no pipeline may have two tokens
 rejected(states,{{101,0},{102,2}});
 rejected(states,{{101,1},{102,KPVertexTransition::AddressLimit}});
 rejected(states,{{101,1}});
 // A cross-product catalogue must reach the same state in either setter order.
 State c=a;c.identity=13;c.vertices[0]={0,301,0x20000,0,128};
 State d=c;d.identity=14;d.pipeline=102;
 std::vector<State> cross={a,b,c,d};std::vector<KPVertexTransition::Row> vertexRows;
 assert(makeRows(cross,tokens,rows));assert(KPVertexTransition::makeRows(cross,vertexRows));
 auto choosePipeline=[&](uint64_t source,uint64_t token){for(const auto&r:rows)if(r.source==source&&r.token==token&&r.slot==2)return r.destination;return uint64_t(0);};
 auto chooseVertex=[&](uint64_t source,uint64_t address){for(const auto&r:vertexRows)if(r.source==source&&r.pointer==address&&r.slot==2&&r.binding==0)return r.destination;return uint64_t(0);};
 assert(choosePipeline(chooseVertex(11,0x20000),0x1002)==14);
 assert(chooseVertex(choosePipeline(11,0x1002),0x20000)==14);
 assert(chooseVertex(11,0x30000)==0&&choosePipeline(11,0x9999)==0);
 assert(makeRows({a,d},tokens,rows));assert(KPVertexTransition::makeRows({a,d},vertexRows));
 assert(choosePipeline(11,0x1002)==0&&chooseVertex(11,0x20000)==0);
 State duplicate=b;duplicate.identity=a.identity;rejected({a,duplicate},tokens);
 State ambiguous=b;ambiguous.identity=13;rejected({a,b,ambiguous},tokens);
 State unaligned=b;unaligned.vertices[0].offset=1;rejected({a,unaligned},tokens);
 State unsorted=b;unsorted.vertices.push_back(unsorted.vertices[0]);rejected({a,unsorted},tokens);
 rejected({},tokens);
 std::vector<State> tooMany(17,a);rejected(tooMany,tokens);
 // All inputs are valid, but a dense 9-by-9 table exceeds the 64-row limit.
 std::vector<State> dense;std::vector<PipelineToken> denseTokens;
 for(uint64_t i=0;i<9;i++){State s=a;s.identity=100+i;s.pipeline=200+i;dense.push_back(s);denseTokens.push_back({200+i,300+i});}
 rejected(dense,denseTokens);
 std::cout << "PIPELINE_TRANSITION_PLANNER_PASS\n";
}
