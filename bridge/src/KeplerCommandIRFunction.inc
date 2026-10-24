// Native MTLFunction metadata stays authoritative. Only explicitly registered
// function instances receive argument encoders for the separately compiled IRv2.
@interface KPIRFunctionLink : NSObject
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic) Class originalClass;
@property(nonatomic) NSUInteger bufferIndex,bindingCount;
@property(nonatomic) BOOL nativeSourceLowering;
@property(nonatomic) BOOL generationTaggedRoot;
@property(nonatomic) BOOL renderRecordRoot;
@property(nonatomic,copy) NSDictionary *schema;
@property(nonatomic,copy) NSString *librarySHA;
@property(nonatomic,strong) id<MTLComputePipelineState> nativeRootPipeline;
@property(nonatomic,copy) NSDictionary *nativeProducerProfile;
@property(nonatomic,copy) NSData *nativeProducerCarrier,*nativeProducerProgram;
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
NSDictionary*functionArgumentSchema(MTLArgument*argument,id<MTLArgumentEncoder>encoder,NSUInteger index,BOOL lowered=NO,BOOL tagged=NO){
 if(!argument||argument.type!=MTLArgumentTypeBuffer||argument.index!=index||argument.bufferDataType!=MTLDataTypeStruct||encoder.alignment!=8)return nil;
 NSArray*members=argument.bufferStructType.members;NSUInteger count=members.count;
 if((count!=5&&count!=6)||argument.bufferDataSize!=count*8||argument.bufferAlignment!=8||encoder.encodedLength!=count*8)return nil;
 NSMutableArray*rows=[NSMutableArray new];
 for(NSUInteger i=0;i<count;i++){
  MTLStructMember*m=members[i];MTLDataType type=i==0?(tagged?MTLDataTypeULong:lowered?MTLDataTypePointer:MTLDataTypeIndirectCommandBuffer):i==1?(lowered?MTLDataTypeULong:MTLDataTypeComputePipeline):MTLDataTypePointer;
  if(m.dataType!=type||m.offset!=i*8||m.argumentIndex!=i)return nil;
  [rows addObject:@{@"name":[NSString stringWithUTF8String:m.name.UTF8String],@"type":@(m.dataType),@"offset":@(m.offset),@"index":@(m.argumentIndex)}];
 }
 if(lowered&&!tagged){
  // The source-lowered root contains a real pointer to our context, not an
  // opaque Apple command-buffer identity. Validate its complete wire layout.
  MTLPointerType*p=((MTLStructMember*)members[0]).pointerType;
  if(p.elementType!=MTLDataTypeStruct||p.alignment!=8||p.dataSize!=sizeof(KPCommandContext)||p.access!=MTLArgumentAccessReadWrite)return nil;
  NSArray*fields=p.elementStructType.members;
  NSArray*names=@[@"magic",@"version",@"capacity",@"max_bindings",@"records_address",@"record_bytes",@"pipeline_count"];
  const NSUInteger offsets[]={0,4,8,12,16,24,28};
  if(fields.count!=names.count)return nil;
  for(NSUInteger i=0;i<names.count;i++){MTLStructMember*m=fields[i];if(![m.name isEqual:names[i]]||m.offset!=offsets[i]||m.dataType!=(i==4?MTLDataTypeULong:MTLDataTypeUInt))return nil;}
 }
 return @{@"buffer_index":@(index),@"binding_count":@(count-2),@"encoded_length":@(count*8),@"alignment":@8,@"members":[rows copy]};
}
NSDictionary*renderRecordFunctionSchema(MTLArgument*a,id<MTLArgumentEncoder>native,NSUInteger index){
 if(index||!a||a.type!=MTLArgumentTypeBuffer||a.index||!a.active||a.bufferDataType!=MTLDataTypeULong||a.bufferDataSize!=8||a.bufferAlignment!=8||a.access!=MTLArgumentAccessReadOnly||native.encodedLength||native.alignment!=1)return nil;
 return @{@"kind":@"render_records_v1",@"compiled_root_type":@(a.bufferDataType),@"compiled_root_bytes":@8,@"compiled_root_alignment":@8,@"native_encoded_length":@0,@"native_encoder_alignment":@1,@"encoded_length":@8,@"alignment":@8,@"buffer_index":@0};
}
id<MTLArgumentEncoder>nativeFunctionEncoder(id self,SEL selector,NSUInteger index,MTLArgument*__autoreleasing*reflection){
 KPIRFunctionLink*link=objc_getAssociatedObject(self,&IRFunctionKey);Class actual=object_getClass(self),native=objc_getClass("_MTLFunctionInternal");Class original=link?link.originalClass:(actual==native?native:class_getSuperclass(actual));Method m=class_getInstanceMethod(original,selector);if(!m)reject(@"Native function encoder selector is missing");
 nativeFunctionArgumentDepth++;
 @try{
  if(sel_isEqual(selector,@selector(newArgumentEncoderWithBufferIndex:reflection:))){typedef id<MTLArgumentEncoder>(*F)(id,SEL,NSUInteger,MTLArgument*__autoreleasing*) __attribute__((ns_returns_retained));return((F)method_getImplementation(m))(self,selector,index,reflection);}
  typedef id<MTLArgumentEncoder>(*F)(id,SEL,NSUInteger) __attribute__((ns_returns_retained));return((F)method_getImplementation(m))(self,selector,index);
 }@finally{nativeFunctionArgumentDepth--;}
}
id<MTLArgumentEncoder>functionIRArguments(id,SEL,NSUInteger) NS_RETURNS_RETAINED;
id<MTLArgumentEncoder>functionIRArgumentsWithReflection(id,SEL,NSUInteger,MTLArgument*__autoreleasing*) NS_RETURNS_RETAINED;
BOOL installRenderOverride(Class,Class,SEL,IMP);
BOOL adoptNativeIRFunction(KPCPUICBScope*s,id<MTLFunction>function,NSString*expected,NSUInteger index,BOOL allowExisting,NSError**error,BOOL lowered=NO,BOOL tagged=NO){
 @synchronized(s.factoryLock){
  if(error)*error=nil;
  if(s.restored||!s.GPUCommandIRv2Selector||index||!function||function.functionType!=MTLFunctionTypeKernel||function.device!=s.device)return fail(error,@"Native producer function identity/type differs");
  KPIRFunctionLink*old=objc_getAssociatedObject(function,&IRFunctionKey);
  if(old)return allowExisting&&old.scope==s&&old.bufferIndex==index&&old.nativeSourceLowering==lowered&&old.generationTaggedRoot==tagged&&[old.librarySHA isEqual:expected]?YES:fail(error,@"Function is already owned by another registration");
  MTLArgument*argument=nil;id<MTLArgumentEncoder>native=nil;
  nativeFunctionArgumentDepth++;@try{native=[function newArgumentEncoderWithBufferIndex:index reflection:&argument];}@catch(NSException*x){fail(error,x.reason?:@"Native argument reflection failed");}@finally{nativeFunctionArgumentDepth--;}
  NSDictionary*schema=functionArgumentSchema(argument,native,index,lowered,tagged);if(!schema)return fail(error,@"Native reflection is outside the dense IRv2 ABI");
  BOOL gettersAdapted=![native isKindOfClass:KPCommandIRArgumentEncoder.class];Class original=object_getClass(function),dynamic=original;
  if(gettersAdapted){
   {std::lock_guard<std::mutex>lock(installMutex);dynamic=scopedClass(functionClasses,original,@"KPIRFunction_",@selector(newArgumentEncoderWithBufferIndex:),(IMP)functionIRArguments,error);if(!dynamic||!installRenderOverride(dynamic,original,@selector(newArgumentEncoderWithBufferIndex:reflection:),(IMP)functionIRArgumentsWithReflection))return fail(error,@"Cannot create function-local encoder overrides");}
   KPIRFunctionLink*link=[KPIRFunctionLink new];link.scope=s;link.originalClass=original;link.bufferIndex=index;link.bindingCount=[schema[@"binding_count"]unsignedIntegerValue];link.schema=schema;link.librarySHA=[expected copy];link.nativeSourceLowering=lowered;link.generationTaggedRoot=tagged;objc_setAssociatedObject(function,&IRFunctionKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(function,dynamic);
   KPAdaptedFunction*record=[KPAdaptedFunction new];record.function=function;record.originalClass=original;if(!s.adaptedFunctions)s.adaptedFunctions=[NSMutableArray new];[s.adaptedFunctions addObject:record];
  }
  NSMutableArray*events=s.eventRows;@synchronized(events){[events addObject:@{@"operation":@"register_native_IRv2_function",@"function":function.name,@"library_SHA256":expected,@"schema":schema,@"native_class":NSStringFromClass(original),@"dynamic_class":NSStringFromClass(dynamic),@"native_reflection_reused":@YES,@"function_getters_adapted":@(gettersAdapted),@"native_argument_encoder_class":NSStringFromClass(object_getClass(native)),@"native_shader_compilation_replaced":@NO,@"GPU_execution":@NO}];}return YES;
 }
}
id<MTLArgumentEncoder>IRFunctionEncoder(KPIRFunctionLink*link){
 if(link.renderRecordRoot){MTLArgumentDescriptor*d=[MTLArgumentDescriptor argumentDescriptor];d.index=0;d.arrayLength=1;d.dataType=MTLDataTypeIndirectCommandBuffer;return[link.scope.device newArgumentEncoderWithArguments:@[d]];}
 NSMutableArray*a=[NSMutableArray new];for(NSUInteger i=0;i<link.bindingCount+2;i++){MTLArgumentDescriptor*d=[MTLArgumentDescriptor argumentDescriptor];d.index=i;d.arrayLength=1;d.dataType=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;[a addObject:d];}
 id<MTLArgumentEncoder>encoder=[link.scope.device newArgumentEncoderWithArguments:a];if(encoder.encodedLength!=(link.bindingCount+2)*8||encoder.alignment!=8)reject(@"Registered function and IR argument encoder differ");((KPCommandIRArgumentEncoder*)encoder).generationTaggedRoot=link.generationTaggedRoot;return encoder;
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
 MTLArgument*argument=nil;id<MTLArgumentEncoder>native=nativeFunctionEncoder(self,selector,index,&argument);NSDictionary*schema=link.renderRecordRoot?renderRecordFunctionSchema(argument,native,index):functionArgumentSchema(argument,native,index,link.nativeSourceLowering,link.generationTaggedRoot);
 if(![schema isEqual:link.schema])reject(@"Native function reflection changed after registration");
 if(reflection)*reflection=argument;
 [s.eventRows addObject:@{@"operation":@"function_IRv2_argument_encoder",@"function":[self name],@"buffer_index":@(index),@"reflection_requested":@YES,@"native_reflection_preserved":@YES}];return IRFunctionEncoder(link);
}
}
