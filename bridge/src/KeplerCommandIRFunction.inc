// Native MTLFunction metadata stays authoritative. Only explicitly registered
// function instances receive argument encoders for the separately compiled IRv2.
@interface KPIRFunctionLink : NSObject
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic) Class originalClass;
@property(nonatomic) NSUInteger bufferIndex,bindingCount;
@property(nonatomic,copy) NSDictionary *schema;
@property(nonatomic,copy) NSString *librarySHA;
@property(nonatomic,strong) id<MTLComputePipelineState> nativeRootPipeline;
@property(nonatomic,copy) NSDictionary *nativeProducerProfile;
@end
@implementation KPIRFunctionLink
@end
@interface KPAdaptedFunction : NSObject
@property(nonatomic,weak) id<MTLFunction> function;
@property(nonatomic) Class originalClass;
@end
@implementation KPAdaptedFunction
@end
namespace {
char IRFunctionKey;
std::map<uintptr_t,Class> functionClasses;
thread_local NSUInteger nativeFunctionArgumentDepth=0;
NSDictionary*functionArgumentSchema(MTLArgument*argument,id<MTLArgumentEncoder>encoder,NSUInteger index){
 if(!argument||argument.type!=MTLArgumentTypeBuffer||argument.index!=index||argument.bufferDataType!=MTLDataTypeStruct||encoder.alignment!=8)return nil;
 NSArray*members=argument.bufferStructType.members;NSUInteger count=members.count;
 if((count!=5&&count!=6)||argument.bufferDataSize!=count*8||argument.bufferAlignment!=8||encoder.encodedLength!=count*8)return nil;
 NSMutableArray*rows=[NSMutableArray new];
 for(NSUInteger i=0;i<count;i++){
  MTLStructMember*m=members[i];MTLDataType type=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;
  if(m.dataType!=type||m.offset!=i*8||m.argumentIndex!=i)return nil;
  [rows addObject:@{@"name":[NSString stringWithUTF8String:m.name.UTF8String],@"type":@(m.dataType),@"offset":@(m.offset),@"index":@(m.argumentIndex)}];
 }
 return @{@"buffer_index":@(index),@"binding_count":@(count-2),@"encoded_length":@(count*8),@"alignment":@8,@"members":[rows copy]};
}
id<MTLArgumentEncoder>nativeFunctionEncoder(id self,SEL selector,NSUInteger index,MTLArgument*__autoreleasing*reflection){
 KPIRFunctionLink*link=objc_getAssociatedObject(self,&IRFunctionKey);Class original=link?link.originalClass:class_getSuperclass(object_getClass(self));Method m=class_getInstanceMethod(original,selector);if(!m)reject(@"Native function encoder selector is missing");
 nativeFunctionArgumentDepth++;
 @try{
  if(sel_isEqual(selector,@selector(newArgumentEncoderWithBufferIndex:reflection:))){typedef id<MTLArgumentEncoder>(*F)(id,SEL,NSUInteger,MTLArgument*__autoreleasing*) __attribute__((ns_returns_retained));return((F)method_getImplementation(m))(self,selector,index,reflection);}
  typedef id<MTLArgumentEncoder>(*F)(id,SEL,NSUInteger) __attribute__((ns_returns_retained));return((F)method_getImplementation(m))(self,selector,index);
 }@finally{nativeFunctionArgumentDepth--;}
}
id<MTLArgumentEncoder>IRFunctionEncoder(KPIRFunctionLink*link){
 NSMutableArray*a=[NSMutableArray new];for(NSUInteger i=0;i<link.bindingCount+2;i++){MTLArgumentDescriptor*d=[MTLArgumentDescriptor argumentDescriptor];d.index=i;d.arrayLength=1;d.dataType=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;[a addObject:d];}
 id<MTLArgumentEncoder>encoder=[link.scope.device newArgumentEncoderWithArguments:a];if(encoder.encodedLength!=(link.bindingCount+2)*8||encoder.alignment!=8)reject(@"Registered function and IR argument encoder differ");return encoder;
}
id<MTLArgumentEncoder>functionIRArguments(id self,SEL selector,NSUInteger index) NS_RETURNS_RETAINED;
id<MTLArgumentEncoder>functionIRArguments(id self,SEL selector,NSUInteger index){
 KPIRFunctionLink*link=objc_getAssociatedObject(self,&IRFunctionKey);KPCPUICBScope*s=link.scope;
 if(nativeFunctionArgumentDepth||!s||s.restored||index!=link.bufferIndex)return nativeFunctionEncoder(self,selector,index,nullptr);
 [s.eventRows addObject:@{@"operation":@"function_IRv2_argument_encoder",@"function":[self name],@"buffer_index":@(index),@"reflection_requested":@NO}];return IRFunctionEncoder(link);
}
id<MTLArgumentEncoder>functionIRArgumentsWithReflection(id self,SEL selector,NSUInteger index,MTLArgument*__autoreleasing*reflection) NS_RETURNS_RETAINED;
id<MTLArgumentEncoder>functionIRArgumentsWithReflection(id self,SEL selector,NSUInteger index,MTLArgument*__autoreleasing*reflection){
 KPIRFunctionLink*link=objc_getAssociatedObject(self,&IRFunctionKey);KPCPUICBScope*s=link.scope;
 if(nativeFunctionArgumentDepth||!s||s.restored||index!=link.bufferIndex)return nativeFunctionEncoder(self,selector,index,reflection);
 MTLArgument*argument=nil;id<MTLArgumentEncoder>native=nativeFunctionEncoder(self,selector,index,&argument);NSDictionary*schema=functionArgumentSchema(argument,native,index);
 if(![schema isEqual:link.schema])reject(@"Native function reflection changed after registration");
 if(reflection)*reflection=argument;
 [s.eventRows addObject:@{@"operation":@"function_IRv2_argument_encoder",@"function":[self name],@"buffer_index":@(index),@"reflection_requested":@YES,@"native_reflection_preserved":@YES}];return IRFunctionEncoder(link);
}
}
