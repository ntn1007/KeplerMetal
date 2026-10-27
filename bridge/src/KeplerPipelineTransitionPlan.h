// SPDX-License-Identifier: MIT
#pragma once
#include "KeplerVertexTransitionPlan.h"

// Offline planning only. Tokens are owned by the caller and are not Metal IDs.
// An eventual integration must retain and validate all referenced objects.
namespace KPPipelineTransition {
using KPVertexTransition::State;
struct PipelineToken { uint64_t pipeline, token; };
struct Row { uint64_t source, destination, token; uint32_t slot, reserved; };
static_assert(sizeof(Row)==32, "Pipeline transition wire ABI");

inline bool sameBindings(const std::vector<KPVertexTransition::Binding>& a,
                         const std::vector<KPVertexTransition::Binding>& b) {
 if(a.size()!=b.size())return false;
 for(size_t i=0;i<a.size();i++)
  if(a[i].index!=b[i].index || a[i].object!=b[i].object || a[i].address!=b[i].address ||
     a[i].offset!=b[i].offset || a[i].length!=b[i].length)return false;
 return true;
}
inline bool sameExceptPipeline(const State& a,const State& b) {
 return a.slot==b.slot && a.kind==b.kind && a.indexObject==b.indexObject &&
  a.indexOffset==b.indexOffset && a.vertexStart==b.vertexStart &&
  a.vertexCount==b.vertexCount && a.instances==b.instances &&
  a.baseInstance==b.baseInstance && a.baseVertex==b.baseVertex &&
  sameBindings(a.vertices,b.vertices) && sameBindings(a.fragments,b.fragments);
}

// Reject ambiguous mappings and malformed input; never return partial rows.
inline bool makeRows(const std::vector<State>& states,const std::vector<PipelineToken>& tokens,
                     std::vector<Row>& output) {
 output.clear();
 if(states.empty() || states.size()>16 || tokens.empty() || tokens.size()>16)return false;
 std::map<uint64_t,uint64_t> byPipeline,byToken;
 for(const auto& t:tokens) {
  if(!t.pipeline || !t.token || t.token>=KPVertexTransition::AddressLimit ||
     !byPipeline.emplace(t.pipeline,t.token).second || !byToken.emplace(t.token,t.pipeline).second)return false;
 }
 std::map<std::pair<uint32_t,uint64_t>,bool> identities;
 for(const State& s:states) {
  if(!s.identity || !s.pipeline || s.slot>=16 || !byPipeline.count(s.pipeline) ||
     !KPVertexTransition::orderedBindings(s.vertices,true) ||
     !KPVertexTransition::orderedBindings(s.fragments,false) ||
     !identities.emplace(std::make_pair(s.slot,s.identity),true).second)return false;
 }
 using Key=std::tuple<uint64_t,uint64_t,uint32_t>;
 std::map<Key,uint64_t> transitions;
 for(const State& src:states)for(const State& dst:states) {
  if(!sameExceptPipeline(src,dst))continue;
  Key key(src.identity,byPipeline.at(dst.pipeline),src.slot);
  auto inserted=transitions.emplace(key,dst.identity);
  if((!inserted.second && inserted.first->second!=dst.identity) || transitions.size()>KPVertexTransition::MaxRows)return false;
 }
 if(transitions.empty())return false;
 for(const auto& entry:transitions) {
  const auto& key=entry.first;
  output.push_back({std::get<0>(key),entry.second,std::get<1>(key),std::get<2>(key),0});
 }
 return true;
}
}
