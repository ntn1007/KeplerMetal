// Included in the private namespace after prepareIndirectRenderRecord.
// Identities are unique within this process across scopes/catalogues.
static std::atomic<uint64_t> nextRenderStateIdentity{1};
static std::atomic<bool> renderStateIdentityExhausted{false};

NSArray *liveRenderCatalogueSources(KPRenderStateCatalogue *catalogue,KPCPUICBScope *scope,NSError **error){
    if(object_getClass(catalogue)!=KPRenderStateCatalogue.class||catalogue.scope!=scope||scope.restored||
       !catalogue.logicalCommandCount||!catalogue.sources.count||catalogue.sources.count>4||
       catalogue.sources.count!=catalogue.stateIdentifiers.count||
       catalogue.logicalCommandCount*catalogue.sources.count>16||
       catalogue.records.count!=catalogue.logicalCommandCount*catalogue.sources.count||
       catalogue.templates.length!=catalogue.records.count*sizeof(KPRenderStateTemplate)){
        fail(error,@"Render catalogue scope/capacity differs");return nil;
    }
    NSMutableArray *buffers=[NSMutableArray new];
    for(KPRenderCatalogueSource *source in catalogue.sources){
        KPRenderICB *buffer=source.buffer;
        if(!buffer||buffer.scope!=scope||buffer.size!=catalogue.logicalCommandCount||
           source.snapshots.count!=buffer.commands.count){
            fail(error,@"Render catalogue source was released or resized");return nil;
        }
        for(NSUInteger i=0;i<buffer.commands.count;i++){
            KPRenderICBCommand *command=buffer.commands[i];id saved=source.snapshots[i];
            if(saved==NSNull.null?command.hasDraw:(!command.hasDraw||command.record!=saved)){
                fail(error,@"Render catalogue source changed after certification");return nil;
            }
        }
        [buffers addObject:buffer];
    }
    return [buffers copy];
}
