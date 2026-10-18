// SPDX-License-Identifier: MIT
#import "KeplerResidentBatch.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <unistd.h>

namespace {
constexpr uint32_t Poison=0xa53c6f09u;
struct Config {uint32_t limit,nonce,rounds,reserved;};
void check(bool ok,NSString *text){if(!ok)@throw [NSException exceptionWithName:@"KPBatchProbeFailure" reason:text userInfo:nil];}
NSString *sha(NSData *d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(auto v:h)[s appendFormat:@"%02x",v];return s;}
BOOL complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
NSArray *words(id<MTLBuffer>b){NSMutableArray*a=[NSMutableArray new];for(NSUInteger i=0;i<b.length/4;++i)[a addObject:@(((uint32_t*)b.contents)[i])];return a;}
uint32_t oracle(uint32_t nonce,unsigned role){uint32_t x=nonce^(role?0x85ebca6bu:0x9e3779b9u);for(unsigned i=0;i<128;++i)x=((x<<7)|(x>>25))*uint32_t(1664525)+uint32_t(1013904223)+i;return x;}
NSIndexSet *indexSet(NSArray *a){NSMutableIndexSet*s=[NSMutableIndexSet new];for(NSNumber*n in a)[s addIndex:n.unsignedIntegerValue];return s;}
}

