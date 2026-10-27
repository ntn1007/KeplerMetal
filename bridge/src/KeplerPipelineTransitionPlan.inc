// SPDX-License-Identifier: MIT
// Private catalogue-to-table bridge. Tokens are process-local project values.
static std::atomic<uint64_t> nextRenderPipelineToken{1};
static bool kpCreatePipelineTransitionRows(NSArray*sources,KPRenderStateCatalogue*catalogue,
 id<MTLDevice>device,id<MTLBuffer>records,NSUInteger recordOffset,NSMutableData*data,
 NSMutableArray*resourceOwners,NSMutableArray*pipelineOwners,NSMutableDictionary*tokenByObject){
 const uint64_t recordStart=records.gpuAddress+recordOffset,recordEnd=recordStart+catalogue.logicalCommandCount*64;
 std::vector<KPVertexTransition::State> states;std::vector<KPPipelineTransition::PipelineToken> tokens;
 for(NSUInteger slot=0;slot<catalogue.logicalCommandCount;slot++)for(NSUInteger i=0;i<sources.count;i++){
  KPRenderICBCommand*cmd=((KPRenderICB*)sources[i]).commands[slot];if(!cmd.hasDraw)continue;
  if(!cmd.pipeline||cmd.pipeline.device!=device||!cmd.record)return false;
  uint64_t object=kpVertexObject(cmd.pipeline);NSNumber*key=@(object);NSNumber*token=tokenByObject[key];
  if(!token){uint64_t sequence=nextRenderPipelineToken.load();do{if(!sequence||sequence>UINT32_MAX)return false;}while(!nextRenderPipelineToken.compare_exchange_weak(sequence,sequence+1));
   token=@(0x4b00000000ull|sequence);tokenByObject[key]=token;[pipelineOwners addObject:cmd.pipeline];tokens.push_back({object,token.unsignedLongLongValue});}
  KPVertexTransition::State state={};state.identity=[catalogue.stateIdentifiers[i]unsignedLongLongValue];state.pipeline=object;
  if(cmd.indices&&!kpRetainRenderBuffer(cmd.indices,device,recordStart,recordEnd,resourceOwners))return false;
  state.indexObject=kpVertexObject(cmd.indices);state.indexOffset=cmd.offset;state.slot=(uint32_t)slot;state.kind=(uint32_t)cmd.kind;
  state.vertexStart=cmd.vertexStart;state.vertexCount=cmd.vertexCount;state.instances=cmd.instances;state.baseInstance=cmd.baseInstance;state.baseVertex=cmd.baseVertex;
  if(!kpVertexBindings(cmd.vertexBindings,device,true,recordStart,recordEnd,state.vertices,resourceOwners)||
     !kpVertexBindings(cmd.fragmentBindings,device,false,recordStart,recordEnd,state.fragments,resourceOwners))return false;
  states.push_back(std::move(state));
 }
 std::vector<KPPipelineTransition::Row> rows;if(!KPPipelineTransition::makeRows(states,tokens,rows))return false;
 [data appendBytes:rows.data() length:rows.size()*sizeof(rows[0])];return true;
}
