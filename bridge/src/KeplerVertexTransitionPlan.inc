// SPDX-License-Identifier: MIT
// Private namespace, after liveRenderCatalogueSources. Rows are derived solely
// from retained Metal objects and snapshots; no caller-supplied GPU addresses.
static uint64_t kpVertexObject(id value){return (uint64_t)(uintptr_t)(__bridge const void*)value;}
static bool kpRetainRenderBuffer(id<MTLBuffer>buffer,id<MTLDevice>device,uint64_t recordStart,uint64_t recordEnd,NSMutableArray*owners){
 if(!buffer||buffer.device!=device)return false;
 uint64_t address=buffer.gpuAddress,length=buffer.length;
 if(!address||address>=KPVertexTransition::AddressLimit||length>KPVertexTransition::AddressLimit-address)return false;
 if(length&&address<recordEnd&&recordStart<address+length)return false;
 [owners addObject:buffer];return true;
}
static bool kpVertexBindings(NSDictionary *bindings,id<MTLDevice>device,bool vertex,
 uint64_t recordStart,uint64_t recordEnd,std::vector<KPVertexTransition::Binding>&out,NSMutableArray*owners){
 for(NSNumber*key in [[bindings allKeys]sortedArrayUsingSelector:@selector(compare:)]){
  NSDictionary*entry=bindings[key];id<MTLBuffer>buffer=entry[@"buffer"];NSNumber*off=entry[@"offset"];
  if(![key isKindOfClass:NSNumber.class]||key.unsignedLongLongValue>=16||
     !buffer||buffer.device!=device||![off isKindOfClass:NSNumber.class])return false;
  uint64_t address=buffer.gpuAddress,offset=off.unsignedLongLongValue,length=buffer.length;
  KPVertexTransition::Binding binding={(uint32_t)key.unsignedIntValue,kpVertexObject(buffer),address,offset,length};
  if(offset>length||!kpRetainRenderBuffer(buffer,device,recordStart,recordEnd,owners)||
     (vertex&&!KPVertexTransition::validBinding(binding)))return false;
  out.push_back(binding);
 }
 return true;
}
static bool kpCreateVertexTransitionRows(NSArray*sources,KPRenderStateCatalogue*catalogue,
 id<MTLDevice>device,id<MTLBuffer>records,NSUInteger recordOffset,NSMutableData*data,NSMutableArray*owners){
 const uint64_t recordStart=records.gpuAddress+recordOffset,recordEnd=recordStart+catalogue.logicalCommandCount*64;
 std::vector<KPVertexTransition::State> states;
 for(NSUInteger slot=0;slot<catalogue.logicalCommandCount;slot++)for(NSUInteger i=0;i<sources.count;i++){
  KPRenderICBCommand*cmd=((KPRenderICB*)sources[i]).commands[slot];
  if(!cmd.hasDraw)continue;
  if(!cmd.pipeline||!cmd.record)return false;
  KPVertexTransition::State state={};
  state.identity=[catalogue.stateIdentifiers[i]unsignedLongLongValue];state.pipeline=kpVertexObject(cmd.pipeline);
  if(cmd.indices&&!kpRetainRenderBuffer(cmd.indices,device,recordStart,recordEnd,owners))return false;
  state.indexObject=kpVertexObject(cmd.indices);state.indexOffset=cmd.offset;state.slot=(uint32_t)slot;state.kind=(uint32_t)cmd.kind;
  state.vertexStart=cmd.vertexStart;state.vertexCount=cmd.vertexCount;state.instances=cmd.instances;
  state.baseInstance=cmd.baseInstance;state.baseVertex=cmd.baseVertex;
  if(!kpVertexBindings(cmd.vertexBindings,device,true,recordStart,recordEnd,state.vertices,owners)||
     !kpVertexBindings(cmd.fragmentBindings,device,false,recordStart,recordEnd,state.fragments,owners))return false;
  states.push_back(std::move(state));
 }
 std::vector<KPVertexTransition::Row> rows;
 if(!KPVertexTransition::makeRows(states,rows))return false;
 [data appendBytes:rows.data() length:rows.size()*sizeof(rows[0])];return true;
}
