// SPDX-License-Identifier: MIT
// Owned render-record roots, not compute IRv2 roots or Apple resource IDs.
@interface KPRenderCommandArgumentContext ()
@property(nonatomic,readwrite,strong) id<MTLBuffer> contextBuffer,commandRecords;
@property(nonatomic,readwrite) NSUInteger contextOffset,commandRecordsOffset,capacity;
@property(nonatomic,readwrite) NSUInteger indexBindingCount,indexBindingTableOffset;
@property(nonatomic,readwrite) NSUInteger vertexTransitionCount,vertexTransitionTableOffset;
@property(nonatomic,readwrite) NSUInteger pipelineTransitionCount,pipelineTransitionTableOffset;
@property(nonatomic,readwrite) NSUInteger fragmentTransitionCount,fragmentTransitionTableOffset;
@property(nonatomic,copy) NSArray<id<MTLBuffer>> *indexOwners,*vertexOwners;
@property(nonatomic,copy) NSArray<id<MTLBuffer>> *fragmentOwners;
@property(nonatomic,copy) NSArray<id<MTLRenderPipelineState>> *pipelineOwners;
@property(nonatomic,copy) NSDictionary<NSNumber*,NSNumber*> *pipelineTokenByObject;
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic,weak) KPRenderICB *target;
@property(nonatomic,strong) KPRenderStateCatalogue *catalogue;
@property(nonatomic,weak) id<MTLCommandBuffer> commandBuffer;
@property(nonatomic,strong) NSThread *ownerThread;
@property(nonatomic,strong) NSMutableArray<NSMutableDictionary*> *roots;
@property(atomic) BOOL prepared,completed,failed;
- (instancetype)initOwned;
@end
@implementation KPRenderCommandArgumentContext
- (instancetype)initOwned{return [super init];}
@end

