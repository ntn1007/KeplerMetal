// Pause OUR factory method before its import, not a vendor method. This makes
// scope destruction happen while a specific asynchronous request is pending.
static IMP pendingOriginal;
static dispatch_semaphore_t pendingEntered,pendingResume;
static id<MTLComputePipelineState>pausedOwnFactory(id self,SEL selector,id<MTLDevice>device,NSData*carrier,NSData*program,MTLComputePipelineDescriptor*descriptor,NSError**error,NSDictionary**evidence) NS_RETURNS_RETAINED;
static id<MTLComputePipelineState>pausedOwnFactory(id self,SEL selector,id<MTLDevice>device,NSData*carrier,NSData*program,MTLComputePipelineDescriptor*descriptor,NSError**error,NSDictionary**evidence){
 dispatch_semaphore_signal(pendingEntered);dispatch_semaphore_wait(pendingResume,DISPATCH_TIME_FOREVER);
 typedef id<MTLComputePipelineState>(*F)(id,SEL,id<MTLDevice>,NSData*,NSData*,MTLComputePipelineDescriptor*,NSError**,NSDictionary**) __attribute__((ns_returns_retained));
 return((F)pendingOriginal)(self,selector,device,carrier,program,descriptor,error,evidence);
}
