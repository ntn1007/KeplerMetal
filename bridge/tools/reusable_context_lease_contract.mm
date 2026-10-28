// SPDX-License-Identifier: MIT
// CPU-only tests against the actual lease implementation, using explicit mocks.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
@class KPGPUCommandSelection;
static BOOL fail(NSError**e,NSString*s){if(e)*e=[NSError errorWithDomain:@"lease-contract" code:1 userInfo:@{NSLocalizedDescriptionKey:s}];return NO;}
#include "KeplerReusableIRContext.inc"
@interface KPLeaseMockBuffer:NSObject
@property(nonatomic,strong) id<MTLCommandQueue> commandQueue;
@property(nonatomic) MTLCommandBufferStatus status;
@property(nonatomic) BOOL retainedReferences;
@property(nonatomic,strong) NSMutableArray *handlers;
- (void)addCompletedHandler:(MTLCommandBufferHandler)handler;
- (void)finish:(MTLCommandBufferStatus)status;
@end
@implementation KPLeaseMockBuffer
- (instancetype)init{if((self=[super init])){_handlers=[NSMutableArray new];_retainedReferences=YES;}return self;}
- (void)addCompletedHandler:(MTLCommandBufferHandler)handler{[_handlers addObject:[handler copy]];}
- (void)finish:(MTLCommandBufferStatus)status{_status=status;for(MTLCommandBufferHandler h in [_handlers copy])h((id<MTLCommandBuffer>)self);[_handlers removeAllObjects];}
@end
int main(){@autoreleasepool{
 NSMutableArray*rows=[NSMutableArray new];auto check=[&](NSString*n,BOOL ok){[rows addObject:@{@"case":n,@"PASS":@(ok)}];if(!ok)fprintf(stderr,"FAIL: %s\n",n.UTF8String);return ok;};
 id<MTLCommandQueue>q=(id)[NSObject new];KPReusableIRContext*s=[KPReusableIRContext new];s.queue=q;s.generation=7;s.retired=NO;KPLeaseMockBuffer*b=[KPLeaseMockBuffer new];b.commandQueue=q;NSError*e=nil;
 if(!check(@"initial_reservation",[s track:(id)b generation:7 error:&e]&&s.pending.count==1))return 1;
 if(!check(@"duplicate_reservation_has_one_handler",[s track:(id)b generation:7 error:&e]&&b.handlers.count==1))return 1;
 for(unsigned status=0;status<4;status++){b.status=(MTLCommandBufferStatus)status;e=nil;if(!check([NSString stringWithFormat:@"busy_status_%u",status],![s idle:&e]&&e&&![s retire:nil]))return 1;}
 [b finish:MTLCommandBufferStatusCompleted];if(!check(@"completion_releases",[s idle:&e]&&s.pending.count==0&&[s retire:nil]))return 1;
 b.status=MTLCommandBufferStatusNotEnqueued;e=nil;if(!check(@"retired_generation_refused",![s track:(id)b generation:7 error:&e]&&e))return 1;
 s.retired=NO;s.generation=8;e=nil;if(!check(@"old_generation_refused",![s track:(id)b generation:7 error:&e]&&e))return 1;
 b.commandQueue=(id)[NSObject new];e=nil;if(!check(@"foreign_queue_refused",![s track:(id)b generation:8 error:&e]&&e))return 1;b.commandQueue=q;
 b.retainedReferences=NO;e=nil;if(!check(@"unretained_buffer_refused",![s track:(id)b generation:8 error:&e]&&e))return 1;b.retainedReferences=YES;
 __block BOOL otherThreadAllowed=YES;dispatch_semaphore_t other=dispatch_semaphore_create(0);dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{otherThreadAllowed=[s track:(id)b generation:8 error:nil];dispatch_semaphore_signal(other);});if(dispatch_semaphore_wait(other,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC)))return 1;if(!check(@"foreign_thread_refused",!otherThreadAllowed))return 1;
 if(![s track:(id)b generation:8 error:&e])return 1;[b finish:MTLCommandBufferStatusError];if(!check(@"error_poisoned",s.poisoned&&![s idle:nil]&&![s retire:nil]))return 1;
 // Completion callback for an already swept CB must not clear a new frame's CB.
 KPReusableIRContext*t=[KPReusableIRContext new];t.queue=q;t.retired=NO;t.generation=9;KPLeaseMockBuffer*old=[KPLeaseMockBuffer new];old.commandQueue=q;[t track:(id)old generation:9 error:nil];old.status=MTLCommandBufferStatusCompleted;if(![t idle:nil])return 1;
 t.generation=10;KPLeaseMockBuffer*current=[KPLeaseMockBuffer new];current.commandQueue=q;[t track:(id)current generation:10 error:nil];[old finish:MTLCommandBufferStatusCompleted];if(!check(@"late_callback_preserves_new_pending",t.pending.count==1&&![t idle:nil]))return 1;[current finish:MTLCommandBufferStatusCompleted];
 __weak KPReusableIRContext*weak=nil;KPLeaseMockBuffer*held=[KPLeaseMockBuffer new];held.commandQueue=q;
 @autoreleasepool{KPReusableIRContext*u=[KPReusableIRContext new];u.queue=q;u.retired=NO;u.generation=11;weak=u;[u track:(id)held generation:11 error:nil];}
 if(!check(@"pending_keeps_lease_alive",weak!=nil))return 1;[held finish:MTLCommandBufferStatusCompleted];if(!check(@"completion_releases_unowned_lease",weak==nil))return 1;
 // One command buffer can belong to multiple contexts. Sweeping one owner
 // must not erase another when its completion callback has not run yet.
 KPReusableIRContext*left=[KPReusableIRContext new],*right=[KPReusableIRContext new];left.queue=q;right.queue=q;left.retired=NO;right.retired=NO;left.generation=21;right.generation=22;
 KPLeaseMockBuffer*shared=[KPLeaseMockBuffer new];shared.commandQueue=q;
 if(![left track:(id)shared generation:21 error:nil]||![right track:(id)shared generation:22 error:nil])return 1;
 if(!check(@"shared_owner_registry",KPReusableOwners(shared,NO).count==2))return 1;
 shared.status=MTLCommandBufferStatusCompleted;if(![left idle:nil]||!check(@"swept_owner_preserves_other",KPReusableOwners(shared,NO).count==1&&[KPReusableOwners(shared,NO)containsObject:right]))return 1;
 [shared finish:MTLCommandBufferStatusCompleted];if(!check(@"completion_clears_shared_owner",KPReusableOwners(shared,NO).count==0&&[right idle:nil]))return 1;
 KPReusableIRContext*refusal=[KPReusableIRContext new];refusal.queue=q;refusal.retired=NO;refusal.generation=23;KPGPUCommandSelection*dummy=(id)[NSObject new];refusal.plan=dummy;KPLeaseMockBuffer*unqualified=[KPLeaseMockBuffer new];unqualified.commandQueue=q;
 if(![refusal track:(id)unqualified generation:23 error:nil]||!check(@"non_native_refused_without_untracking",![refusal abandonExclusiveProducer:(id)unqualified generation:23 plan:dummy error:nil]&&refusal.pending.count==1&&KPReusableOwners(unqualified,NO).count==1))return 1;
 [unqualified finish:MTLCommandBufferStatusCompleted];
 NSDictionary*r=@{@"status":@"PASS",@"cases":rows,@"GPU_dispatches":@0,@"mock_command_buffers":@YES};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
