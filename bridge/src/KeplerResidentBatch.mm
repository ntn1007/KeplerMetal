// SPDX-License-Identifier: MIT
#import "KeplerResidentBatch.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <mach/vm_region.h>
#include <cstdint>
#include <cstring>

// These getters belong to our own unchanged SDK classes, not the driver.
@protocol KPBatchSlot
@property(nonatomic,readonly) KPRecordedNativeCompute *record;
@property(nonatomic,readonly) NSDictionary *bindings;
@property(nonatomic,readonly) BOOL barrier;
@end
@protocol KPBatchScopeState
@property(nonatomic,readonly) BOOL restored;
@end

namespace {
BOOL fail(NSError **error,NSString *text) {
 if(error)*error=[NSError errorWithDomain:@"KeplerResidentBatch" code:1
   userInfo:@{NSLocalizedDescriptionKey:text}];
 return NO;
}
void check(BOOL ok,NSString *text) {
 if(!ok)@throw [NSException exceptionWithName:@"KPResidentBatchRefusal" reason:text userInfo:nil];
}
NSString *sha(NSData *data) {
 unsigned char digest[32];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *s=[NSMutableString new];for(auto x:digest)[s appendFormat:@"%02x",x];return s;
}
NSData *memory(uintptr_t p,size_t n) {
 if(!p||!n||n>65536)return nil;
 NSMutableData *d=[NSMutableData dataWithLength:n];mach_vm_size_t got=0;
 return mach_vm_read_overwrite(mach_task_self(),p,n,(mach_vm_address_t)d.mutableBytes,&got)==KERN_SUCCESS&&got==n?d:nil;
}
uint64_t u64(NSData *d,size_t o) {uint64_t v=0;if(o+8<=d.length)memcpy(&v,(const char*)d.bytes+o,8);return v;}
uint32_t u32(NSData *d,size_t o) {uint32_t v=0;if(o+4<=d.length)memcpy(&v,(const char*)d.bytes+o,4);return v;}
NSArray *words(NSData *d) {
 NSMutableArray *a=[NSMutableArray new];for(NSUInteger i=0;i<d.length;i+=4)[a addObject:@(u32(d,i))];return a;
}
struct Cursor {uintptr_t push,current,end;};
Cursor cursor(id<MTLComputeCommandEncoder> e) {
 Cursor c{};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");
 if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;
 uintptr_t impl=0;memcpy(&impl,(const char*)(__bridge const void*)e+120,8);
 c.push=u64(memory(impl,64),32);NSData *p=memory(c.push,144);
 c.current=u64(p,0);c.end=u64(p,136);return c;
}
BOOL writable(uintptr_t p,size_t n) {
 if(!p||!n||p+n<p)return NO;
 mach_vm_address_t a=p;mach_vm_size_t size=0;vm_region_basic_info_data_64_t info{};
 mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=MACH_PORT_NULL;
 kern_return_t result=mach_vm_region(mach_task_self(),&a,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);
 if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
 return result==KERN_SUCCESS&&a<=p&&p+n<=a+size&&(info.protection&VM_PROT_WRITE);
}
BOOL overlaps(NSDictionary *a,NSDictionary *b) {
 return [a[@"begin"]unsignedLongLongValue]<[b[@"end"]unsignedLongLongValue]&&
   [b[@"begin"]unsignedLongLongValue]<[a[@"end"]unsignedLongLongValue];
}
NSDictionary *footprint(KPRecordedNativeCompute *r) {
 check(object_getClass(r)==KPRecordedNativeCompute.class&&r.residentDescriptorReady,@"Prepared exact SDK record required");
 NSDictionary *p=r.relocationEvidence;
 check([p[@"library_SHA256"]isEqual:@"479a0f85935823395174b25c0ead11482796389a5c8116cc7e5929d84ec0e7ed"]&&
   [@[@"observe_a",@"observe_b"]containsObject:p[@"function"]]&&
   [p[@"groups_shape"]isEqual:@[@1,@1,@1]]&&[p[@"local_shape"]isEqual:@[@1,@1,@1]]&&
   [p[@"native_register_count"]unsignedIntegerValue]==17&&[p[@"constant_buffer_valid_mask"]unsignedIntegerValue]==7&&
   [p[@"static_threadgroup_bytes"]unsignedIntegerValue]==0&&[p[@"dynamic_threadgroup_length"]unsignedIntegerValue]==0,
   @"Library/function/geometry footprint is not the qualified profile");
 check(r.originalCommands.length==464&&r.relocatedCommands.length==464&&r.constants.length==65536&&r.descriptor.length==4096&&
   r.constants.storageMode==MTLStorageModePrivate&&r.descriptor.storageMode==MTLStorageModePrivate,@"Native resident state profile differs");
 NSDictionary *literal=p[@"native_literal_bank_0"];
 check([literal[@"bytes"]unsignedIntegerValue]==256&&[literal[@"native_code_bytes"]unsignedIntegerValue]==2304&&
   [literal[@"variant_owner_retained"]boolValue],@"Original native literal/code owner missing");
 NSArray *bindings=p[@"bindings"];check(bindings.count==3,@"Three exact native bindings required");
 NSMutableArray *ranges=[NSMutableArray new];
 for(NSUInteger i=0;i<3;++i) {
  NSDictionary *b=bindings[i];uint64_t address=[b[@"GPU_address"]unsignedLongLongValue];
  uint64_t offset=[b[@"offset"]unsignedLongLongValue],length=[b[@"length"]unsignedLongLongValue];
  uint64_t bytes=i==0?12:i==1?32:16;
  check([b[@"index"]unsignedIntegerValue]==i&&address&&address<1ull<<40&&offset<=length&&bytes<=length-offset&&
    address+offset+bytes<1ull<<40&&[b[@"native_table_address"]unsignedLongLongValue]==address+offset,
    @"Native footprint bounds differ");
  [ranges addObject:@{@"begin":@(address+offset),@"end":@(address+offset+bytes),
    @"access":i==0?@"atomic":i==1?@"write":@"read",@"binding":@(i)}];
 }
 for(NSUInteger i=0;i<3;++i)for(NSUInteger j=i+1;j<3;++j)
   check(!overlaps(ranges[i],ranges[j]),@"A record aliases its own atomic/output/config footprint");
 return @{@"function":p[@"function"],@"descriptor":@(r.descriptor.gpuAddress),
   @"constants":@(r.constants.gpuAddress),@"ranges":ranges};
}
}