@interface KPRenderCommandArgumentEncoder : NSObject<MTLArgumentEncoder>
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic,strong) id<MTLBuffer> root;
@property(nonatomic) NSUInteger offset;
@property(nonatomic,strong) KPRenderICB *target;
@property(nonatomic,strong) KPRenderCommandArgumentContext *context;
@property(nonatomic,strong) NSMutableDictionary *rootRow;
@property(nonatomic) BOOL pipelineRoot;
@property(nonatomic,strong) id<MTLRenderPipelineState> pendingPipeline;
@property(atomic,copy) NSString *label;
- (void)encodePipeline;
@end
@implementation KPRenderCommandArgumentEncoder
- (id<MTLDevice>)device{return _scope.device;}
- (NSUInteger)encodedLength{return _pipelineRoot?16:8;}
- (NSUInteger)alignment{return 8;}
- (void)refuse:(NSString*)message{_rootRow[@"complete"]=@NO;reject(message);}
- (void)doesNotRecognizeSelector:(SEL)selector{_rootRow[@"complete"]=@NO;[super doesNotRecognizeSelector:selector];}
- (void)active{
    if(!_scope||_scope.restored)[self refuse:@"Render argument scope was restored"];
    if(_context){NSError*error=nil;if(![_scope validateRenderCommandArgumentContext:_context error:&error])[self refuse:error.localizedDescription];}
}
- (void)setArgumentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset{
    if(!_scope||_scope.restored)[self refuse:@"Render argument scope was restored"];
    if(buffer&&(buffer.device!=self.device||buffer.storageMode!=MTLStorageModeShared||!buffer.contents||offset%8||offset>buffer.length||self.encodedLength>buffer.length-offset||!buffer.gpuAddress||buffer.gpuAddress>>40||buffer.length>((uint64_t(1)<<40)-buffer.gpuAddress)))
        [self refuse:@"Render argument root must be an owned aligned Shared span"];
    _root=buffer;_offset=offset;_target=nil;_context=nil;_rootRow=nil;_pendingPipeline=nil;
}
- (void)setArgumentBuffer:(id<MTLBuffer>)buffer startOffset:(NSUInteger)offset arrayElement:(NSUInteger)element{
    if(element>(NSUIntegerMax-offset)/self.encodedLength)[self refuse:@"Render argument array offset overflows"];
    [self setArgumentBuffer:buffer offset:offset+element*self.encodedLength];
}
- (void)setIndirectCommandBuffer:(id<MTLIndirectCommandBuffer>)buffer atIndex:(NSUInteger)index{
 @synchronized(_scope.factoryLock){
    [self active];
    if(index||object_getClass(buffer)!=KPRenderICB.class||((KPRenderICB*)buffer).scope!=_scope)
        [self refuse:@"Render argument requires this scope's render ICB at index0"];
    KPRenderCommandArgumentContext*c=((KPRenderICB*)buffer).renderArgumentContext;NSError*error=nil;
    if(!c||![_scope validateRenderCommandArgumentContext:c error:&error])[self refuse:error.localizedDescription?:@"Render ICB has no active argument context"];
    if(_pipelineRoot!=(c.pipelineTransitionCount>0))[self refuse:@"Render root and pipeline context differ"];
    if(!_root)[self refuse:@"Set an argument buffer before the render ICB"];
    uint64_t address=_root.gpuAddress+_offset;
    for(KPRenderCommandArgumentContext*other in _scope.renderArgumentContexts){
        if(other.completed||!other.commandBuffer)continue;
        for(NSDictionary*r in other.roots){
            id<MTLBuffer>b=r[@"buffer"];NSUInteger off=[r[@"offset"]unsignedIntegerValue];uint64_t a=b.gpuAddress+off;
            uintptr_t host=(uintptr_t)_root.contents+_offset,prior=(uintptr_t)b.contents+off;
            NSUInteger length=[r[@"bytes"]unsignedIntegerValue]?:8;
            if(b==_root&&off==_offset&&other==c&&length==self.encodedLength){_rootRow=(NSMutableDictionary*)r;continue;}
            if((address<a+length&&a<address+self.encodedLength)||(host<prior+length&&prior<host+self.encodedLength))[self refuse:@"Render argument root overlaps an exported root"];
        }
    }
    NSMutableArray *protectedResources=[@[c.contextBuffer,c.commandRecords]mutableCopy];[protectedResources addObjectsFromArray:c.indexOwners?:@[]];[protectedResources addObjectsFromArray:c.vertexOwners?:@[]];[protectedResources addObjectsFromArray:c.fragmentOwners?:@[]];
    for(id<MTLBuffer>b in protectedResources){
        uint64_t a=b.gpuAddress;if(address<a+b.length&&a<address+self.encodedLength)[self refuse:@"Render argument root aliases retained resources"];
        if(b.storageMode!=MTLStorageModePrivate&&b.contents){uintptr_t host=(uintptr_t)_root.contents+_offset,other=(uintptr_t)b.contents;if(host<other+b.length&&other<host+self.encodedLength)[self refuse:@"Render root aliases retained CPU backing"];}
    }
    if(!_rootRow){
        if(c.roots.count>=16)[self refuse:@"Render argument root count exceeds16"];
        _rootRow=[@{@"buffer":_root,@"offset":@(_offset),@"bytes":@(self.encodedLength),@"complete":@NO}mutableCopy];[c.roots addObject:_rootRow];
    }
    _context=c;_target=(KPRenderICB*)buffer;
    uint64_t pointer=c.contextBuffer.gpuAddress+c.contextOffset;
    if(_pipelineRoot){uint64_t words[2]={pointer,0};memcpy((char*)_root.contents+_offset,words,16);_rootRow[@"complete"]=@NO;if(_pendingPipeline)[self encodePipeline];}
    else{NSData*expected=[NSData dataWithBytes:&pointer length:8];memcpy((char*)_root.contents+_offset,expected.bytes,8);_rootRow[@"expected"]=expected;_rootRow[@"complete"]=@YES;}
    [_scope.eventRows addObject:@{@"operation":@"encode_public_render_record_root",@"index":@0,@"bytes":@(self.encodedLength),@"offset":@(_offset),@"capacity":@(c.capacity),@"Apple_native_ICB_identity":@NO}];
 }
}
- (void)setIndirectCommandBuffers:(const id<MTLIndirectCommandBuffer> __unsafe_unretained*)buffers withRange:(NSRange)range{
    if(range.location||range.length!=1||!buffers)[self refuse:@"Render argument array shape differs"];
    [self setIndirectCommandBuffer:buffers[0]atIndex:0];
}
- (void)setBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset atIndex:(NSUInteger)index{[self refuse:@"Render root accepts only its ICB argument"];}
- (void)setComputePipelineState:(id<MTLComputePipelineState>)pipeline atIndex:(NSUInteger)index{[self refuse:@"Compute root schema differs from render records"];}
- (void*)constantDataAtIndex:(NSUInteger)index{[self refuse:@"Render root has no inline constants"];return nullptr;}
- (id<MTLArgumentEncoder>)newArgumentEncoderForBufferAtIndex:(NSUInteger)index{[self refuse:@"Nested render root encoders are unsupported"];return nil;}
- (void)setBuffers:(const id<MTLBuffer> __unsafe_unretained*)buffers offsets:(const NSUInteger*)offsets withRange:(NSRange)range{[self refuse:@"Render root has no buffer arguments"];}
- (void)setTexture:(id<MTLTexture>)value atIndex:(NSUInteger)index{[self refuse:@"Render root has no texture arguments"];}
- (void)setTextures:(const id<MTLTexture> __unsafe_unretained*)values withRange:(NSRange)range{[self refuse:@"Render root has no texture arguments"];}
- (void)setSamplerState:(id<MTLSamplerState>)value atIndex:(NSUInteger)index{[self refuse:@"Render root has no sampler arguments"];}
- (void)setSamplerStates:(const id<MTLSamplerState> __unsafe_unretained*)values withRange:(NSRange)range{[self refuse:@"Render root has no sampler arguments"];}
- (void)encodePipeline{
    if(!_context||!_rootRow||!_pendingPipeline)[self refuse:@"Pipeline root is incomplete"];
    uint64_t object=(uint64_t)(uintptr_t)(__bridge const void*)_pendingPipeline;NSNumber*token=_context.pipelineTokenByObject[@(object)];
    if(!token)[self refuse:@"Pipeline is not retained by this context"];
    uint64_t words[2]={_context.contextBuffer.gpuAddress+_context.contextOffset,token.unsignedLongLongValue};
    NSData*expected=[NSData dataWithBytes:words length:16];memcpy((char*)_root.contents+_offset,expected.bytes,16);_rootRow[@"expected"]=expected;_rootRow[@"complete"]=@YES;
}
- (void)setRenderPipelineState:(id<MTLRenderPipelineState>)value atIndex:(NSUInteger)index{
 @synchronized(_scope.factoryLock){[self active];if(!_pipelineRoot||index!=1||!_root||!value||value.device!=self.device)[self refuse:@"Pipeline root requires a device pipeline at index1"];
  _pendingPipeline=value;if(_context)[self encodePipeline];}
}
- (void)setRenderPipelineStates:(const id<MTLRenderPipelineState> __unsafe_unretained*)values withRange:(NSRange)range{if(range.location!=1||range.length!=1||!values)[self refuse:@"Pipeline argument array shape differs"];[self setRenderPipelineState:values[0] atIndex:1];}
- (void)setComputePipelineStates:(const id<MTLComputePipelineState> __unsafe_unretained*)values withRange:(NSRange)range{[self refuse:@"Render root has no pipeline arguments"];}
- (void)setAccelerationStructure:(id<MTLAccelerationStructure>)value atIndex:(NSUInteger)index{[self refuse:@"Render root has no acceleration arguments"];}
- (void)setVisibleFunctionTable:(id<MTLVisibleFunctionTable>)value atIndex:(NSUInteger)index{[self refuse:@"Render root has no function tables"];}
- (void)setVisibleFunctionTables:(const id<MTLVisibleFunctionTable> __unsafe_unretained*)values withRange:(NSRange)range{[self refuse:@"Render root has no function tables"];}
- (void)setIntersectionFunctionTable:(id<MTLIntersectionFunctionTable>)value atIndex:(NSUInteger)index{[self refuse:@"Render root has no function tables"];}
- (void)setIntersectionFunctionTables:(const id<MTLIntersectionFunctionTable> __unsafe_unretained*)values withRange:(NSRange)range{[self refuse:@"Render root has no function tables"];}
- (void)setDepthStencilState:(id<MTLDepthStencilState>)value atIndex:(NSUInteger)index{[self refuse:@"Render root has no depth arguments"];}
- (void)setDepthStencilStates:(const id<MTLDepthStencilState> __unsafe_unretained*)values withRange:(NSRange)range{[self refuse:@"Render root has no depth arguments"];}
@end
