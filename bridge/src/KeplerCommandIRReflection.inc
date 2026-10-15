// Public reflection adapter. The argument/type objects are the native function's
// immutable metadata; nothing is attached back to the function or its scope.
@interface KPIRBufferBinding : NSObject <MTLBufferBinding>
@property(nonatomic,strong) MTLArgument *nativeArgument;
@end
@implementation KPIRBufferBinding
- (NSString*)name{return _nativeArgument.name;}
- (MTLBindingType)type{return MTLBindingTypeBuffer;}
- (MTLBindingAccess)access{return (MTLBindingAccess)_nativeArgument.access;}
- (NSUInteger)index{return _nativeArgument.index;}
- (BOOL)isUsed{return _nativeArgument.active;}
- (BOOL)isArgument{return YES;}
- (NSUInteger)bufferAlignment{return _nativeArgument.bufferAlignment;}
- (NSUInteger)bufferDataSize{return _nativeArgument.bufferDataSize;}
- (MTLDataType)bufferDataType{return _nativeArgument.bufferDataType;}
- (MTLStructType*)bufferStructType{return _nativeArgument.bufferStructType;}
- (MTLPointerType*)bufferPointerType{return _nativeArgument.bufferPointerType;}
@end
@interface KPIRComputeReflection : MTLComputePipelineReflection
@property(nonatomic,strong) NSArray<MTLArgument*> *nativeArguments;
@property(nonatomic,strong) NSArray<id<MTLBinding>> *nativeBindings;
- (instancetype)initWithNativeArgument:(MTLArgument*)argument;
@end
@implementation KPIRComputeReflection
- (instancetype)initWithNativeArgument:(MTLArgument*)argument{
 if(!(self=[super init]))return nil;
 KPIRBufferBinding*binding=[KPIRBufferBinding new];binding.nativeArgument=argument;
 _nativeArguments=@[argument];_nativeBindings=@[binding];return self;
}
- (NSArray<MTLArgument*>*)arguments{return _nativeArguments;}
- (NSArray<id<MTLBinding>>*)bindings{return _nativeBindings;}
@end
