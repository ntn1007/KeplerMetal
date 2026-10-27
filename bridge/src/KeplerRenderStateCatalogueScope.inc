// Included inside KPCPUICBScope. CPU certifies states; GPU selects predicates.
- (BOOL)enableGPURenderStateCatalogueWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
    @synchronized(_factoryLock){
        NSData *snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
        if(_restored||!_renderEngine||!snapshot||![expected isEqual:KP_RENDER_STATE_CATALOGUE_SHA256]||![hash(snapshot)isEqual:expected])
            return fail(error,@"Render state materializer identity/scope differs");
        if(_indirectRenderStatePipeline)return YES;
        id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);
        id<MTLFunction>function=[library newFunctionWithName:@"materialize_render_state_catalogue"];
        MTLComputePipelineReflection *reflection=nil;
        id<MTLComputePipelineState>pipeline=function?[_device newComputePipelineStateWithFunction:function
            options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:error]:nil;
        if(!pipeline||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32||
           pipeline.staticThreadgroupMemoryLength||reflection.arguments.count!=6)
            return fail(error,@"Render state pipeline/reflection differs");
        NSArray *names=@[@"range",@"records",@"templates",@"arguments",@"witness",@"config"];
        NSUInteger sizes[]={4,64,64,4,16,16},alignments[]={4,8,8,4,16,256};
        MTLDataType types[]={MTLDataTypeUInt,MTLDataTypeStruct,MTLDataTypeStruct,MTLDataTypeUInt,MTLDataTypeUInt4,MTLDataTypeStruct};
        unsigned mask=0;
        for(MTLArgument *argument in reflection.arguments){
            NSUInteger i=argument.index;
            if(i>=6||argument.type!=MTLArgumentTypeBuffer||!argument.active||(mask&(1u<<i))||
               ![argument.name isEqual:names[i]]||argument.bufferDataSize!=sizes[i]||
               argument.bufferAlignment!=alignments[i]||argument.bufferDataType!=types[i]||
               argument.access!=((i==3||i==4)?MTLArgumentAccessReadWrite:MTLArgumentAccessReadOnly))
                return fail(error,@"Render state native buffer ABI differs");
            mask|=1u<<i;
        }
        if(mask!=63)return fail(error,@"Render state materializer coverage differs");
        _indirectRenderStateLibrary=library;_indirectRenderStatePipeline=pipeline;
        [_eventRows addObject:@{@"operation":@"enable_GPU_render_state_catalogue",@"library_SHA256":expected,
            @"native_pipeline":@YES,@"GPU_submissions":@0}];return YES;
    }
}
- (KPRenderStateCatalogue*)newRenderStateCatalogueWithCommands:(id<MTLIndirectCommandBuffer>)commands alternatives:(NSArray*)alternatives error:(NSError**)error {
    if(_restored||!_renderEngine||![commands isKindOfClass:KPRenderICB.class]||
       ((KPRenderICB*)commands).scope!=self||![alternatives isKindOfClass:NSArray.class]||alternatives.count>=KP_RENDER_STATE_SOURCE_LIMIT){
        fail(error,@"Render catalogue sources/scope differ");return nil;
    }
    NSMutableArray *buffers=[NSMutableArray arrayWithObject:commands];[buffers addObjectsFromArray:alternatives];
    NSUInteger slots=((KPRenderICB*)commands).size,states=buffers.count;
    if(!slots||slots*states>KP_RENDER_STATE_SEQUENCE_LIMIT){fail(error,@"Render catalogue exceeds native sequence capacity");return nil;}
    NSMutableArray *sources=[NSMutableArray new];
    for(NSUInteger state=0;state<states;state++){
        id value=buffers[state];
        if(object_getClass(value)!=KPRenderICB.class||((KPRenderICB*)value).scope!=self||((KPRenderICB*)value).size!=slots){
            fail(error,@"Render catalogue source ownership/capacity differs");return nil;
        }
        for(NSUInteger prior=0;prior<state;prior++)if(buffers[prior]==value){
            fail(error,@"Render catalogue sources must be distinct objects");return nil;
        }
        KPRenderICB *buffer=value;NSMutableArray *snapshots=[NSMutableArray new];
        for(KPRenderICBCommand *command in buffer.commands){
            id record=prepareIndirectRenderRecord(command,self,error);if(!record)return nil;
            [snapshots addObject:record];
        }
        KPRenderCatalogueSource *source=[KPRenderCatalogueSource new];source.buffer=buffer;source.snapshots=snapshots;
        [sources addObject:source];
    }
    if(renderStateIdentityExhausted.load()){fail(error,@"Render state identity domain exhausted");return nil;}
    uint64_t first=nextRenderStateIdentity.fetch_add(states);
    if(first>UINT32_MAX-states+1){renderStateIdentityExhausted.store(true);fail(error,@"Render state identity domain exhausted");return nil;}
    NSMutableArray *identifiers=[NSMutableArray new],*records=[NSMutableArray new];
    for(NSUInteger state=0;state<states;state++)[identifiers addObject:@(KP_RENDER_STATE_ID_TAG|(first+state))];
    NSMutableData *table=[NSMutableData dataWithLength:slots*states*sizeof(KPRenderStateTemplate)];
    for(NSUInteger logical=0;logical<slots;logical++)for(NSUInteger state=0;state<states;state++){
        KPRenderICBCommand *command=((KPRenderICB*)buffers[state]).commands[logical];
        KPRenderCatalogueSource *source=sources[state];[records addObject:source.snapshots[logical]];
        KPRenderStateTemplate *entry=(KPRenderStateTemplate*)table.mutableBytes+logical*states+state;
        entry->state_identity=[identifiers[state]unsignedLongLongValue];entry->logical_slot=(unsigned)logical;
        if(!command.hasDraw)continue;
        entry->occupied=1;entry->kind=(unsigned)command.kind;
        entry->arguments[0]=(unsigned)command.vertexCount;entry->arguments[1]=(unsigned)command.instances;
        entry->arguments[2]=command.kind?0:(unsigned)command.vertexStart;
        entry->arguments[3]=command.kind?(unsigned)(int32_t)command.baseVertex:(unsigned)command.baseInstance;
        entry->arguments[4]=command.kind?(unsigned)command.baseInstance:0;
    }
    KPRenderStateCatalogue *catalogue=[[KPRenderStateCatalogue alloc]initOwned];
    catalogue.scope=self;catalogue.logicalCommandCount=slots;catalogue.stateIdentifiers=identifiers;
    catalogue.sources=sources;catalogue.records=records;catalogue.templates=table;
    [_eventRows addObject:@{@"operation":@"create_render_state_catalogue",@"logical_slots":@(slots),
        @"states":@(states),@"native_slots":@(slots*states),@"state_identifiers":identifiers,
        @"native_Apple_pipeline_resource_IDs":@NO,@"GPU_submissions":@0}];return catalogue;
}
- (BOOL)prepareIndirectRenderCommands:(id<MTLIndirectCommandBuffer>)buffer stateCatalogue:(KPRenderStateCatalogue*)catalogue commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)recordOffset indirectBuffer:(id<MTLBuffer>)range indirectBufferOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
    NSArray *sources=liveRenderCatalogueSources(catalogue,self,error);
    if(!sources||sources.firstObject!=buffer||!records)return fail(error,@"Render catalogue execution ICB/records differ");
    return [self prepareRenderPlan:buffer records:records recordOffset:recordOffset range:range rangeOffset:offset commandBuffer:cb catalogue:catalogue error:error];
}
