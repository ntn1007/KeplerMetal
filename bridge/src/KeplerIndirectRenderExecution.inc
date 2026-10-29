// Included in the scope's private namespace. Never reads GPU range contents.
id prepareIndirectRenderRecord(KPRenderICBCommand*c,KPCPUICBScope*scope,NSError**error){
    if(c.owner.inheritPipelineState){fail(error,@"GPU indirect render preparation cannot capture inherited pipelines");return nil;}
    if([[scope.renderEngine profileForPipeline:c.pipeline][@"apple_explicit_buffers"]boolValue]){fail(error,@"GPU indirect render preparation for explicit Apple buffers is not qualified");return nil;}
    if(!c.hasDraw)return NSNull.null;
    NSDictionary*p=[scope.renderEngine profileForPipeline:c.pipeline];if(!p){fail(error,@"Indirect render pipeline is not registered");return nil;}
    BOOL legacy=[p[@"legacy"]boolValue];
    BOOL valid=c.kind&&!legacy?
        [scope.renderEngine validateIndexedVertexBindings:c.vertexBindings pipeline:c.pipeline indexCount:c.vertexCount indexBuffer:c.indices indexOffset:c.offset kind:c.kind instances:c.instances baseVertex:c.baseVertex baseInstance:c.baseInstance error:error]:
        [scope.renderEngine validateVertexBindings:c.vertexBindings pipeline:c.pipeline vertexStart:c.vertexStart vertexCount:c.vertexCount instances:c.instances baseInstance:c.baseInstance error:error];
    if(!valid||(legacy&&c.baseVertex)||![scope.renderEngine validateFragmentBindings:c.fragmentBindings pipeline:c.pipeline error:error])return nil;
    if(!c.record){
        if(legacy)c.record=[scope.renderEngine prepareInheritedDrawKind:c.kind indexBuffer:c.indices offset:c.offset instances:c.instances error:error];
        else if(c.kind)c.record=c.fragmentBindings.count?
            [scope.renderEngine prepareIndexedFragmentPipeline:c.pipeline vertexBindings:c.vertexBindings fragmentBindings:c.fragmentBindings indexCount:c.vertexCount indexBuffer:c.indices indexOffset:c.offset kind:c.kind instances:c.instances baseVertex:c.baseVertex baseInstance:c.baseInstance error:error]:
            [scope.renderEngine prepareIndexedVertexPipeline:c.pipeline bindings:c.vertexBindings indexCount:c.vertexCount indexBuffer:c.indices indexOffset:c.offset kind:c.kind instances:c.instances baseVertex:c.baseVertex baseInstance:c.baseInstance error:error];
        else c.record=c.fragmentBindings.count?
            [scope.renderEngine prepareFragmentDrawPipeline:c.pipeline vertexBindings:c.vertexBindings fragmentBindings:c.fragmentBindings vertexStart:c.vertexStart vertexCount:c.vertexCount instances:c.instances baseInstance:c.baseInstance error:error]:
            [scope.renderEngine prepareVertexDrawPipeline:c.pipeline bindings:c.vertexBindings vertexStart:c.vertexStart vertexCount:c.vertexCount instances:c.instances baseInstance:c.baseInstance error:error];
    }
    return c.record;
}

#include "KeplerRenderStateCatalogueRecords.inc"

