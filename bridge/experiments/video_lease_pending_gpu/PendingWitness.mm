// SPDX-License-Identifier: MIT
#import "PendingWitness.h"
#include <atomic>
#include <memory>
#include <cstdint>
static constexpr uint32_t Count=4096, Guard=16, Sentinel=0xa5f0c3d2u, Seed=0x12345678u;
static NSString *const Source=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void witness(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {if(i<4096)out[i]=(i*1664525u)^0x12345678u;}\n";
@implementation PendingWitness {
 id<MTLDevice> _device; NSString *_directory; BOOL _skip;
 id<MTLSharedEvent> _gate; id<MTLBuffer> _buffer; id<MTLCommandBuffer> _command;
 std::shared_ptr<std::atomic<int>> _gateState;
}
- (instancetype)initWithDevice:(id<MTLDevice>)device directory:(NSString*)directory skip:(BOOL)skip {
 if((self=[super init])){_device=device;_directory=[directory copy];_skip=skip;_gateState=std::make_shared<std::atomic<int>>(0);}return self;
}
- (BOOL)begin {
 NSError *err=nil;id<MTLLibrary> lib=[_device newLibraryWithSource:Source options:nil error:&err];
 id<MTLFunction> fn=[lib newFunctionWithName:@"witness"];id<MTLComputePipelineState> pipeline=fn?[_device newComputePipelineStateWithFunction:fn error:&err]:nil;
 id<MTLCommandQueue> queue=pipeline?[_device newCommandQueue]:nil;_gate=queue?[_device newSharedEvent]:nil;
 _buffer=_gate?[_device newBufferWithLength:(Count+2*Guard)*sizeof(uint32_t) options:MTLResourceStorageModeShared]:nil;
 if(!_buffer||!_buffer.contents)return NO;
 uint32_t *v=(uint32_t*)_buffer.contents;for(unsigned i=0;i<Count+2*Guard;i++)v[i]=Sentinel;
 _gate.signaledValue=0;_command=[queue commandBuffer];if(!_command)return NO;
 [_command encodeWaitForEvent:_gate value:1];
 if(!_skip){id<MTLComputeCommandEncoder> enc=[_command computeCommandEncoder];if(!enc)return NO;[enc setComputePipelineState:pipeline];[enc setBuffer:_buffer offset:Guard*sizeof(uint32_t) atIndex:0];[enc dispatchThreadgroups:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];[enc endEncoding];}
 auto state=_gateState;id<MTLSharedEvent>gate=_gate;
 dispatch_after(dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC),dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{int old=0;if(state->compare_exchange_strong(old,2))gate.signaledValue=1;});
 [_command commit];return YES;
}
- (NSDictionary*)snapshot {
 uint32_t changes=0;if(_buffer&&_buffer.contents){uint32_t*v=(uint32_t*)_buffer.contents;for(unsigned i=0;i<Count+2*Guard;i++)changes+=(v[i]!=Sentinel);}
 return @{@"command_status":@(_command?_command.status:0),@"gate_value":@(_gate?_gate.signaledValue:0),@"watchdog_state":@(_gateState->load()),@"changed_words":@(changes)};
}
- (NSDictionary*)finish {
 int old=0;BOOL signaled=_gateState->compare_exchange_strong(old,1);if(signaled)_gate.signaledValue=1;
 if(_command)[_command waitUntilCompleted];unsigned errors=0,guards=0;BOOL written=NO;
 if(_buffer&&_buffer.contents){uint32_t*v=(uint32_t*)_buffer.contents;for(unsigned i=0;i<Count;i++)errors+=v[Guard+i]!=(_skip?Sentinel:(i*1664525u)^Seed);for(unsigned i=0;i<Guard;i++){guards+=v[i]!=Sentinel;guards+=v[Count+Guard+i]!=Sentinel;}
 NSData*d=[NSData dataWithBytes:v length:(Count+2*Guard)*sizeof(uint32_t)];written=[d writeToFile:[_directory stringByAppendingPathComponent:@"pending-compute.bin"] atomically:NO];}
 return @{@"normal_signal":@(signaled),@"watchdog_state":@(_gateState->load()),@"gate_value":@(_gate?_gate.signaledValue:0),@"command_status":@(_command?_command.status:0),@"dispatch_encoded":@(!_skip),@"errors":@(errors),@"guard_errors":@(guards),@"written":@(written)};
}
@end
