// SPDX-License-Identifier: MIT
// Public API/reflection/lifetime reception; no command buffer or GPU dispatch.
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#import <objc/runtime.h>
#import <CommonCrypto/CommonDigest.h>
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char c:h)[s appendFormat:@"%02x",c];return s;}
static void emit(id x){NSData*d=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;NSString*assets=@(argv[1]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}if(!d)return 2;
 Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 auto bytes=[&](NSString*name){return[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:name]];};
 NSData*consumer=bytes(@"consumer.metallib"),*manifest=bytes(@"consumer.json");
 KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:consumer expectedSHA256:sha(consumer) manifestData:manifest expectedManifestSHA256:sha(manifest) error:&error];if(!s)return 3;
 for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=bytes(a[0]);BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[s enableGPUCommandSelectionWithLibraryData:b expectedSHA256:sha(b)error:&error];break;case 1:ok=[s enableGPUCommandGeometryWithLibraryData:b expectedSHA256:sha(b)error:&error];break;case 2:ok=[s enableGPUCommandBindingsWithLibraryData:b expectedSHA256:sha(b)error:&error];break;case 3:ok=[s enableGPUCommandIRv2WithLibraryData:b expectedSHA256:sha(b)error:&error];}if(!ok)return 3;}
 NSMutableArray*cases=[NSMutableArray new];NSData*source=bytes(@"native_producer.metallib");NSString*digest=sha(source);
 auto check=[&](NSString*name,BOOL ok){[cases addObject:@{@"case":name,@"PASS":@(ok)}];if(!ok){emit(@{@"status":@"FAIL",@"cases":cases,@"error":error.description?:@""});return false;}return true;};
 for(NSString*name in @[@"empty",@"hash",@"index",@"missing",@"old_opaque",@"wrong_token",@"wrong_context_type",@"wrong_context_size",@"wrong_context_access",@"missing_context",@"missing_slot",@"extra_slot"]){
  NSData*data=source;NSString*expected=digest,*function=@"encode_dataflow_basic";NSUInteger index=0;
  if([name isEqual:@"empty"])data=[NSData data];
  else if([name isEqual:@"hash"])expected=[@"0" stringByPaddingToLength:64 withString:@"0" startingAtIndex:0];
  else if([name isEqual:@"index"])index=1;
  else if([name isEqual:@"missing"])function=@"does_not_exist";
  else if([name isEqual:@"old_opaque"]){data=bytes(@"opaque_producer.metallib");expected=sha(data);}
  else{data=bytes(@"function_contracts.metallib");expected=sha(data);function=name;}
  error=nil;id f=[s newNativeSourceCommandIRFunctionWithLibraryData:data expectedSHA256:expected functionName:function rootBufferIndex:index error:&error];
  if(!check([@"refuse_" stringByAppendingString:name],!f&&error))return 4;
 }
 NSMutableData*mutableSource=[source mutableCopy];NSMutableString*mutableName=[@"encode_dataflow_basic" mutableCopy];error=nil;
 id<MTLFunction>f=[s newNativeSourceCommandIRFunctionWithLibraryData:mutableSource expectedSHA256:digest functionName:mutableName rootBufferIndex:0 error:&error];[mutableSource setLength:0];[mutableName setString:@"changed"];
 if(!check(@"immutable_registration",f&&!error&&[f.name isEqual:@"encode_dataflow_basic"]&&f.device==d))return 5;
 MTLArgument*root=nil;id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0 reflection:&root];
 if(!check(@"adapted_getter_native_reflection",[NSStringFromClass(object_getClass(ae))isEqual:@"KPCommandIRArgumentEncoder"]&&ae.encodedLength==48&&ae.alignment==8&&root.bufferDataSize==48&&((MTLStructMember*)root.bufferStructType.members[0]).dataType==MTLDataTypePointer&&((MTLStructMember*)root.bufferStructType.members[1]).dataType==MTLDataTypeULong))return 5;
 error=nil;id reversed=[s newCommandIRFunctionWithLibraryData:source expectedSHA256:digest functionName:@"encode_dataflow_basic" rootBufferIndex:0 error:&error];if(!check(@"reverse_ABI_refused",!reversed&&error))return 5;
 NSData*opaque=bytes(@"opaque_producer.metallib");error=nil;id<MTLFunction>legacy=[s newCommandIRFunctionWithLibraryData:opaque expectedSHA256:sha(opaque) functionName:@"encode_dataflow_basic" rootBufferIndex:0 error:&error];
 MTLArgument*oldRoot=nil;id<MTLArgumentEncoder>oldEncoder=[legacy newArgumentEncoderWithBufferIndex:0 reflection:&oldRoot];root=nil;id<MTLArgumentEncoder>again=[f newArgumentEncoderWithBufferIndex:0 reflection:&root];
 if(!check(@"legacy_getters_coexist",legacy&&!error&&oldEncoder.encodedLength==48&&again.encodedLength==48&&((MTLStructMember*)oldRoot.bufferStructType.members[0]).dataType==MTLDataTypeIndirectCommandBuffer&&((MTLStructMember*)oldRoot.bufferStructType.members[1]).dataType==MTLDataTypeComputePipeline&&((MTLStructMember*)root.bufferStructType.members[1]).dataType==MTLDataTypeULong))return 5;
 NSMutableArray*factories=[NSMutableArray new];
 for(unsigned variant=0;variant<6;variant++){
  __block id<MTLComputePipelineState>p=nil;__block MTLComputePipelineReflection*reflection=nil;__block NSError*failure=nil;BOOL completionDone=YES;
  MTLComputePipelineDescriptor*desc=[MTLComputePipelineDescriptor new];desc.computeFunction=f;desc.label=@"native_source_contract";MTLPipelineOption options=MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo;
  if(variant==0)p=[d newComputePipelineStateWithFunction:f error:&failure];
  else if(variant==1)p=[d newComputePipelineStateWithFunction:f options:options reflection:&reflection error:&failure];
  else if(variant==2)p=[d newComputePipelineStateWithDescriptor:desc options:options reflection:&reflection error:&failure];
  else{
   dispatch_semaphore_t sem=dispatch_semaphore_create(0);
   if(variant==3)[d newComputePipelineStateWithFunction:f completionHandler:^(id<MTLComputePipelineState>x,NSError*e){p=x;failure=e;dispatch_semaphore_signal(sem);}];
   else if(variant==4)[d newComputePipelineStateWithFunction:f options:options completionHandler:^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*r,NSError*e){p=x;reflection=r;failure=e;dispatch_semaphore_signal(sem);}];
   else[d newComputePipelineStateWithDescriptor:desc options:options completionHandler:^(id<MTLComputePipelineState>x,MTLComputePipelineReflection*r,NSError*e){p=x;reflection=r;failure=e;dispatch_semaphore_signal(sem);}];
   completionDone=dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC))==0;
  }
  MTLArgument*arg=reflection.arguments.firstObject;BOOL wantsReflection=variant!=0&&variant!=3;
  BOOL ok=completionDone&&p&&!failure&&p.device==d&&[NSStringFromClass(object_getClass(p))isEqual:@"NVMTLComputePipelineState"]&&p.threadExecutionWidth==32&&p.maxTotalThreadsPerThreadgroup>=32&&(!wantsReflection||(reflection.arguments.count>=1&&arg.bufferDataSize==48&&((MTLStructMember*)arg.bufferStructType.members[1]).dataType==MTLDataTypeULong))&&((variant!=2&&variant!=5)||[p.label isEqual:desc.label]);
  [factories addObject:@{@"variant":@(variant),@"PASS":@(ok),@"class":p?NSStringFromClass(object_getClass(p)):@"",@"native_reflection":@(wantsReflection&&arg.bufferDataSize==48),@"error":failure.description?:@""}];
  if(!check([NSString stringWithFormat:@"native_factory_%u",variant],ok))return 6;
 }
 [s restore];BOOL inactiveRejected=NO;@try{[ae setArgumentBuffer:nil offset:0];}@catch(NSException*x){inactiveRejected=[x.reason isEqual:@"Argument scope was restored"];}
 if(!check(@"inactive_encoder_refused",inactiveRejected))return 7;
 root=nil;id<MTLArgumentEncoder>native=[f newArgumentEncoderWithBufferIndex:0 reflection:&root];
 id<MTLArgumentEncoder>oldNative=[legacy newArgumentEncoderWithBufferIndex:0];
 if(!check(@"native_getters_restored",object_getClass(d)==original&&[NSStringFromClass(object_getClass(f))isEqual:@"_MTLFunctionInternal"]&&[NSStringFromClass(object_getClass(legacy))isEqual:@"_MTLFunctionInternal"]&&[NSStringFromClass(object_getClass(oldNative))isEqual:@"NVMTLIndirectArgumentEncoder"]&&[NSStringFromClass(object_getClass(native))isEqual:@"NVMTLIndirectArgumentEncoder"]&&native.encodedLength==48&&root.bufferDataSize==48))return 7;
 error=nil;id bad=[s newNativeSourceCommandIRFunctionWithLibraryData:source expectedSHA256:digest functionName:@"encode_dataflow_basic" rootBufferIndex:0 error:&error];if(!check(@"inactive_registration_refused",!bad&&error))return 7;
 emit(@{@"status":@"PASS",@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":KPKepler880MIdentity(d),@"cases":cases,@"factories":factories,@"events":s.events,@"scope_restored":@YES,@"GPU_command_buffers":@0,@"GPU_dispatches":@0,@"instruction_import":@NO,@"system_modified":@NO});return 0;
}}
