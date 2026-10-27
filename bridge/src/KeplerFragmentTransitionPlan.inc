// SPDX-License-Identifier: MIT
// Private catalogue-to-table bridge; all owners originate in certified states.
static bool kpCreateFragmentTransitionRows(NSArray*sources,KPRenderStateCatalogue*catalogue,
 id<MTLDevice>device,id<MTLBuffer>records,NSUInteger recordOffset,NSMutableData*data,NSMutableArray*owners){
 const uint64_t recordStart=records.gpuAddress+recordOffset,recordEnd=recordStart+catalogue.logicalCommandCount*64;
 std::vector<KPVertexTransition::State>states;
 for(NSUInteger slot=0;slot<catalogue.logicalCommandCount;slot++)for(NSUInteger i=0;i<sources.count;i++){
  KPRenderICBCommand*cmd=((KPRenderICB*)sources[i]).commands[slot];if(!cmd.hasDraw)continue;
  if(!cmd.pipeline||cmd.pipeline.device!=device||!cmd.record)return false;
  KPVertexTransition::State state={};state.identity=[catalogue.stateIdentifiers[i]unsignedLongLongValue];state.pipeline=kpVertexObject(cmd.pipeline);
  if(cmd.indices&&!kpRetainRenderBuffer(cmd.indices,device,recordStart,recordEnd,owners))return false;
  state.indexObject=kpVertexObject(cmd.indices);state.indexOffset=cmd.offset;state.slot=(uint32_t)slot;state.kind=(uint32_t)cmd.kind;
  state.vertexStart=cmd.vertexStart;state.vertexCount=cmd.vertexCount;state.instances=cmd.instances;state.baseInstance=cmd.baseInstance;state.baseVertex=cmd.baseVertex;
  if(!kpVertexBindings(cmd.vertexBindings,device,true,recordStart,recordEnd,state.vertices,owners)||
     !kpVertexBindings(cmd.fragmentBindings,device,false,recordStart,recordEnd,state.fragments,owners))return false;
  states.push_back(std::move(state));
 }
 std::vector<KPFragmentTransition::Row>rows;if(!KPFragmentTransition::makeRows(states,rows))return false;
 [data appendBytes:rows.data() length:rows.size()*sizeof(rows[0])];return true;
}
