// Public binding selectors for the explicitly enabled IRv2 compiler ABI.
// These handles are scoped to owned templates; no Apple resource ID is forged.
@interface KPCommandIRArgumentContext : NSObject
@property(nonatomic,weak) KPGPUCommandSelection *plan;
@property(nonatomic,strong) id<MTLBuffer> context;
@property(nonatomic,strong) NSArray *resources,*pipelines,*parameters,*catalogue;
@property(nonatomic,strong) NSMutableArray *roots;
@property(nonatomic,strong) NSThread *ownerThread;
@property(nonatomic) NSUInteger bindingCount,constantIndex;
@end
@implementation KPCommandIRArgumentContext
@end

@interface KPCommandIRArgumentEncoder : NSObject<MTLArgumentEncoder>
@property(nonatomic,strong) KPCPUICBScope *scope;
@property(nonatomic) NSUInteger bindingCount,argumentOffset;
@property(nonatomic) BOOL generationTaggedRoot;
@property(nonatomic,strong) id<MTLBuffer> argumentBuffer;
@property(nonatomic,strong) KPComputeICB *ICB;
@property(nonatomic,strong) KPGPUCommandSelection *plan;
@property(nonatomic,strong) id<MTLComputePipelineState> pipeline;
@property(nonatomic,strong) NSMutableDictionary *buffers,*rootRecord;
@property(atomic,copy) NSString *label;
@end
@implementation KPCommandIRArgumentEncoder
- (instancetype)init{if((self=[super init]))_buffers=[NSMutableDictionary new];return self;}
- (id<MTLDevice>)device{return _scope.device;}
- (NSUInteger)encodedLength{return(2+_bindingCount)*8;}
- (NSUInteger)alignment{return 8;}
- (void)unsupported{_rootRecord[@"complete"]=@NO;[_rootRecord removeObjectForKey:@"expected"];reject(@"Argument kind is outside the IRv2 compiler ABI");}
- (void)active {
 if(!_scope||_scope.restored)reject(@"Argument scope was restored");
 if(_plan){NSError*e=nil;if(_plan.selectionBuffer||![ _plan validateOwners:&e]||_plan.commandIRArgumentContext.ownerThread!=NSThread.currentThread)reject(@"Argument plan is inactive or accessed from another thread");}
}
- (void)refresh {
 [self active];if(!_plan||!_argumentBuffer)return;
 KPCommandIRArgumentContext*c=_plan.commandIRArgumentContext;
 if(_bindingCount!=c.bindingCount)reject(@"Argument layout and prepared plan differ");
 if(!_rootRecord){
  uint64_t a=_argumentBuffer.gpuAddress+_argumentOffset;
  for(id<MTLBuffer>b in c.resources){uint64_t start=b.gpuAddress;if(a<start+b.length&&start<a+self.encodedLength)reject(@"Argument root aliases a retained producer resource");
   if(b.storageMode!=MTLStorageModePrivate&&b.contents){uintptr_t host=(uintptr_t)_argumentBuffer.contents+_argumentOffset,other=(uintptr_t)b.contents;if(host<other+b.length&&other<host+self.encodedLength)reject(@"Argument root aliases retained CPU backing");}
  }
  for(NSMutableDictionary*r in c.roots){id<MTLBuffer>b=r[@"buffer"];NSUInteger off=[r[@"offset"]unsignedIntegerValue],len=[r[@"bytes"]unsignedIntegerValue];uint64_t start=b.gpuAddress+off;uintptr_t host=(uintptr_t)_argumentBuffer.contents+_argumentOffset,other=(uintptr_t)b.contents+off;
   if(b==_argumentBuffer&&off==_argumentOffset&&len==self.encodedLength){_rootRecord=r;break;}
   if((a<start+len&&start<a+self.encodedLength)||(host<other+len&&other<host+self.encodedLength))reject(@"Argument roots overlap an already exported root");
  }
  if(!_rootRecord){_rootRecord=[@{@"buffer":_argumentBuffer,@"offset":@(_argumentOffset),@"bytes":@(self.encodedLength),@"complete":@NO}mutableCopy];[c.roots addObject:_rootRecord];}
 }
 _rootRecord[@"complete"]=@NO;[_rootRecord removeObjectForKey:@"expected"];
 memset((char*)_argumentBuffer.contents+_argumentOffset,0,self.encodedLength);
 if(!_pipeline||_buffers.count!=_bindingCount){_rootRecord[@"reason"]=@"Argument bindings are incomplete";return;}
 NSUInteger candidate=NSNotFound,bank=NSNotFound,matches=0;BOOL differentStableRoot=NO;
 for(NSUInteger i=0;i<c.pipelines.count;i++){
  NSDictionary*p=c.parameters[i],*bound=_buffers[@(c.constantIndex)];
  if(c.pipelines[i]!=_pipeline||p[@"buffer"]!=bound[@"buffer"]||![p[@"offset"]isEqual:bound[@"offset"]])continue;
  for(NSUInteger j=0;j<c.catalogue.count;j++){
   NSArray*entry=c.catalogue[j];BOOL same=YES;NSUInteger mutableSlot=0;
   for(NSUInteger slot=0;slot<_bindingCount;slot++)if(slot!=c.constantIndex){NSDictionary*x=entry[mutableSlot++],*y=_buffers[@(slot)];same&=x[@"buffer"]==y[@"buffer"]&&[x[@"offset"]isEqual:y[@"offset"]];}
   if(same){
    if(matches&&_plan.commandIRStablePipelineIdentities&&(bank!=j||![_plan.commandIRPipelineIdentities[candidate]isEqual:_plan.commandIRPipelineIdentities[i]]))differentStableRoot=YES;
    candidate=i;bank=j;matches++;
   }
  }
 }
 // Repeated templates with the same PSO, parameter binding and resource bank
 // have an identical stable root. Their local/grid requirements are resolved
 // later by GPU command setters; positional tokens retain the old refusal.
 if(matches!=1&&(!_plan.commandIRStablePipelineIdentities||!matches||differentStableRoot)){_rootRecord[@"reason"]=@"Argument combination is absent or ambiguous in the sealed catalogue";return;}
 NSError*e=nil;id<MTLBuffer>canonical=[_plan newCommandIRArgumentsForCandidateIndex:candidate resourceIndex:bank error:&e];
 if(canonical.length<self.encodedLength)reject(@"Cannot resolve an owned argument representation");
 NSData*bytes=[NSData dataWithBytes:canonical.contents length:self.encodedLength];memcpy((char*)_argumentBuffer.contents+_argumentOffset,bytes.bytes,bytes.length);
 _rootRecord[@"expected"]=bytes;_rootRecord[@"complete"]=@YES;[_rootRecord removeObjectForKey:@"reason"];
 NSMutableDictionary*event=[@{@"operation":@"encode_public_IRv2_arguments",@"resource":@(bank),@"bytes":@(bytes.length),@"offset":@(_argumentOffset),@"native_Apple_ICB_identity":@NO}mutableCopy];
 if(_plan.commandIRStablePipelineIdentities){event[@"root_template_index"]=@(candidate);event[@"execution_template_resolved_on_GPU"]=@YES;}else event[@"candidate"]=@(candidate);
 [_plan.eventRows addObject:event];
}
- (void)setArgumentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset {
 // Detaching a destination does not mutate the prior exported root. Its plan
 // and completion lease retain it, so the encoder can serve another frame.
 if(!_scope||_scope.restored)reject(@"Argument scope was restored");
 if(buffer&&(buffer.device!=self.device||buffer.storageMode!=MTLStorageModeShared||!buffer.contents||offset%8||offset>buffer.length||self.encodedLength>buffer.length-offset||!buffer.gpuAddress||buffer.gpuAddress>>40||buffer.length>((uint64_t(1)<<40)-buffer.gpuAddress)))reject(@"Argument root must be an aligned, CPU-writable owned Shared span");
 _argumentBuffer=buffer;_argumentOffset=offset;_rootRecord=nil;_ICB=nil;_plan=nil;_pipeline=nil;[_buffers removeAllObjects];
}
- (void)setArgumentBuffer:(id<MTLBuffer>)buffer startOffset:(NSUInteger)offset arrayElement:(NSUInteger)element {
 if(element>(NSUIntegerMax-offset)/self.encodedLength)reject(@"Argument array offset overflow");[self setArgumentBuffer:buffer offset:offset+element*self.encodedLength];
}
- (void)setIndirectCommandBuffer:(id<MTLIndirectCommandBuffer>)buffer atIndex:(NSUInteger)index {
 [self active];if(index||![buffer isKindOfClass:KPComputeICB.class]||[buffer isKindOfClass:KPRenderICB.class]||((KPComputeICB*)buffer).scope!=_scope)reject(@"Argument ICB is not an owned compute target");
 KPComputeICB*b=(KPComputeICB*)buffer;KPCommandIRArgumentContext*c=b.commandIRArgumentContext;KPGPUCommandSelection*p=c.plan;
 if(!p||c.bindingCount!=_bindingCount||p.targetICB!=b||c.ownerThread!=NSThread.currentThread||(_plan&&_plan!=p))reject(@"Argument ICB has no matching live IRv2 representation");
 if(_generationTaggedRoot!=(p.reusableContext!=nil))reject(@"Function and ICB context generation ABI differ");
 _ICB=b;_plan=p;[self refresh];
}
- (void)setComputePipelineState:(id<MTLComputePipelineState>)pipeline atIndex:(NSUInteger)index {
 [self active];if(index!=1)reject(@"Pipeline argument index must be1");
 if(pipeline&&_plan){BOOL found=NO;for(id p in _plan.commandIRArgumentContext.pipelines)found|=p==pipeline;if(!found){_rootRecord[@"complete"]=@NO;reject(@"Argument pipeline is not a sealed candidate");}}
 _pipeline=pipeline;[self refresh];
}
- (void)setBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset atIndex:(NSUInteger)index {
 [self active];if(index<2||index>=_bindingCount+2)reject(@"Buffer argument index is outside the pointer layout");
 if(buffer&&(buffer.device!=self.device||offset>buffer.length))reject(@"Argument buffer device/span differs");
 if(buffer)_buffers[@(index-2)]=@{@"buffer":buffer,@"offset":@(offset)};else[_buffers removeObjectForKey:@(index-2)];[self refresh];
}
- (void)setBuffers:(const id<MTLBuffer> __unsafe_unretained*)buffers offsets:(const NSUInteger*)offsets withRange:(NSRange)range {
 if(range.location<2||range.location>_bindingCount+2||range.length>_bindingCount+2-range.location||(range.length&&(!buffers||!offsets)))reject(@"Buffer argument array range differs");for(NSUInteger i=0;i<range.length;i++)[self setBuffer:buffers[i]offset:offsets[i]atIndex:range.location+i];
}
- (void)setComputePipelineStates:(const id<MTLComputePipelineState> __unsafe_unretained*)pipelines withRange:(NSRange)range{if(range.location!=1||range.length!=1||!pipelines)reject(@"Pipeline argument array differs");[self setComputePipelineState:pipelines[0]atIndex:1];}
- (void)setIndirectCommandBuffers:(const id<MTLIndirectCommandBuffer> __unsafe_unretained*)buffers withRange:(NSRange)range{if(range.location||range.length!=1||!buffers)reject(@"ICB argument array differs");[self setIndirectCommandBuffer:buffers[0]atIndex:0];}
- (void)setTexture:(id<MTLTexture>)x atIndex:(NSUInteger)i{[self unsupported];}
- (void)setTextures:(const id<MTLTexture> __unsafe_unretained*)x withRange:(NSRange)r{[self unsupported];}
- (void)setSamplerState:(id<MTLSamplerState>)x atIndex:(NSUInteger)i{[self unsupported];}
- (void)setSamplerStates:(const id<MTLSamplerState> __unsafe_unretained*)x withRange:(NSRange)r{[self unsupported];}
- (void*)constantDataAtIndex:(NSUInteger)i{[self unsupported];return nullptr;}
- (void)setRenderPipelineState:(id<MTLRenderPipelineState>)x atIndex:(NSUInteger)i{[self unsupported];}
- (void)setRenderPipelineStates:(const id<MTLRenderPipelineState> __unsafe_unretained*)x withRange:(NSRange)r{[self unsupported];}
- (void)setAccelerationStructure:(id<MTLAccelerationStructure>)x atIndex:(NSUInteger)i{[self unsupported];}
- (id<MTLArgumentEncoder>)newArgumentEncoderForBufferAtIndex:(NSUInteger)i{[self unsupported];return nil;}
- (void)setVisibleFunctionTable:(id<MTLVisibleFunctionTable>)x atIndex:(NSUInteger)i{[self unsupported];}
- (void)setVisibleFunctionTables:(const id<MTLVisibleFunctionTable> __unsafe_unretained*)x withRange:(NSRange)r{[self unsupported];}
- (void)setIntersectionFunctionTable:(id<MTLIntersectionFunctionTable>)x atIndex:(NSUInteger)i{[self unsupported];}
- (void)setIntersectionFunctionTables:(const id<MTLIntersectionFunctionTable> __unsafe_unretained*)x withRange:(NSRange)r{[self unsupported];}
- (void)setDepthStencilState:(id<MTLDepthStencilState>)x atIndex:(NSUInteger)i{[self unsupported];}
- (void)setDepthStencilStates:(const id<MTLDepthStencilState> __unsafe_unretained*)x withRange:(NSRange)r{[self unsupported];}
@end

