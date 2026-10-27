// SPDX-License-Identifier: MIT
#pragma once
#include "KeplerPipelineTransitionPlan.h"

// Host-side plan only. Object identities must come from retained Metal objects.
namespace KPFragmentTransition {
using KPVertexTransition::State;
using KPVertexTransition::Binding;
using KPVertexTransition::Row;

inline bool validFragmentBinding(const Binding& b){
 return b.index<16 && b.object && b.address && b.address<KPVertexTransition::AddressLimit &&
        b.length<=KPVertexTransition::AddressLimit-b.address && b.offset<b.length &&
        !(b.offset%256) && !((b.address+b.offset)%256);
}
inline bool sameOtherState(const State&a,const State&b){
 return a.slot==b.slot && a.pipeline==b.pipeline && a.kind==b.kind &&
  a.indexObject==b.indexObject && a.indexOffset==b.indexOffset &&
  a.vertexStart==b.vertexStart && a.vertexCount==b.vertexCount &&
  a.instances==b.instances && a.baseInstance==b.baseInstance && a.baseVertex==b.baseVertex &&
  KPPipelineTransition::sameBindings(a.vertices,b.vertices);
}
inline bool sameFragmentsExcept(const std::vector<Binding>&a,const std::vector<Binding>&b,uint32_t omitted){
 std::vector<Binding>x,y;for(const Binding&v:a)if(v.index!=omitted)x.push_back(v);for(const Binding&v:b)if(v.index!=omitted)y.push_back(v);
 return KPPipelineTransition::sameBindings(x,y);
}
// All-or-nothing. Identical addresses leading to different states are refused.
inline bool makeRows(const std::vector<State>&states,std::vector<Row>&output){
 output.clear();if(states.empty()||states.size()>16)return false;
 std::map<std::pair<uint32_t,uint64_t>,bool> ids;
 for(const State&s:states){
  if(!s.identity||!s.pipeline||s.slot>=16||!KPVertexTransition::orderedBindings(s.vertices,true)||
     !KPVertexTransition::orderedBindings(s.fragments,false)||!ids.emplace(std::make_pair(s.slot,s.identity),true).second)return false;
  for(const Binding&b:s.fragments)if(!validFragmentBinding(b))return false;
 }
 using Key=std::tuple<uint64_t,uint64_t,uint32_t,uint32_t>;std::map<Key,uint64_t>transitions;
 for(const State&src:states)for(const State&dst:states){
  if(!sameOtherState(src,dst))continue;
  for(const Binding&target:dst.fragments){
   auto old=std::find_if(src.fragments.begin(),src.fragments.end(),[&](const Binding&b){return b.index==target.index;});
   if(old==src.fragments.end()||!sameFragmentsExcept(src.fragments,dst.fragments,target.index))continue;
   Key key(src.identity,target.address+target.offset,src.slot,target.index);auto inserted=transitions.emplace(key,dst.identity);
   if((!inserted.second&&inserted.first->second!=dst.identity)||transitions.size()>KPVertexTransition::MaxRows)return false;
  }
 }
 if(transitions.empty())return false;
 for(const auto&entry:transitions){const auto&k=entry.first;output.push_back({std::get<0>(k),entry.second,std::get<1>(k),std::get<2>(k),std::get<3>(k)});}
 return true;
}
}
