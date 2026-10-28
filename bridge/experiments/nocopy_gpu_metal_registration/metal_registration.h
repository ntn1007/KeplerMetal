// SPDX-License-Identifier: MIT
// Opt-in registration; caller must serialize registration with command-buffer commit.
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "race_gate.h"
typedef void (^KMWorkCompletion)(kepler_witness::Decision,bool);
@interface KMMetalWorkRegistrar : NSObject {
 @private kepler_witness::RaceGate *_gate; NSMutableSet<NSValue*> *_seen; BOOL _closed;
}
- (instancetype)initWithGate:(kepler_witness::RaceGate*)gate;
- (BOOL)registerBuffer:(id<MTLCommandBuffer>)buffer completion:(KMWorkCompletion)completion;
- (kepler_witness::Decision)seal;
@end
@implementation KMMetalWorkRegistrar
- (instancetype)initWithGate:(kepler_witness::RaceGate*)gate {
 if(!gate)return nil;if((self=[super init])){_gate=gate;_seen=[NSMutableSet new];_closed=NO;}return self;
}
- (BOOL)registerBuffer:(id<MTLCommandBuffer>)buffer completion:(KMWorkCompletion)completion {
 @synchronized(self) {
  if(_closed||!buffer||!completion||buffer.status!=MTLCommandBufferStatusNotEnqueued)return NO;
  NSValue *identity=[NSValue valueWithPointer:(__bridge const void*)buffer];if([_seen containsObject:identity])return NO;
  uint64_t token=_gate->register_work();if(!token)return NO;
  [_seen addObject:identity];kepler_witness::RaceGate *gate=_gate;
  @try {
   [buffer addCompletedHandler:^(id<MTLCommandBuffer> finished){
    bool success=finished.status==MTLCommandBufferStatusCompleted;
    auto decision=gate->complete(token,success);completion(decision,success);
   }];
  } @catch(NSException *exception) { (void)exception;gate->complete(token,false);return NO; }
  return YES;
 }
}
- (kepler_witness::Decision)seal {
 @synchronized(self) {if(_closed)return kepler_witness::Decision::duplicate;_closed=YES;return _gate->seal();}
}
@end