void executeIndirectRenderICB(id self,SEL selector,id buffer,id range,NSUInteger offset){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);KPCPUICBScope*scope=link.scope;
    if(!scope||scope.restored||!scope.renderEngine||![buffer isKindOfClass:KPRenderICB.class]||((KPRenderICB*)buffer).scope!=scope||!link.renderTarget)reject(@"Indirect render ICB/encoder scope differs");
    KPRenderICB*icb=buffer;KPIndirectRenderPlan*plan=icb.indirectRenderPlan;
    Ivar cv=class_getInstanceVariable(object_getClass(self),"_commandBuffer");
    if(!cv||ivar_getOffset(cv)!=32)reject(@"Indirect render command buffer owner differs");
    id<MTLCommandBuffer>cb=object_getIvar(self,cv);
    if(!plan||plan.commandBuffer!=cb||plan.range!=range||plan.rangeOffset!=offset||cb.commandQueue!=scope.queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)reject(@"Indirect render execution requires its prepared range on the same recording buffer");
    NSMutableArray *encodedCommands=[NSMutableArray new];
    @synchronized(plan){
        if(plan.consumed||plan.completed||plan.failed)reject(@"Indirect render preparation already consumed/terminal");
        NSArray *sources=@[icb];
        if(plan.stateCatalogue){
            NSError *error=nil;sources=liveRenderCatalogueSources(plan.stateCatalogue,scope,&error);
            if(!sources||sources.firstObject!=icb)reject(error.localizedDescription?:@"Render catalogue execution source differs");
        }else if(plan.records.count!=icb.commands.count)reject(@"Indirect render snapshot size differs");
        for(NSUInteger state=0;state<sources.count;state++){
            KPRenderICB *source=sources[state];
            NSArray *snapshot=plan.stateCatalogue?plan.stateCatalogue.sources[state].snapshots:plan.records;
            for(NSUInteger i=0;i<source.commands.count;i++){
                KPRenderICBCommand *c=source.commands[i];id saved=snapshot[i];
                if(saved==NSNull.null){if(c.hasDraw)reject(@"Indirect render empty slot changed");continue;}
                if(!c.hasDraw||c.record!=saved)reject(@"Indirect render command changed after preparation");
                NSDictionary *p=[scope.renderEngine profileForPipeline:c.pipeline];
                if(!p||([p[@"target_width"]unsignedIntegerValue]?:64)!=link.renderTarget.width||([p[@"target_height"]unsignedIntegerValue]?:48)!=link.renderTarget.height||([p[@"color_format"]unsignedIntegerValue]?:MTLPixelFormatRGBA32Float)!=link.renderTarget.pixelFormat||[p[@"depth_format"]unsignedIntegerValue]!=link.renderPass.depthAttachment.texture.pixelFormat||[p[@"stencil_format"]unsignedIntegerValue]!=link.renderPass.stencilAttachment.texture.pixelFormat)reject(@"Indirect render pass differs from registered pipeline");
                [encodedCommands addObject:c];
            }
        }
        plan.consumed=YES;
    }
    NSMutableIndexSet*vertex=[NSMutableIndexSet new],*fragment=[NSMutableIndexSet new];
    for(KPRenderICBCommand*c in encodedCommands){for(NSNumber*i in c.vertexBindings)[vertex addIndex:i.unsignedIntegerValue];for(NSNumber*i in c.fragmentBindings)[fragment addIndex:i.unsignedIntegerValue];}
    NSError*error=nil;NSDictionary*proof=nil;BOOL ok=NO;link.encodingRenderICB=YES;
    @try{ok=[scope.renderEngine encodeGPUIndirectRecords:plan.records arguments:plan.arguments encoder:self target:link.renderTarget evidence:&proof error:&error];}
    @finally{
        if(link.callerRenderPipeline)[self setRenderPipelineState:link.callerRenderPipeline];
        for(NSUInteger i=vertex.firstIndex;i!=NSNotFound;i=[vertex indexGreaterThanIndex:i]){NSDictionary*b=link.callerVertexBindings[@(i)];if(b[@"bytes"]){NSData*d=b[@"bytes"];[self setVertexBytes:d.bytes length:d.length atIndex:i];}else[self setVertexBuffer:b[@"buffer"]offset:[b[@"offset"]unsignedIntegerValue]atIndex:i];}
        for(NSUInteger i=fragment.firstIndex;i!=NSNotFound;i=[fragment indexGreaterThanIndex:i]){NSDictionary*b=link.callerFragmentBindings[@(i)];if(b[@"bytes"]){NSData*d=b[@"bytes"];[self setFragmentBytes:d.bytes length:d.length atIndex:i];}else[self setFragmentBuffer:b[@"buffer"]offset:[b[@"offset"]unsignedIntegerValue]atIndex:i];}
        link.encodingRenderICB=NO;
    }
    if(!ok)reject([error.localizedDescription?:@"Indirect render encoding failed" stringByAppendingString:@"; discard command buffer"]);
    [scope.eventRows addObject:@{@"operation":@"execute_GPU_indirect_render_range",@"slot_capacity":@(icb.size),@"native_slot_capacity":@(plan.records.count),@"GPU_state_selection":@(plan.stateCatalogue!=nil),@"state_count":@(plan.stateCatalogue?plan.stateCatalogue.sources.count:1),@"selection_CPU_read":@NO,@"state_selection_method":plan.stateCatalogue?@"native_indirect_draw_predicates":@"fixed_slot_state",@"GPU_generated_draw_records":@(plan.commandRecords!=nil),@"record_CPU_read":@NO,@"range_offset":@(offset),@"range_CPU_read":@NO,@"caller_pipeline_restored":@(link.callerRenderPipeline!=nil),@"caller_vertex_slots_restored":@(vertex.count),@"caller_fragment_slots_restored":@(fragment.count),@"evidence":proof?:@{}}];
}
