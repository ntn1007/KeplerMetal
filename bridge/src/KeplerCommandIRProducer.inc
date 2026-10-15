// Explicitly registered, already GPU-qualified source/program pairs only.
@protocol KPCommandIRProducerFactoryProtocol <NSObject>
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
    carrier:(NSData *)carrier program:(NSData *)program error:(NSError **)error
    evidence:(NSDictionary **)evidence NS_RETURNS_RETAINED;
@end
namespace {
NSDictionary *nativeProducerPins(){
 return @{
  @"encode_dataflow_basic":@"e99dbc3cdd06c94fe12fa4c7844171d798db19008511cef4631c88cf8bd5a408",
  @"encode_dataflow_barrier":@"7e1f63516f6c950f3214ae467a65e6463e7284224d6244e4290ea33b05ba9744",
  @"encode_dataflow_copy":@"f2ae6bd728e63391edb4093655a1e6e997414f4533160b810f5867fd5ae08e0b",
  @"encode_dataflow_no_seed":@"f23da37c9ee8eddfbe343ff73663565fcdda8298e18be358995e2bb2aaab55e1",
  @"encode_dataflow_no_gather":@"5c04b0889ce20063b09456f33306c9eac3712a66a27de9ee2a6163c54ed586ca",
  @"encode_dataflow_no_finish":@"92dca0817ba9b17a1f4f17068c37fc412979531ec08488f39d6adad3cf6c714e"
 };
}
id<MTLComputePipelineState>registeredProducerPipeline(id self,SEL selector,id<MTLFunction>function,NSError**error) NS_RETURNS_RETAINED;
id<MTLComputePipelineState>registeredProducerPipeline(id self,SEL selector,id<MTLFunction>function,NSError**error){
 KPCPUICBScope*scope=((KPScopeLink*)objc_getAssociatedObject(self,&contextKey)).scope;
 KPIRFunctionLink*link=function?objc_getAssociatedObject(function,&IRFunctionKey):nil;
 if(scope&&!scope.restored&&link.scope==scope&&link.nativeRootPipeline){
  if(error)*error=nil;
  [scope.eventRows addObject:@{@"operation":@"new_registered_IRv2_pipeline",@"function":function.name,@"selector":NSStringFromSelector(selector),@"native_pipeline":@YES,@"native_root_binding":@YES,@"compiled_at_registration":@YES}];
  return link.nativeRootPipeline;
 }
 Class original=scope?scope.originalDeviceClass:class_getSuperclass(object_getClass(self));Method method=class_getInstanceMethod(original,selector);
 if(!method){fail(error,@"Native compute pipeline selector missing");return nil;}
 typedef id<MTLComputePipelineState>(*Factory)(id,SEL,id<MTLFunction>,NSError**) __attribute__((ns_returns_retained));
 return((Factory)method_getImplementation(method))(self,selector,function,error);
}
}
