// Included inside KPCPUICBScope. Source-only native materializer, exact pin.
#include "KeplerIndirectRenderRangePins.h"
- (BOOL)enableGPUIndirectRenderRangesWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
    @synchronized(_factoryLock){
        NSData*snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
        if(_restored||!_renderEngine||!snapshot||![expected isEqual:KP_INDIRECT_RENDER_RANGE_SHA256]||![hash(snapshot)isEqual:expected])return fail(error,@"Indirect render materializer identity/scope differs");
        if(_indirectRenderRangePipeline)return YES;
        id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);id<MTLFunction>f=[library newFunctionWithName:@"materialize_render_icb_range"];
        MTLComputePipelineReflection*reflection=nil;
        id<MTLComputePipelineState>p=f?[_device newComputePipelineStateWithFunction:f options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:error]:nil;
        if(!p||p.threadExecutionWidth!=32||p.maxTotalThreadsPerThreadgroup<32||p.staticThreadgroupMemoryLength||reflection.arguments.count!=5)return fail(error,@"Indirect render native pipeline/reflection differs");
        NSArray*names=@[@"range",@"templates",@"arguments",@"witness",@"config"];
        NSUInteger sizes[]={4,4,4,16,16},align[]={4,4,4,16,256},types[]={MTLDataTypeUInt,MTLDataTypeUInt,MTLDataTypeUInt,MTLDataTypeUInt4,MTLDataTypeStruct};
        unsigned mask=0;
        for(MTLArgument*a in reflection.arguments){NSUInteger i=a.index;if(i>=5||a.type!=MTLArgumentTypeBuffer||!a.active||mask&(1u<<i)||![a.name isEqual:names[i]]||a.bufferDataSize!=sizes[i]||a.bufferAlignment!=align[i]||a.bufferDataType!=types[i]||a.access!=((i==2||i==3)?MTLArgumentAccessReadWrite:MTLArgumentAccessReadOnly))return fail(error,@"Indirect render native buffer ABI differs");mask|=1u<<i;}
        if(mask!=31)return fail(error,@"Indirect render materializer coverage differs");
        _indirectRenderRangeLibrary=library;_indirectRenderRangePipeline=p;
        [_eventRows addObject:@{@"operation":@"enable_GPU_indirect_render_ranges",@"library_SHA256":expected,@"native_pipeline":@YES,@"GPU_submissions":@0}];return YES;
    }
}
- (BOOL)enableGPURenderCommandRecordsWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
    @synchronized(_factoryLock){
        NSData *snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
        if(_restored||!_renderEngine||!snapshot||![expected isEqual:KP_RENDER_COMMAND_RECORDS_SHA256]||![hash(snapshot)isEqual:expected])
            return fail(error,@"Render record materializer identity/scope differs");
        if(_indirectRenderCommandPipeline)return YES;
        id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);
        id<MTLFunction>function=[library newFunctionWithName:@"materialize_render_command_records"];
        MTLComputePipelineReflection *reflection=nil;
        id<MTLComputePipelineState>pipeline=function?[_device newComputePipelineStateWithFunction:function
            options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:error]:nil;
        if(!pipeline||pipeline.threadExecutionWidth!=32||pipeline.maxTotalThreadsPerThreadgroup<32||
            pipeline.staticThreadgroupMemoryLength||reflection.arguments.count!=6)
            return fail(error,@"Render record native pipeline/reflection differs");
        NSArray *names=@[@"range",@"records",@"templates",@"arguments",@"witness",@"config"];
        NSUInteger sizes[]={4,32,4,4,16,16},alignments[]={4,4,4,4,16,256};
        MTLDataType types[]={MTLDataTypeUInt,MTLDataTypeStruct,MTLDataTypeUInt,MTLDataTypeUInt,MTLDataTypeUInt4,MTLDataTypeStruct};
        unsigned mask=0;
        for(MTLArgument *argument in reflection.arguments){
            NSUInteger i=argument.index;
            if(i>=6||argument.type!=MTLArgumentTypeBuffer||!argument.active||(mask&(1u<<i))||
                ![argument.name isEqual:names[i]]||argument.bufferDataSize!=sizes[i]||
                argument.bufferAlignment!=alignments[i]||argument.bufferDataType!=types[i]||
                argument.access!=((i==3||i==4)?MTLArgumentAccessReadWrite:MTLArgumentAccessReadOnly))
                return fail(error,@"Render record native buffer ABI differs");
            mask|=1u<<i;
        }
        if(mask!=63)return fail(error,@"Render record materializer coverage differs");
        _indirectRenderCommandLibrary=library;_indirectRenderCommandPipeline=pipeline;
        [_eventRows addObject:@{@"operation":@"enable_GPU_render_command_records",@"library_SHA256":expected,
            @"native_pipeline":@YES,@"GPU_submissions":@0}];
        return YES;
    }
}
- (BOOL)prepareIndirectRenderCommands:(id<MTLIndirectCommandBuffer>)buffer indirectBuffer:(id<MTLBuffer>)range indirectBufferOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
    return [self prepareRenderPlan:buffer records:nil recordOffset:0 range:range rangeOffset:offset commandBuffer:cb catalogue:nil error:error];
}
- (BOOL)prepareIndirectRenderCommands:(id<MTLIndirectCommandBuffer>)buffer commandRecords:(id<MTLBuffer>)records commandRecordsOffset:(NSUInteger)recordOffset indirectBuffer:(id<MTLBuffer>)range indirectBufferOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
    if(!records)return fail(error,@"GPU render command records are required");
    return [self prepareRenderPlan:buffer records:records recordOffset:recordOffset range:range rangeOffset:offset commandBuffer:cb catalogue:nil error:error];
}
- (BOOL)prepareRenderPlan:(id<MTLIndirectCommandBuffer>)buffer records:(id<MTLBuffer>)commandRecords recordOffset:(NSUInteger)recordOffset range:(id<MTLBuffer>)range rangeOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb catalogue:(KPRenderStateCatalogue*)catalogue error:(NSError**)error {
    id<MTLComputePipelineState>materializer=catalogue?_indirectRenderStatePipeline:commandRecords?_indirectRenderCommandPipeline:_indirectRenderRangePipeline;
    if(_restored||!_renderEngine||!materializer||![buffer isKindOfClass:KPRenderICB.class]||((KPRenderICB*)buffer).scope!=self||![range conformsToProtocol:@protocol(MTLBuffer)]||range.device!=_device||offset%4||offset>range.length||range.length-offset<8||!cb||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return fail(error,@"Indirect render preparation range/queue/scope differs");
    KPRenderICB*icb=(KPRenderICB*)buffer;KPIndirectRenderPlan*old=icb.indirectRenderPlan;
    if(old){@synchronized(old){MTLCommandBufferStatus status=old.commandBuffer.status;if(status==MTLCommandBufferStatusCompleted||status==MTLCommandBufferStatusError){old.completed=YES;old.failed=status==MTLCommandBufferStatusError;}if(!old.completed||old.failed)return fail(error,@"Prior indirect render preparation is pending or failed");}}
    if(!icb.size||icb.size>16)return fail(error,@"Indirect render slot capacity differs");
    if(commandRecords&&(![commandRecords conformsToProtocol:@protocol(MTLBuffer)]||commandRecords.device!=_device||recordOffset%(catalogue?8:4)||recordOffset>commandRecords.length||icb.size*(catalogue?KP_RENDER_STATE_COMMAND_BYTES:KP_RENDER_COMMAND_BYTES)>commandRecords.length-recordOffset))return fail(error,@"GPU render record buffer/extent differs");
    NSArray *records=nil;NSData *table=nil;
    if(catalogue){
        NSArray *sources=liveRenderCatalogueSources(catalogue,self,error);
        if(!sources||sources.firstObject!=buffer)return fail(error,@"Render catalogue source differs");
        records=catalogue.records;table=catalogue.templates;
    }else{
    NSMutableArray*mutableRecords=[NSMutableArray new];NSMutableData*mutableTable=[NSMutableData dataWithLength:icb.size*32];
    for(NSUInteger slot=0;slot<icb.size;slot++){
        KPRenderICBCommand*c=icb.commands[slot];id record=prepareIndirectRenderRecord(c,self,error);if(!record)return NO;[mutableRecords addObject:record];
        if(!c.hasDraw)continue;
        uint32_t*words=(uint32_t*)mutableTable.mutableBytes+slot*8;words[0]=(uint32_t)c.vertexCount;words[1]=(uint32_t)c.instances;
        words[2]=c.kind?0:(uint32_t)c.vertexStart;words[3]=c.kind?(uint32_t)(int32_t)c.baseVertex:(uint32_t)c.baseInstance;words[4]=c.kind?(uint32_t)c.baseInstance:0;words[5]=(uint32_t)c.kind;words[6]=1;
    }
        records=mutableRecords;table=mutableTable;
    }
    NSUInteger nativeSlots=records.count;
    KPIndirectRenderPlan*plan=[KPIndirectRenderPlan new];plan.commandBuffer=cb;plan.commandRecords=commandRecords;plan.stateCatalogue=catalogue;plan.range=range;plan.rangeOffset=offset;plan.records=[records copy];
    plan.templates=[_device newBufferWithBytes:table.bytes length:table.length options:MTLResourceStorageModeShared];
    plan.arguments=[_device newBufferWithLength:128+nativeSlots*32 options:MTLResourceStorageModePrivate];plan.witness=[_device newBufferWithLength:128+nativeSlots*16 options:MTLResourceStorageModePrivate];plan.config=[_device newBufferWithLength:256 options:MTLResourceStorageModeShared];
    if(!plan.templates||!plan.arguments||!plan.witness||!plan.config)return fail(error,@"Indirect render plan allocation failed");
    memset(plan.config.contents,0,256);uint32_t count=(uint32_t)icb.size;memcpy(plan.config.contents,&count,4);
    if(catalogue){uint32_t*words=(uint32_t*)plan.config.contents;words[1]=(uint32_t)catalogue.sources.count;words[2]=(uint32_t)nativeSlots;}
    id<MTLBuffer>initialArgs=[_device newBufferWithLength:plan.arguments.length options:MTLResourceStorageModeShared],initialWitness=[_device newBufferWithLength:plan.witness.length options:MTLResourceStorageModeShared];
    if(!initialArgs||!initialWitness)return fail(error,@"Indirect render initializer allocation failed");memset(initialArgs.contents,0xa5,initialArgs.length);memset(initialWitness.contents,0xa5,initialWitness.length);
    id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];if(!b)return fail(error,@"Indirect render initializer encoder failed; discard command buffer");
    [b copyFromBuffer:initialArgs sourceOffset:0 toBuffer:plan.arguments destinationOffset:0 size:initialArgs.length];[b copyFromBuffer:initialWitness sourceOffset:0 toBuffer:plan.witness destinationOffset:0 size:initialWitness.length];[b endEncoding];
    id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(!e)return fail(error,@"Indirect render materializer encoder failed; discard command buffer");
    [e setComputePipelineState:materializer];[e setBuffer:range offset:offset atIndex:0];NSUInteger shift=commandRecords?1:0;if(commandRecords)[e setBuffer:commandRecords offset:recordOffset atIndex:1];[e setBuffer:plan.templates offset:0 atIndex:1+shift];[e setBuffer:plan.arguments offset:64 atIndex:2+shift];[e setBuffer:plan.witness offset:64 atIndex:3+shift];[e setBuffer:plan.config offset:0 atIndex:4+shift];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
    plan.owners=@[catalogue?_indirectRenderStateLibrary:commandRecords?_indirectRenderCommandLibrary:_indirectRenderRangeLibrary,materializer,initialArgs,initialWitness];
    [cb addCompletedHandler:^(id<MTLCommandBuffer>done){@synchronized(plan){plan.failed=done.status!=MTLCommandBufferStatusCompleted;plan.completed=YES;}(void)plan.records.count;}];
    icb.indirectRenderPlan=plan;
    [_eventRows addObject:@{@"operation":@"prepare_GPU_indirect_render_range",@"slots":@(icb.size),@"native_slots":@(nativeSlots),@"GPU_state_selection":@(catalogue!=nil),@"GPU_generated_draw_records":@(commandRecords!=nil),@"record_offset":@(recordOffset),@"range_offset":@(offset),@"range_CPU_read":@NO,@"native_materializer_dispatches":@1,@"same_command_buffer_required":@YES,@"single_consumption":@YES}];return YES;
}
