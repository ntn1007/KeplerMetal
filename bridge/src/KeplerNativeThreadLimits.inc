// SPDX-License-Identifier: MIT
// A per-pipeline native field correction, never a replacement getter or family flag.
namespace {
char nativeThreadLimitKey;
BOOL installRenderOverride(Class,Class,SEL,IMP);
BOOL configureNativeProducerThreadLimit(id<MTLComputePipelineState>pipeline,NSUInteger requested,NSError**error){
 if(!requested)return YES;
 NSDictionary*proof=objc_getAssociatedObject(pipeline,sel_registerName("KeplerMetalProducerEvidence-v1"));
 Class native=objc_getClass("NVMTLComputePipelineState");Ivar slot=class_getInstanceVariable(native,"maxTotalThreadsPerThreadgroup");
 NSUInteger before=pipeline.maxTotalThreadsPerThreadgroup;
 if(![proof[@"contract_verified"]boolValue]||![proof[@"driver_sha256"]isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"]||object_getClass(pipeline)!=native||class_getInstanceSize(native)!=104||!slot||ivar_getOffset(slot)!=88||strcmp(ivar_getTypeEncoding(slot),"Q")||pipeline.threadExecutionWidth!=32||requested<32||requested>before)return fail(error,@"Unqualified native thread-limit field/profile");
 SEL getter=@selector(maxTotalThreadsPerThreadgroup);IMP implementation=class_getMethodImplementation(native,getter);
 uint64_t actual=0;auto*field=(unsigned char*)(__bridge void*)pipeline+88;memcpy(&actual,field,8);
 if(actual!=before||objc_getAssociatedObject(pipeline,&nativeThreadLimitKey))return fail(error,@"Native thread-limit field differs or was already configured");
 uint64_t value=requested;memcpy(field,&value,8);
 if(pipeline.maxTotalThreadsPerThreadgroup!=requested||class_getMethodImplementation(native,getter)!=implementation){memcpy(field,&actual,8);return fail(error,@"Native getter did not observe the configured field");}
 NSDictionary*limit=@{@"requested":@(requested),@"native_before":@(before),@"native_after":@(pipeline.maxTotalThreadsPerThreadgroup),@"field_offset":@88,@"native_getter_unchanged":@YES,@"shader_optimizer_changed":@NO,@"enforcement":@"Direct and indirect dispatch entry points on explicitly adapted compute encoders"};
 objc_setAssociatedObject(pipeline,&nativeThreadLimitKey,limit,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
 NSMutableDictionary*updated=[proof mutableCopy];updated[@"native_thread_limit"]=limit;objc_setAssociatedObject(pipeline,sel_registerName("KeplerMetalProducerEvidence-v1"),updated,OBJC_ASSOCIATION_RETAIN_NONATOMIC);return YES;
}
Class originalComputeEncoder(id encoder){return class_getSuperclass(object_getClass(encoder));}
void setCallerComputePipeline(id self,SEL selector,id<MTLComputePipelineState>pipeline){
 KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);
 typedef void(*F)(id,SEL,id<MTLComputePipelineState>);((F)class_getMethodImplementation(originalComputeEncoder(self),selector))(self,selector,pipeline);
 if(link.scope&&!link.scope.restored)link.callerComputePipeline=pipeline;
}
void validateNativeThreadLimit(id encoder,MTLSize local){
 KPScopeLink*link=objc_getAssociatedObject(encoder,&contextKey);id<MTLComputePipelineState>p=link.callerComputePipeline;
 NSDictionary*limit=p?objc_getAssociatedObject(p,&nativeThreadLimitKey):nil;if(!limit)return;
 NSUInteger maximum=[limit[@"requested"]unsignedIntegerValue];
 if(!volume(local,maximum))reject(@"Dispatch exceeds the pipeline thread limit or has a zero/overflowing dimension");
 if(p.maxTotalThreadsPerThreadgroup!=maximum)reject(@"Configured native pipeline thread limit was changed");
}
void dispatchLimitedThreadgroups(id self,SEL selector,MTLSize groups,MTLSize local){
 validateNativeThreadLimit(self,local);typedef void(*F)(id,SEL,MTLSize,MTLSize);((F)class_getMethodImplementation(originalComputeEncoder(self),selector))(self,selector,groups,local);
}
void dispatchLimitedThreads(id self,SEL selector,MTLSize threads,MTLSize local){
 validateNativeThreadLimit(self,local);typedef void(*F)(id,SEL,MTLSize,MTLSize);((F)class_getMethodImplementation(originalComputeEncoder(self),selector))(self,selector,threads,local);
}
void dispatchLimitedIndirect(id self,SEL selector,id<MTLBuffer>buffer,NSUInteger offset,MTLSize local){
 validateNativeThreadLimit(self,local);typedef void(*F)(id,SEL,id<MTLBuffer>,NSUInteger,MTLSize);((F)class_getMethodImplementation(originalComputeEncoder(self),selector))(self,selector,buffer,offset,local);
}
void endLimitedComputeEncoder(id self,SEL selector){
 typedef void(*F)(id,SEL);((F)class_getMethodImplementation(originalComputeEncoder(self),selector))(self,selector);
 ((KPScopeLink*)objc_getAssociatedObject(self,&contextKey)).callerComputePipeline=nil;
}
BOOL installNativeThreadLimitChecks(Class dynamic,Class original){
 const SEL selectors[]={@selector(setComputePipelineState:),@selector(dispatchThreadgroups:threadsPerThreadgroup:),@selector(dispatchThreads:threadsPerThreadgroup:),@selector(dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:threadsPerThreadgroup:),@selector(endEncoding)};
 const IMP functions[]={(IMP)setCallerComputePipeline,(IMP)dispatchLimitedThreadgroups,(IMP)dispatchLimitedThreads,(IMP)dispatchLimitedIndirect,(IMP)endLimitedComputeEncoder};
 for(unsigned i=0;i<5;i++){if(i==2&&!class_getInstanceMethod(original,selectors[i]))continue;if(!installRenderOverride(dynamic,original,selectors[i],functions[i]))return NO;}return YES;
}
}
