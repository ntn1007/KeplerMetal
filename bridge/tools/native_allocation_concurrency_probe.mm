// SPDX-License-Identifier: MIT
#import "KeplerNativeAllocation.h"
#import "KeplerNativeCAS.h"
#import <objc/runtime.h>
#include <atomic>
#include <thread>
#include <cstring>
#include "NativeAllocationExecution.inc"

struct GateState {
 __strong NSCondition*condition=[NSCondition new];
 bool entered=false,nativeDone=false,legacyStarted=false,legacyDone=false,blocked=false,hookSeen=false,timedOut=false;
 Method method=nullptr;IMP baseline=nullptr;
};

// A forwarding device object gates our own call before entering the real Metal
// device. It does not replace a method on the system's device object/class.
@interface KPAllocationGateDevice : NSProxy {
 id<MTLDevice>_target;GateState*_gate;
}
+ (id)device:(id<MTLDevice>)target gate:(GateState*)gate;
@end
@implementation KPAllocationGateDevice
+ (id)device:(id<MTLDevice>)target gate:(GateState*)gate {
 KPAllocationGateDevice*p=[self alloc];p->_target=target;p->_gate=gate;return p;
}
- (NSMethodSignature*)methodSignatureForSelector:(SEL)s{return[(id)_target methodSignatureForSelector:s];}
- (void)forwardInvocation:(NSInvocation*)invocation{[invocation invokeWithTarget:_target];}
- (id<MTLComputePipelineState>)newComputePipelineStateWithFunction:(id<MTLFunction>)function error:(NSError**)error {
 [_gate->condition lock];_gate->hookSeen=method_getImplementation(_gate->method)!=_gate->baseline;
 _gate->entered=true;[_gate->condition broadcast];NSDate*deadline=[NSDate dateWithTimeIntervalSinceNow:8];
 while(!(_gate->nativeDone&&_gate->legacyStarted)) {
  if(![_gate->condition waitUntilDate:deadline]){_gate->timedOut=true;break;}
 }
 if(!_gate->timedOut&&!_gate->legacyDone)[_gate->condition waitUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
 _gate->blocked=_gate->legacyStarted&&!_gate->legacyDone;
 [_gate->condition unlock];
 return[_target newComputePipelineStateWithFunction:function error:error];
}
@end

struct PipelineResult {
 __strong id<MTLComputePipelineState>pipeline=nil;
 __strong NSDictionary*proof=nil;
 __strong NSString*error=@"";
};
static bool awaitGate(GateState&gate) {
 [gate.condition lock];NSDate*deadline=[NSDate dateWithTimeIntervalSinceNow:8];
 while(!gate.entered)if(![gate.condition waitUntilDate:deadline]){[gate.condition unlock];return false;}
 [gate.condition unlock];return true;
}
static id<MTLComputePipelineState>plain(id<MTLDevice>d,NSData*data,NSString*name,NSError**error) {
 dispatch_data_t bytes=dispatch_data_create(data.bytes,data.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)data.length;});
 id<MTLLibrary>library=[d newLibraryWithData:bytes error:error];id<MTLFunction>f=[library newFunctionWithName:name];
 return f?[d newComputePipelineStateWithFunction:f error:error]:nil;
}
static NSDictionary*runCAS(id<MTLDevice>d,id<MTLComputePipelineState>pipeline,NSString*out,NSDictionary*profile) {
 struct Params{uint32_t seed,n,local,groups,variant;}params={0x2468,99,33,3,0};
 NSUInteger bytes=params.n*16+128;id<MTLBuffer>staging=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];
 id<MTLBuffer>output=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>unused=[d newBufferWithLength:params.n*4 options:MTLResourceStorageModePrivate];if(!staging||!output||!unused)return nil;
 memset(staging.contents,0xa5,bytes);id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];
 id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:staging sourceOffset:0 toBuffer:output destinationOffset:0 size:bytes];[b endEncoding];
 id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:pipeline];[e setBytes:&params length:sizeof params atIndex:0];
 [e setBuffer:output offset:64 atIndex:1];[e setBuffer:unused offset:0 atIndex:3];
 [e dispatchThreadgroups:MTLSizeMake(3,1,1)threadsPerThreadgroup:MTLSizeMake(33,1,1)];[e endEncoding];
 b=[cb blitCommandEncoder];[b copyFromBuffer:output sourceOffset:0 toBuffer:staging destinationOffset:0 size:bytes];[b endEncoding];
 [cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return nil;
 NSString*file=@"concurrent-cas.bin";if(![[NSData dataWithBytes:staging.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:file]atomically:YES])return nil;
 return @{@"kind":@"CAS",@"function":profile[@"function"],@"candidate":profile[@"candidate"],@"layout":profile[@"layout"],
  @"local":@33,@"groups":@3,@"variant":@0,@"iteration":@0,@"seed":@(params.seed),@"file":file,@"committed":@YES,@"command_status":@(cb.status)};
}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4||strcmp(argv[3],"concurrent"))return 1;NSString*assets=@(argv[1]),*out=@(argv[2]);
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(d.registryID==4294968458&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"])device=d;
 if(!device)return 2;
 NSDictionary*manifest=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"native-allocation-manifest.json"]]options:0 error:nil];
 NSData*library=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"control_flow.metallib"]];
 NSDictionary*entry=manifest[@"certificates"][@"depth96"];
 NSData*certificate=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:entry[@"file"]]];
 NSDictionary*cas=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"concurrent-cas-manifest.json"]]options:0 error:nil];
 NSData*casLibrary=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:cas[@"library"]]];
 NSDictionary*profile=cas[@"profile"];NSData*casCertificate=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:profile[@"certificate"]]];
 GateState gate;gate.method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));
 if(!gate.method)return 2;gate.baseline=method_getImplementation(gate.method);
 id<MTLDevice>proxy=(id<MTLDevice>)[KPAllocationGateDevice device:device gate:&gate];PipelineResult r[3];
 std::thread allocation([&]{@autoreleasepool{
  @try{NSError*error=nil;NSDictionary*proof=nil;r[0].pipeline=KPCreateCertifiedNativeAllocationPipeline(proxy,library,manifest[@"library_sha256"],certificate,entry[@"SHA256"],&error,&proof);r[0].proof=proof;r[0].error=error.description?:@"";}
  @catch(NSException*e){r[0].error=e.reason;}
 }});
 std::thread legacy([&]{@autoreleasepool{
  if(!awaitGate(gate)){r[1].error=@"Gate not entered";return;}
  [gate.condition lock];gate.legacyStarted=true;[gate.condition broadcast];[gate.condition unlock];
  @try{NSError*error=nil;NSDictionary*proof=nil;r[1].pipeline=KPCreateCertifiedNativeCASPipeline(device,casLibrary,cas[@"library_SHA256"],casCertificate,profile[@"certificate_SHA256"],&error,&proof);r[1].proof=proof;r[1].error=error.description?:@"";}
  @catch(NSException*e){r[1].error=e.reason;}
  [gate.condition lock];gate.legacyDone=true;[gate.condition broadcast];[gate.condition unlock];
 }});
 std::thread native([&]{@autoreleasepool{
  if(!awaitGate(gate)){r[2].error=@"Gate not entered";return;}
  @try{NSError*error=nil;r[2].pipeline=plain(device,library,@"depth0",&error);r[2].error=error.description?:@"";}
  @catch(NSException*e){r[2].error=e.reason;}
  [gate.condition lock];gate.nativeDone=true;[gate.condition broadcast];[gate.condition unlock];
 }});
 allocation.join();legacy.join();native.join();
 BOOL restored=method_getImplementation(gate.method)==gate.baseline;
 BOOL valid=r[0].pipeline&&r[1].pipeline&&r[2].pipeline&&restored&&gate.hookSeen&&gate.blocked&&!gate.timedOut
  &&[r[0].proof[@"contract_verified"]boolValue]&&[r[0].proof[@"unrelated_constructor_passthrough_calls"]unsignedIntValue]>0
  &&[r[1].proof[@"native_import"][@"contract_verified"]boolValue];
 NSMutableArray*runs=[NSMutableArray array];
 if(valid){NSDictionary*a=KPRunAllocationKernel(device,r[0].pipeline,out,@"concurrent-native96",96);
  NSDictionary*b=runCAS(device,r[1].pipeline,out,profile);NSDictionary*c=KPRunAllocationKernel(device,r[2].pipeline,out,@"concurrent-unrelated0",0);
  valid=a&&b&&c;if(valid)[runs addObjectsFromArray:@[a,b,c]];}
 NSDictionary*result=@{@"mode":@"concurrent",@"status":valid?@"PASS":@"FAIL",@"device":device.name,@"registry_id":@(device.registryID),
  @"constructor_restored":@(restored),@"hook_seen_at_gate":@(gate.hookSeen),@"legacy_blocked_during_gate":@(gate.blocked),
  @"gate_timeout":@(gate.timedOut),@"allocation":r[0].proof?:@{},@"CAS":r[1].proof?:@{},
  @"errors":@[r[0].error?:@"",r[1].error?:@"",r[2].error?:@""],@"runs":runs,
  @"CPU_expected_answers_uploaded":@NO,@"system_modified":@NO,@"performance_benchmark":@NO};
 NSData*data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(data.bytes,1,data.length,stdout);puts("");return valid?0:3;
}}