@interface KPResidentBatch ()
- (instancetype)initWithScope:(KPCPUICBScope *)scope records:(NSArray *)records
                     barriers:(NSIndexSet *)barriers parameters:(NSArray *)parameters evidence:(NSDictionary *)evidence;
@end
@implementation KPResidentBatch {
 KPCPUICBScope *_scope;
 NSArray<KPRecordedNativeCompute *> *_records;
 NSIndexSet *_barriers;
 NSDictionary *_planEvidence;
 NSArray *_parameters;
}
- (instancetype)initWithScope:(KPCPUICBScope *)scope records:(NSArray *)records
                     barriers:(NSIndexSet *)barriers parameters:(NSArray *)parameters evidence:(NSDictionary *)evidence {
 if((self=[super init])){_scope=scope;_records=[records copy];_barriers=[barriers copy];_parameters=[parameters copy];_planEvidence=[evidence copy];}return self;
}
- (NSArray *)records{return _records;}
- (NSDictionary *)planEvidence{return _planEvidence;}
+ (instancetype)prepareScope:(KPCPUICBScope *)scope buffer:(id<MTLIndirectCommandBuffer>)buffer
                     indices:(NSArray<NSNumber *> *)indices barrierBefore:(NSIndexSet *)barriers error:(NSError **)error {
 @try {
  check(scope&&buffer&&indices.count>=1&&indices.count<=4&&barriers,@"A nonempty bounded batch and explicit barriers are required");
  check(![barriers containsIndex:0]&&(barriers.lastIndex==NSNotFound||barriers.lastIndex<indices.count),@"Barrier position is outside the batch");
  NSArray *selected=[indices copy];NSMutableIndexSet *boundaries=[barriers mutableCopy];
  for(NSNumber *n in selected)check([n isKindOfClass:NSNumber.class]&&n.doubleValue==(double)n.unsignedIntegerValue&&n.unsignedIntegerValue<buffer.size,@"ICB slot index is outside the owned buffer");
  for(NSNumber *n in selected) {
   NSError *inner=nil;BOOL ok=[scope prepareResidentComputeCommands:buffer range:NSMakeRange(n.unsignedIntegerValue,1) error:&inner];
   check(ok,inner.localizedDescription?:@"Owned preparation failed");
  }
  NSMutableArray *records=[NSMutableArray new],*rows=[NSMutableArray new],*barrierRows=[NSMutableArray new],*parameters=[NSMutableArray new],*slotBarriers=[NSMutableArray new];
  for(NSNumber *n in selected) {
   id slot=[buffer indirectComputeCommandAtIndex:n.unsignedIntegerValue];
   check([slot respondsToSelector:@selector(record)],@"Owned SDK slot record missing");
   if([(id<KPBatchSlot>)slot barrier]&&records.count){[boundaries addIndex:records.count];[slotBarriers addObject:@(records.count)];}
   KPRecordedNativeCompute *r=[(id<KPBatchSlot>)slot record];[rows addObject:footprint(r)];[records addObject:r];
   NSDictionary *binding=[(id<KPBatchSlot>)slot bindings][@2];id<MTLBuffer>parameter=binding[@"buffer"];
   NSUInteger offset=[binding[@"offset"]unsignedIntegerValue];
   check(parameter.contents&&offset<=parameter.length&&parameter.length-offset>=16&&
     parameter.gpuAddress+offset==[r.relocationEvidence[@"bindings"][2][@"native_table_address"]unsignedLongLongValue],@"Retained CPU-readable bounded config required");
   [parameters addObject:@{@"buffer":parameter,@"offset":@(offset)}];
  }
  for(NSUInteger i=0;i<records.count;++i)for(KPRecordedNativeCompute *r in records)for(NSDictionary *range in rows[i][@"ranges"])
   if(![range[@"access"]isEqual:@"read"])for(id<MTLBuffer>state in @[r.descriptor,r.constants])
     check(!overlaps(range,@{@"begin":@(state.gpuAddress),@"end":@(state.gpuAddress+state.length)}),@"Kernel writes alias resident descriptor/constant state");
  NSUInteger start=0;
  for(NSUInteger i=0;i<records.count;++i) {
   if([boundaries containsIndex:i]){start=i;[barrierRows addObject:@(i)];}
   for(NSUInteger j=start;j<i;++j) {
    check(records[j]!=records[i]&&![rows[j][@"descriptor"]isEqual:rows[i][@"descriptor"]],@"A concurrent segment repeats resident descriptor state");
    for(NSDictionary *a in rows[j][@"ranges"])for(NSDictionary *b in rows[i][@"ranges"]) {
     if(!overlaps(a,b))continue;
     BOOL reads=[a[@"access"]isEqual:@"read"]&&[b[@"access"]isEqual:@"read"];
     BOOL atomics=[a[@"access"]isEqual:@"atomic"]&&[b[@"access"]isEqual:@"atomic"]&&
       [a[@"begin"]isEqual:b[@"begin"]]&&[a[@"end"]isEqual:b[@"end"]];
     check(reads||atomics,@"Concurrent segment has a non-atomic or partial-atomic alias");
    }
   }
  }
  NSDictionary *proof=@{@"record_indices":selected,@"barrier_before_positions":barrierRows,@"source_slot_barrier_positions":slotBarriers,@"footprints":rows,
    @"snapshot_of_records":@YES,@"max_entries":@4,@"scope":@"Explicit pinned native profile; not an ordinary Metal encoder"};
  NSData *json=[NSJSONSerialization dataWithJSONObject:proof options:0 error:nil];
  NSDictionary *immutable=[NSJSONSerialization JSONObjectWithData:json options:0 error:nil];
  return [[self alloc]initWithScope:scope records:records barriers:boundaries parameters:parameters evidence:immutable];
 } @catch(NSException *x) {fail(error,x.reason);return nil;}
}
- (BOOL)encodeToCommandBuffer:(id<MTLCommandBuffer>)cb evidence:(NSDictionary **)evidence error:(NSError **)error {
 if(evidence)*evidence=nil;
 if([(id<KPBatchScopeState>)_scope restored]||!cb||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)
   return fail(error,@"Active scope and new retained command buffer required");
 id<MTLComputeCommandEncoder>encoder=nil;
 @try {
  for(NSDictionary *binding in _parameters) {
   id<MTLBuffer>buffer=binding[@"buffer"];NSUInteger offset=[binding[@"offset"]unsignedIntegerValue];uint32_t words[4];
   check(buffer.contents&&offset<=buffer.length&&buffer.length-offset>=16,@"Retained config unavailable");
   memcpy(words,(const char*)buffer.contents+offset,16);
   check(words[0]==4096&&words[2]==128&&words[3]==0,@"Config changed outside bounded qualified workload");
  }
  encoder=[cb computeCommandEncoder];check(encoder&&encoder.dispatchType==MTLDispatchTypeSerial,@"Native serial carrier required");
  NSData *original=nil,*candidate=nil;uintptr_t start=0;NSDictionary *transport=nil;NSMutableArray *changed=[NSMutableArray new];
  @try {
   for(NSUInteger i=0;i<_records.count;++i)check([footprint(_records[i])isEqual:_planEvidence[@"footprints"][i]],@"Retained record footprint changed");
   NSError *inner=nil;BOOL ok=[_records[0]encodeResidentSequence:_records owners:[NSOrderedSet orderedSetWithArray:_records].array
     encoder:encoder suppressElementIndexes:[NSIndexSet indexSet] evidence:&transport error:&inner];
   check(ok,inner.localizedDescription?:@"Resident encoding failed");
   Cursor c=cursor(encoder);NSUInteger length=_records.count*24;
   check(c.push&&c.current>=length&&c.current<c.end&&cb.status==MTLCommandBufferStatusNotEnqueued,@"Native returned cursor/buffer state differs");
   start=c.current-length;original=memory(start,length);NSMutableData *expected=[NSMutableData new];
   for(KPRecordedNativeCompute *r in _records)[expected appendData:[r.relocatedCommands subdataWithRange:NSMakeRange(440,24)]];
   check([original isEqual:expected]&&[sha(original)isEqual:transport[@"stream_SHA256"]]&&
     [transport[@"command_bytes"]unsignedIntegerValue]==length&&writable(start,length),@"Exact native stream boundary/readback/protection differs");
   NSMutableData *next=[original mutableCopy];
   for(NSUInteger i=0;i+1<_records.count;++i)if(![_barriers containsIndex:i+1]) {
    NSUInteger offset=24*i+16;check(u32(next,offset)==0x20012044&&u32(next,offset+4)==0,@"Native wait template differs");
    uint32_t nop=0x20012040;memcpy((char*)next.mutableBytes+offset,&nop,4);[changed addObject:@(offset)];
   }
   check(u32(next,length-8)==0x20012044&&u32(next,length-4)==0,@"Final native wait missing");
   for(NSNumber *n in changed){uint32_t nop=0x20012040;memcpy((void*)(start+n.unsignedIntegerValue),&nop,4);}
   candidate=memory(start,length);check([candidate isEqual:next]&&cursor(encoder).current==c.current,@"Only qualified wait headers may change");
  } @finally {[encoder endEncoding];encoder=nil;}
  check([memory(start,candidate.length)isEqual:candidate],@"Native endEncoding changed candidate bytes");
  if(evidence)*evidence=@{@"plan":_planEvidence,@"transport":transport,@"original_stream_SHA256":sha(original),
    @"candidate_stream_SHA256":sha(candidate),@"original_stream_words":words(original),@"candidate_stream_words":words(candidate),
    @"changed_word_offsets":changed,@"terminal_wait_retained":@YES,@"native_encoder_dispatch_type":@0,
    @"carrier_encoder_ended":@YES,@"system_modified":@NO,@"ordinary_concurrent_API":@NO};
  return YES;
 } @catch(NSException *x) {if(encoder){@try{[encoder endEncoding];}@catch(NSException *ignored){(void)ignored;}}return fail(error,x.reason);}
}
@end