int main(int argc,char **argv){@autoreleasepool{
 if(argc!=6)return 2;
 NSString *mode=@(argv[4]),*directory=@(argv[3]);unsigned trials=(unsigned)strtoul(argv[5],nullptr,10);
 if(![@[@"prepare",@"serial",@"segmented",@"parallel"]containsObject:mode]||!trials||trials>4)return 2;
 id<MTLDevice>device=nil;KPCPUICBScope *scope=nil;Class originalClass=nil;
 NSMutableDictionary *report=[@{@"status":@"ERROR",@"mode":mode,@"pid":@(getpid()),@"uid":@(getuid()),@"euid":@(geteuid()),
   @"user_compute_dispatches":@0,@"system_modified":@NO,@"common_runtime_modified":@NO,@"native_shader_changed":@NO,@"performance_benchmark":@NO}mutableCopy];
 @try {
  device=MTLCreateSystemDefaultDevice();check([device.name isEqual:@"NVIDIA GeForce GTX 880M"]&&device.registryID==4294968458,@"Pinned GPU required");
  originalClass=object_getClass(device);id<MTLCommandQueue>queue=[device newCommandQueue];check(queue!=nil,@"Queue missing");
  report[@"device"]=device.name;report[@"registry_id"]=@(device.registryID);
  NSData *library=[NSData dataWithContentsOfFile:@(argv[1])],*manifest=[NSData dataWithContentsOfFile:@(argv[2])];NSError *error=nil;
  scope=[KPCPUICBScope installOnDevice:device queue:queue libraryData:library expectedSHA256:sha(library) manifestData:manifest expectedManifestSHA256:sha(manifest) error:&error];
  check(scope!=nil,error.localizedDescription?:@"Registration failed");report[@"library_SHA256"]=sha(library);report[@"manifest_SHA256"]=sha(manifest);
  id<MTLBuffer>sync=[device newBufferWithLength:1024 options:MTLResourceStorageModeManaged];
  id<MTLBuffer>output=[device newBufferWithLength:2048 options:MTLResourceStorageModeManaged];
  id<MTLBuffer>params[4];for(unsigned i=0;i<4;++i)params[i]=[device newBufferWithLength:1024 options:MTLResourceStorageModeShared];
  check(sync&&output&&params[0]&&params[1]&&params[2]&&params[3],@"Witness resources unavailable");
  auto initialize=[&](uint32_t nonce) {
   for(id<MTLBuffer>b in @[sync,output])for(NSUInteger i=0;i<b.length/4;++i)((uint32_t*)b.contents)[i]=Poison;
   uint32_t*s=(uint32_t*)sync.contents;s[64]=s[65]=s[66]=0;
   for(unsigned i=0;i<4;++i){memset(params[i].contents,0xa5,1024);Config c{4096,nonce+37*i,128,0};memcpy((char*)params[i].contents+256,&c,16);}
   [sync didModifyRange:NSMakeRange(0,sync.length)];[output didModifyRange:NSMakeRange(0,output.length)];
  };
  auto synchronize=[&]() {
   id<MTLCommandBuffer>c=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[c blitCommandEncoder];
   [b synchronizeResource:sync];[b synchronizeResource:output];[b endEncoding];check(complete(c),@"Witness synchronization failed");
  };
  auto validate=[&](NSArray *indices,NSArray *barriers,uint32_t nonce)->NSDictionary* {
   const uint32_t*s=(const uint32_t*)sync.contents,*o=(const uint32_t*)output.contents;
   bool active[4]={};unsigned count=(unsigned)indices.count,bad=0,guards=0;
   for(NSNumber*n in indices){check(n.unsignedIntegerValue<4&&!active[n.unsignedIntegerValue],@"Probe oracle expects distinct entries");active[n.unsignedIntegerValue]=true;}
   if(s[64]!=2*count||s[65]!=unsigned(active[0]||active[2])||s[66]!=unsigned(active[1]||active[3]))++bad;
   for(unsigned i=0;i<256;++i)if((i<64||i>=67)&&s[i]!=Poison)++guards;
   bool used[512]={},tags[9]={};NSMutableArray *result=[NSMutableArray new];
   for(unsigned i=0;i<4;++i) {
    if(!active[i])continue;unsigned offset=64*(i+1);for(unsigned j=0;j<8;++j)used[offset+j]=true;
    const uint32_t*v=o+offset;
    if(v[0]<1||v[0]>=v[1]||v[1]>2*count||v[2]>1||v[3]<1||v[3]>4096||(!v[2]&&v[3]!=4096))++bad;
    for(unsigned j=0;j<2;++j){if(v[j]<1||v[j]>2*count||tags[v[j]])++bad;else tags[v[j]]=true;}
    if(!(i%2?(active[0]||active[2]):(active[1]||active[3]))&&v[2])++bad;
    uint32_t expectedNonce=nonce+37*i;
    if(v[4]!=oracle(expectedNonce,i%2)||v[5]!=expectedNonce||v[6]!=i%2||v[7]!=128)++bad;
    [result addObject:@{@"index":@(i),@"begin":@(v[0]),@"end":@(v[1]),@"seen":@(v[2]),@"iterations":@(v[3]),@"arithmetic":@(v[4])}];
   }
   for(unsigned tag=1;tag<=2*count;++tag)if(!tags[tag])++bad;
   for(unsigned i=0;i<512;++i)if(!used[i]&&o[i]!=Poison)++guards;
   for(unsigned i=0;i<4;++i){unsigned char expected[1024];memset(expected,0xa5,1024);Config c{4096,nonce+37*i,128,0};memcpy(expected+256,&c,16);if(memcmp(expected,params[i].contents,1024))++guards;}
   unsigned crossed=0,overlaps=0;
   for(NSUInteger i=0;i<indices.count;++i)for(NSUInteger j=i+1;j<indices.count;++j) {
    unsigned a=[indices[i]unsignedIntValue],b=[indices[j]unsignedIntValue];const uint32_t*x=o+64*(a+1),*y=o+64*(b+1);
    bool overlap=x[0]<y[1]&&y[0]<x[1];if(overlap)++overlaps;
    bool boundary=false;for(NSNumber*n in barriers)if(i<n.unsignedIntegerValue&&n.unsignedIntegerValue<=j)boundary=true;
    if(boundary&&x[1]>=y[0])++bad;
    if(i<2&&j>=2&&x[1]>=y[0])++crossed;
   }
   check(bad==0&&guards==0,@"Independent arithmetic/order/guard witness failed");
   return @{@"sync_words":words(sync),@"output_words":words(output),@"arithmetic_mismatches":@(bad),@"guard_mismatches":@(guards),
     @"active_dispatches":@(count),@"results":result,@"interleaved_pairs":@(overlaps),@"crossed_midpoint_pairs":@(crossed)};
  };
  initialize(710003);
  MTLIndirectCommandBufferDescriptor *desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;
  desc.maxKernelBufferBindCount=3;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
  id<MTLIndirectCommandBuffer>icb=[device newIndirectCommandBufferWithDescriptor:desc maxCommandCount:4 options:MTLResourceStorageModeShared];check(icb!=nil,@"Owned ICB missing");
  for(unsigned i=0;i<4;++i){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:i];[c setComputePipelineState:[scope pipelineForFunction:i%2?@"observe_b":@"observe_a"]];[c setKernelBuffer:sync offset:256 atIndex:0];[c setKernelBuffer:output offset:256*(i+1) atIndex:1];[c setKernelBuffer:params[i]offset:256 atIndex:2];[c concurrentDispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];}
  NSArray *specs=@[
   @{@"name":@"only-a",@"indices":@[@0],@"barriers":@[]},@{@"name":@"only-b",@"indices":@[@1],@"barriers":@[]},
   @{@"name":@"pair-serial-ab",@"indices":@[@0,@1],@"barriers":@[@1]},@{@"name":@"pair-serial-ba",@"indices":@[@1,@0],@"barriers":@[@1]},
   @{@"name":@"serial-ab",@"indices":@[@0,@1,@2,@3],@"barriers":@[@1,@2,@3]},@{@"name":@"serial-ba",@"indices":@[@3,@2,@1,@0],@"barriers":@[@1,@2,@3]},
   @{@"name":@"pair-parallel-ab",@"indices":@[@0,@1],@"barriers":@[]},@{@"name":@"pair-parallel-ba",@"indices":@[@1,@0],@"barriers":@[]},
   @{@"name":@"segmented-ab",@"indices":@[@0,@1,@2,@3],@"barriers":@[@2]},@{@"name":@"segmented-ba",@"indices":@[@3,@2,@1,@0],@"barriers":@[@2]},
   @{@"name":@"source-barrier-ab",@"indices":@[@0,@1,@2,@3],@"barriers":@[],@"source_position":@2},@{@"name":@"source-barrier-ba",@"indices":@[@3,@2,@1,@0],@"barriers":@[],@"source_position":@2},
   @{@"name":@"parallel-ab",@"indices":@[@0,@1,@2,@3],@"barriers":@[]},@{@"name":@"parallel-ba",@"indices":@[@3,@2,@1,@0],@"barriers":@[]}];
  NSMutableDictionary *plans=[NSMutableDictionary new],*planRows=[NSMutableDictionary new];
  for(NSDictionary *spec in specs) {
   for(unsigned i=0;i<4;++i)[[icb indirectComputeCommandAtIndex:i]clearBarrier];
   if(spec[@"source_position"]){NSUInteger slot=[spec[@"indices"][[spec[@"source_position"]unsignedIntegerValue]]unsignedIntegerValue];[[icb indirectComputeCommandAtIndex:slot]setBarrier];}
   NSMutableArray *indices=[spec[@"indices"]mutableCopy];NSMutableIndexSet *boundaries=[indexSet(spec[@"barriers"])mutableCopy];
   KPResidentBatch *plan=[KPResidentBatch prepareScope:scope buffer:icb indices:indices barrierBefore:boundaries error:&error];check(plan!=nil,error.localizedDescription?:@"Plan refused");
   [indices removeAllObjects];[boundaries addIndex:99];plans[spec[@"name"]]=plan;planRows[spec[@"name"]]=plan.planEvidence;
  }
  report[@"plans"]=planRows;
  NSArray<KPRecordedNativeCompute*> *records=((KPResidentBatch*)plans[@"serial-ab"]).records;
  NSMutableArray *backing=[NSMutableArray new],*rechecks=[NSMutableArray new];
  auto stateReadback=[&](NSString *label,BOOL initial) {
   for(unsigned i=0;i<4;++i) {
    KPRecordedNativeCompute*r=records[i];id<MTLBuffer>q=[device newBufferWithLength:256 options:MTLResourceStorageModeManaged],c=[device newBufferWithLength:65536 options:MTLResourceStorageModeManaged];
    id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromBuffer:r.descriptor sourceOffset:0 toBuffer:q destinationOffset:0 size:256];[blit copyFromBuffer:r.constants sourceOffset:0 toBuffer:c destinationOffset:0 size:65536];[blit synchronizeResource:q];[blit synchronizeResource:c];[blit endEncoding];check(complete(cb),@"Resident state readback failed");
    NSData *qd=[NSData dataWithBytes:q.contents length:256],*cd=[NSData dataWithBytes:c.contents length:65536];
    check([qd isEqual:[r.relocatedCommands subdataWithRange:NSMakeRange(184,256)]],@"GPU QMD differs from validated relocation");
    NSString *prefix=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"%@-%u",label,i]];
    check([qd writeToFile:[prefix stringByAppendingString:@".QMD.bin"]atomically:YES]&&[cd writeToFile:[prefix stringByAppendingString:@".constants.bin"]atomically:YES],@"Cannot preserve GPU state");
    if(initial) {
     check([r.originalCommands writeToFile:[prefix stringByAppendingString:@".original.bin"]atomically:YES]&&[r.relocatedCommands writeToFile:[prefix stringByAppendingString:@".relocated.bin"]atomically:YES],@"Cannot preserve native records");
     [backing addObject:@{@"index":@(i),@"QMD_SHA256":sha(qd),@"constants_SHA256":sha(cd),@"original_SHA256":sha(r.originalCommands),@"relocated_SHA256":sha(r.relocatedCommands),@"relocation":r.relocationEvidence}];
    } else {check([sha(qd)isEqual:backing[i][@"QMD_SHA256"]]&&[sha(cd)isEqual:backing[i][@"constants_SHA256"]],@"Resident state changed");[rechecks addObject:@{@"label":label,@"index":@(i),@"QMD_SHA256":sha(qd),@"constants_SHA256":sha(cd)}];}
   }
  };
  stateReadback(@"record",YES);report[@"resident_backing"]=backing;report[@"resident_state_rechecks"]=rechecks;
  NSMutableArray *rejections=[NSMutableArray new];
  for(NSDictionary *bad in @[@{@"label":@"empty",@"indices":@[],@"barriers":@[]},@{@"label":@"out-of-range",@"indices":@[@4],@"barriers":@[]},@{@"label":@"first-barrier",@"indices":@[@0,@1],@"barriers":@[@0]},@{@"label":@"past-barrier",@"indices":@[@0,@1],@"barriers":@[@2]},@{@"label":@"duplicate-in-segment",@"indices":@[@0,@0],@"barriers":@[]}]) {
   for(unsigned i=0;i<4;++i)[[icb indirectComputeCommandAtIndex:i]clearBarrier];error=nil;
   KPResidentBatch *p=[KPResidentBatch prepareScope:scope buffer:icb indices:bad[@"indices"]barrierBefore:indexSet(bad[@"barriers"])error:&error];
   check(!p&&error,@"Invalid plan was accepted");[rejections addObject:@{@"label":bad[@"label"],@"reason":error.localizedDescription,@"user_dispatches":@0}];
  }
  id<MTLIndirectComputeCommand>changedSlot=[icb indirectComputeCommandAtIndex:1];
  for(NSString *label in @[@"output-alias",@"partial-atomic-alias",@"self-alias",@"resident-state-alias",@"output-config-alias"]) {
   [changedSlot setKernelBuffer:sync offset:[label isEqual:@"partial-atomic-alias"]?260:256 atIndex:0];
   id<MTLBuffer>target=[label isEqual:@"self-alias"]?sync:[label isEqual:@"resident-state-alias"]?records[0].descriptor:[label isEqual:@"output-config-alias"]?params[0]:output;
   NSUInteger offset=[label isEqual:@"resident-state-alias"]?0:[label isEqual:@"partial-atomic-alias"]?512:256;
   [changedSlot setKernelBuffer:target offset:offset atIndex:1];error=nil;
   KPResidentBatch *p=[KPResidentBatch prepareScope:scope buffer:icb indices:@[@0,@1]barrierBefore:[NSIndexSet indexSet]error:&error];
   check(!p&&error,@"Aliased concurrent plan was accepted");[rejections addObject:@{@"label":label,@"reason":error.localizedDescription,@"user_dispatches":@0}];
  }
  [changedSlot setKernelBuffer:sync offset:256 atIndex:0];[changedSlot setKernelBuffer:output offset:512 atIndex:1];
  // The snapshot retains records and resources after all source slots reset.
  [icb resetWithRange:NSMakeRange(0,4)];report[@"source_slots_reset_before_execution"]=@YES;
  KPResidentBatch *serial=plans[@"serial-ab"];Config saved;memcpy(&saved,(char*)params[0].contents+256,16);Config bad=saved;bad.rounds=UINT32_MAX;memcpy((char*)params[0].contents+256,&bad,16);
  id<MTLCommandBuffer>rejected=[queue commandBuffer];error=nil;BOOL accepted=[serial encodeToCommandBuffer:rejected evidence:nil error:&error];check(!accepted&&error&&rejected.status==MTLCommandBufferStatusNotEnqueued,@"Unbounded config must be refused before commit");
  [rejections addObject:@{@"label":@"unbounded-config",@"reason":error.localizedDescription,@"user_dispatches":@0}];memcpy((char*)params[0].contents+256,&saved,16);
  id<MTLCommandQueue>other=[device newCommandQueue];rejected=[other commandBuffer];error=nil;accepted=[serial encodeToCommandBuffer:rejected evidence:nil error:&error];check(!accepted&&error&&rejected.status==MTLCommandBufferStatusNotEnqueued,@"Foreign queue must be refused");[rejections addObject:@{@"label":@"foreign-queue",@"reason":error.localizedDescription,@"user_dispatches":@0}];
  synchronize();report[@"preparation_untouched_witness"]=validate(@[],@[],710003);report[@"rejections"]=rejections;
  NSMutableArray *runs=[NSMutableArray new];report[@"runs"]=runs;unsigned dispatches=0;
  NSMutableArray *kinds=[@[@"none",@"only-a",@"only-b",@"pair-serial-ab",@"pair-serial-ba",@"serial-ab",@"serial-ba"]mutableCopy];
  if([mode isEqual:@"segmented"]||[mode isEqual:@"parallel"])[kinds addObjectsFromArray:@[@"pair-parallel-ab",@"pair-parallel-ba",@"segmented-ab",@"segmented-ba",@"source-barrier-ab",@"source-barrier-ba"]];
  if([mode isEqual:@"parallel"])[kinds addObjectsFromArray:@[@"parallel-ab",@"parallel-ba"]];
  if(![mode isEqual:@"prepare"])for(NSUInteger kindIndex=0;kindIndex<kinds.count;++kindIndex) {
   NSString *kind=kinds[kindIndex];BOOL experimental=kindIndex>=7;
   if(experimental)stateReadback([@"before-" stringByAppendingString:kind],NO);
   unsigned repeat=[mode isEqual:@"serial"]||([mode isEqual:@"segmented"]&&experimental)||([mode isEqual:@"parallel"]&&kindIndex>=13)?trials:1;
   for(unsigned trial=0;trial<repeat;++trial){@autoreleasepool{
    check(!experimental||runs.count>=7,@"Current-process controls required before experimental batch");
    uint32_t nonce=710011u+104729u*unsigned(runs.count);initialize(nonce);id<MTLCommandBuffer>cb=[queue commandBuffer];NSDictionary *evidence=@{};
    KPResidentBatch *plan=plans[kind];if(plan){error=nil;BOOL ok=[plan encodeToCommandBuffer:cb evidence:&evidence error:&error];check(ok,error.localizedDescription?:@"Batch encode failed");}
    check(complete(cb),@"Batch command buffer failed");NSArray *indices=plan?plan.planEvidence[@"record_indices"]:@[],*barriers=plan?plan.planEvidence[@"barrier_before_positions"]:@[];dispatches+=indices.count;report[@"user_compute_dispatches"]=@(dispatches);
    synchronize();NSMutableDictionary *row=[validate(indices,barriers,nonce)mutableCopy];row[@"kind"]=kind;row[@"trial"]=@(trial);row[@"nonce"]=@(nonce);row[@"encoding"]=evidence;row[@"command_status"]=@(cb.status);
    for(unsigned i=0;i<4;++i){NSData *data=[NSData dataWithBytes:params[i].contents length:1024];check([data writeToFile:[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"trial-%lu.params-%u.bin",(unsigned long)runs.count,i]]atomically:YES],@"Cannot preserve parameter bytes");}
    [runs addObject:row];
   }}
  }
  stateReadback(@"after",NO);report[@"runs"]=runs;report[@"scope_events"]=scope.events;
  [scope restore];report[@"scope_restored"]=@(object_getClass(device)==originalClass);check(object_getClass(device)==originalClass,@"Scope not restored");
  rejected=[queue commandBuffer];error=nil;accepted=[serial encodeToCommandBuffer:rejected evidence:nil error:&error];check(!accepted&&error&&rejected.status==MTLCommandBufferStatusNotEnqueued,@"Restored scope must refuse new batches");
  [rejections addObject:@{@"label":@"restored-scope",@"reason":error.localizedDescription,@"user_dispatches":@0}];report[@"status"]=@"PASS";
 } @catch(NSException *x) {if(scope)[scope restore];report[@"scope_restored"]=@(device&&originalClass&&object_getClass(device)==originalClass);report[@"exception_name"]=x.name;report[@"reason"]=x.reason?:@"";}
 NSData *json=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");return [report[@"status"]isEqual:@"PASS"]?0:1;
}}