namespace {
id<MTLArgumentEncoder> createIRArgumentEncoder(id self,SEL selector,NSArray*arguments) NS_RETURNS_RETAINED;
id<MTLArgumentEncoder> createIRArgumentEncoder(id self,SEL selector,NSArray*arguments){
 KPCPUICBScope*s=scopeFor(self);BOOL special=NO;
 for(MTLArgumentDescriptor*a in arguments)if([a isKindOfClass:MTLArgumentDescriptor.class]&&(a.dataType==MTLDataTypeIndirectCommandBuffer||a.dataType==MTLDataTypeComputePipeline))special=YES;
 if(!s||s.restored||!s.GPUCommandIRv2Selector||!special){
  Class original=s?s.originalDeviceClass:class_getSuperclass(object_getClass(self));Method m=class_getInstanceMethod(original,selector);
  typedef id<MTLArgumentEncoder>(*Factory)(id,SEL,NSArray*) __attribute__((ns_returns_retained));return ((Factory)method_getImplementation(m))(self,selector,arguments);
 }
 if(arguments.count!=5&&arguments.count!=6)reject(@"IRv2 arguments require ICB,pipeline and3/4 pointers");
 NSMutableDictionary*byIndex=[NSMutableDictionary new];
 for(MTLArgumentDescriptor*a in arguments){if(![a isKindOfClass:MTLArgumentDescriptor.class]||a.index>=arguments.count||a.arrayLength!=1||byIndex[@(a.index)])reject(@"IRv2 descriptor index/array shape differs");byIndex[@(a.index)]=a;}
 for(NSUInteger i=0;i<arguments.count;i++){MTLArgumentDescriptor*a=byIndex[@(i)];MTLDataType type=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;if(a.dataType!=type)reject(@"IRv2 argument descriptor type differs");}
 KPCommandIRArgumentEncoder*e=[KPCommandIRArgumentEncoder new];e.scope=s;e.bindingCount=arguments.count-2;
 [s.eventRows addObject:@{@"operation":@"new_public_IRv2_argument_encoder",@"bytes":@(e.encodedLength),@"Apple_native_ICB_ABI":@NO}];return e;
}
}
