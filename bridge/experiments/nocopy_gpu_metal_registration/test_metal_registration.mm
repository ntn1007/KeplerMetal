// SPDX-License-Identifier: MIT
// Mocked Metal callback contract: no real command buffer and no GPU dispatch.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cassert>
#include <atomic>
#include <thread>
#include <vector>
#include "metal_registration.h"
@interface KMFakeBuffer : NSObject
@property MTLCommandBufferStatus status;
@property(copy) void (^handler)(id<MTLCommandBuffer>);
- (void)addCompletedHandler:(void (^)(id<MTLCommandBuffer>))handler;
- (void)finish:(MTLCommandBufferStatus)status;
@end
@implementation KMFakeBuffer
- (void)addCompletedHandler:(void (^)(id<MTLCommandBuffer>))handler {self.handler=handler;}
- (void)finish:(MTLCommandBufferStatus)status {self.status=status;self.handler((id<MTLCommandBuffer>)self);}
@end
@interface KMThrowingBuffer : KMFakeBuffer @end
@implementation KMThrowingBuffer
- (void)addCompletedHandler:(void (^)(id<MTLCommandBuffer>))handler {(void)handler;@throw [NSException exceptionWithName:@"Synthetic" reason:@"Registration failure" userInfo:nil];}
@end
int main(){@autoreleasepool {
 using namespace kepler_witness;
 RaceGate gate;KMMetalWorkRegistrar *reg=[[KMMetalWorkRegistrar alloc] initWithGate:&gate];assert(reg);
 KMFakeBuffer *one=[KMFakeBuffer new],*two=[KMFakeBuffer new],*late=[KMFakeBuffer new],*busy=[KMFakeBuffer new];busy.status=MTLCommandBufferStatusCommitted;
 __block unsigned completions=0,delivered=0,failures=0,duplicates=0;
 KMWorkCompletion sink=^(Decision d,bool ok){completions++;if(d==Decision::deliver)delivered++;if(!ok)failures++;if(d==Decision::duplicate)duplicates++;};
 assert(![reg registerBuffer:(id<MTLCommandBuffer>)one completion:nil]);
 assert(![reg registerBuffer:nil completion:sink]);assert(![reg registerBuffer:(id<MTLCommandBuffer>)busy completion:sink]);
 assert([reg registerBuffer:(id<MTLCommandBuffer>)one completion:sink]);assert(![reg registerBuffer:(id<MTLCommandBuffer>)one completion:sink]);assert([reg registerBuffer:(id<MTLCommandBuffer>)two completion:sink]);
 assert([reg seal]==Decision::waiting && [reg seal]==Decision::duplicate);assert(![reg registerBuffer:(id<MTLCommandBuffer>)late completion:sink]);
 assert(gate.root()==Decision::waiting && gate.root_returned()==Decision::waiting && gate.result(true)==Decision::waiting);
 [one finish:MTLCommandBufferStatusCompleted];assert(completions==1 && delivered==0);[two finish:MTLCommandBufferStatusCompleted];assert(completions==2 && delivered==1 && failures==0);
 [two finish:MTLCommandBufferStatusCompleted];assert(duplicates==1 && delivered==1);
 RaceGate concurrent;KMMetalWorkRegistrar *parallel=[[KMMetalWorkRegistrar alloc] initWithGate:&concurrent];NSMutableArray<KMFakeBuffer*> *items=[NSMutableArray array];for(unsigned i=0;i<16;i++)[items addObject:[KMFakeBuffer new]];
 std::atomic<unsigned> registered{0};std::vector<std::thread> threads;for(KMFakeBuffer *f in items)threads.emplace_back([&,f]{@autoreleasepool {if([parallel registerBuffer:(id<MTLCommandBuffer>)f completion:sink])registered++;}});
 for(auto &thread:threads)thread.join();assert(registered==16);assert([parallel seal]==Decision::waiting);assert(concurrent.root()==Decision::waiting && concurrent.root_returned()==Decision::waiting && concurrent.result(true)==Decision::waiting);
 unsigned oldDelivered=delivered;for(KMFakeBuffer *f in items)[f finish:MTLCommandBufferStatusCompleted];assert(delivered==oldDelivered+1);
 RaceGate thrown;KMMetalWorkRegistrar *throws=[[KMMetalWorkRegistrar alloc] initWithGate:&thrown];KMThrowingBuffer *throwsBuffer=[KMThrowingBuffer new];
 assert(![throws registerBuffer:(id<MTLCommandBuffer>)throwsBuffer completion:sink]);assert([throws seal]==Decision::rejected);assert(thrown.root()==Decision::rejected && thrown.result(true)==Decision::rejected);
 RaceGate bad;KMMetalWorkRegistrar *badreg=[[KMMetalWorkRegistrar alloc] initWithGate:&bad];KMFakeBuffer *failed=[KMFakeBuffer new];__block Decision failure=Decision::waiting;
 assert([badreg registerBuffer:(id<MTLCommandBuffer>)failed completion:^(Decision d,bool ok){failure=d;assert(!ok);}]);assert([badreg seal]==Decision::waiting);
 [failed finish:MTLCommandBufferStatusError];assert(failure==Decision::rejected);assert(bad.root()==Decision::rejected && bad.root_returned()==Decision::rejected && bad.result(true)==Decision::rejected);
 }}
