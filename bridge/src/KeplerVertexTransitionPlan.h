// SPDX-License-Identifier: MIT
#pragma once
#include <algorithm>
#include <cstdint>
#include <map>
#include <tuple>
#include <vector>

// CPU planning data. This is not an Apple resource ID or a GPU sandbox.
// Callers must derive object identities/addresses from retained, certified
// Metal resources and keep them alive through execution.
namespace KPVertexTransition {
constexpr uint64_t AddressLimit = uint64_t(1) << 40;
constexpr size_t MaxRows = 64;
struct Binding { uint32_t index; uint64_t object, address, offset, length; };
struct State {
 uint64_t identity, pipeline, indexObject, indexOffset;
 uint32_t slot, kind;
 uint64_t vertexStart, vertexCount, instances, baseInstance;
 int64_t baseVertex;
 std::vector<Binding> vertices, fragments;
};
struct Row { uint64_t source, destination, pointer; uint32_t slot, binding; };
static_assert(sizeof(Row)==32, "Vertex transition wire ABI");

inline bool validBinding(const Binding& b) {
 return b.index<16 && b.object && b.address && b.address<AddressLimit &&
        b.length<=AddressLimit-b.address && b.offset<=b.length &&
        !(b.offset%16) && b.offset<AddressLimit-b.address;
}
inline bool orderedBindings(const std::vector<Binding>& bindings, bool checked) {
 uint32_t previous=0; bool first=true;
 for(const Binding& b:bindings) {
  if(b.index>=16 || !b.object || (!first && previous>=b.index) || (checked&&!validBinding(b)))return false;
  previous=b.index;first=false;
 }
 return true;
}
inline bool sameBindingsExcept(const std::vector<Binding>& a,const std::vector<Binding>& b,uint32_t omitted) {
 size_t i=0,j=0;
 while(true) {
  while(i<a.size()&&a[i].index==omitted)++i;
  while(j<b.size()&&b[j].index==omitted)++j;
  if(i==a.size()||j==b.size())return i==a.size()&&j==b.size();
  if(a[i].index!=b[j].index||a[i].object!=b[j].object||a[i].offset!=b[j].offset)return false;
  ++i;++j;
 }
}
inline bool matchingOtherState(const State& a,const State& b) {
 return a.slot==b.slot && a.pipeline==b.pipeline && a.kind==b.kind &&
  a.indexObject==b.indexObject && a.indexOffset==b.indexOffset &&
  a.vertexStart==b.vertexStart && a.vertexCount==b.vertexCount &&
  a.instances==b.instances && a.baseInstance==b.baseInstance && a.baseVertex==b.baseVertex &&
  sameBindingsExcept(a.fragments,b.fragments,UINT32_MAX);
}
// All-or-nothing: output is empty on malformed or ambiguous input, or overflow.
inline bool makeRows(const std::vector<State>& states,std::vector<Row>& output) {
 output.clear();if(states.empty()||states.size()>16)return false;
 std::map<std::pair<uint32_t,uint64_t>,bool> ids;
 for(const State&s:states) {
  if(!s.identity||!s.pipeline||s.slot>=16||!orderedBindings(s.vertices,true)||
     !orderedBindings(s.fragments,false)||!ids.emplace(std::make_pair(s.slot,s.identity),true).second)return false;
 }
 using Key=std::tuple<uint64_t,uint64_t,uint32_t,uint32_t>;
 std::map<Key,uint64_t> transitions;
 for(const State&src:states)for(const State&dst:states) {
  if(!matchingOtherState(src,dst))continue;
  for(const Binding&target:dst.vertices) {
   auto old=std::find_if(src.vertices.begin(),src.vertices.end(),[&](const Binding&v){return v.index==target.index;});
   if(old==src.vertices.end()||!sameBindingsExcept(src.vertices,dst.vertices,target.index))continue;
   Key key(src.identity,target.address+target.offset,src.slot,target.index);
   auto inserted=transitions.emplace(key,dst.identity);
   if(!inserted.second&&inserted.first->second!=dst.identity){output.clear();return false;}
   if(transitions.size()>MaxRows){output.clear();return false;}
  }
 }
 if(transitions.empty())return false;
 for(const auto&entry:transitions) {
  const auto&k=entry.first;output.push_back({std::get<0>(k),entry.second,std::get<1>(k),std::get<2>(k),std::get<3>(k)});
 }
 return true;
}
}
