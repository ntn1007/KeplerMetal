// SPDX-License-Identifier: MIT
// Isolated laboratory client of the unchanged resident-record transport.
#import "KeplerCPUICB.h"
#import "KeplerNativeCommands.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <mach/vm_region.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <unistd.h>

@protocol KPLabRecordAccess
@property(nonatomic,readonly) KPRecordedNativeCompute *record;
@end
struct Config {uint32_t limit,nonce,rounds,reserved;};
static constexpr uint32_t Poison=0xa53c6f09u;
static void require(bool v,NSString *s){if(!v)@throw [NSException exceptionWithName:@"ResidentPairFailure" reason:s userInfo:nil];}
static NSString *sha(NSData *d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(auto c:h)[s appendFormat:@"%02x",c];return s;}
static NSData *memory(uintptr_t p,size_t n){if(!p||!n||n>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:n];mach_vm_size_t got=0;return mach_vm_read_overwrite(mach_task_self(),p,n,(mach_vm_address_t)d.mutableBytes,&got)==KERN_SUCCESS&&got==n?d:nil;}
static uint64_t u64(NSData*d,size_t o){uint64_t n=0;if(o+8<=d.length)memcpy(&n,(const char*)d.bytes+o,8);return n;}
static uint32_t u32(NSData*d,size_t o){uint32_t n=0;if(o+4<=d.length)memcpy(&n,(const char*)d.bytes+o,4);return n;}
struct Cursor{uintptr_t push,current,end;};
static Cursor cursor(id<MTLComputeCommandEncoder>e){Cursor c{};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;uintptr_t impl=0;memcpy(&impl,(const char*)(__bridge const void*)e+120,8);c.push=u64(memory(impl,64),32);NSData*p=memory(c.push,144);c.current=u64(p,0);c.end=u64(p,136);return c;}
static bool writable(uintptr_t p,size_t n){if(!p||!n||p+n<p)return false;mach_vm_address_t address=p;mach_vm_size_t size=0;vm_region_basic_info_data_64_t info{};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=MACH_PORT_NULL;kern_return_t result=mach_vm_region(mach_task_self(),&address,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);return result==KERN_SUCCESS&&address<=p&&p+n<=address+size&&(info.protection&VM_PROT_WRITE);}
static bool complete(id<MTLCommandBuffer>cb){[cb commit];[cb waitUntilCompleted];return cb.status==MTLCommandBufferStatusCompleted;}
static NSArray *words(id<MTLBuffer>b){NSMutableArray*a=[NSMutableArray new];const uint32_t*p=(const uint32_t*)b.contents;for(NSUInteger i=0;i<b.length/4;++i)[a addObject:@(p[i])];return a;}
static uint32_t oracle(uint32_t nonce,unsigned role){uint32_t x=nonce^(role?0x85ebca6bu:0x9e3779b9u);for(unsigned i=0;i<128;++i)x=((x<<7)|(x>>25))*uint32_t(1664525)+uint32_t(1013904223)+i;return x;}

int main(int argc,char **argv){@autoreleasepool{
 if(argc!=6)return 2;NSString*mode=@(argv[4]);unsigned trials=(unsigned)strtoul(argv[5],nullptr,10);
 if(![@[@"prepare",@"serial",@"overlap"]containsObject:mode]||!trials||trials>8)return 2;
 NSString*directory=@(argv[3]);KPCPUICBScope*scope=nil;id<MTLDevice>device=nil;Class original=nil;
 NSMutableDictionary*report=[@{@"status":@"ERROR",@"mode":mode,@"pid":@(getpid()),@"uid":@(getuid()),@"euid":@(geteuid()),
   @"user_compute_dispatches":@0,@"experimental_wait_removals":@0,@"native_shader_code_changed":@NO,
   @"common_runtime_modified":@NO,@"system_modified":@NO,@"performance_benchmark":@NO}mutableCopy];
 @try{
  device=MTLCreateSystemDefaultDevice();require([device.name isEqual:@"NVIDIA GeForce GTX 880M"]&&device.registryID==4294968458,@"Pinned GPU required");original=object_getClass(device);
  report[@"device"]=device.name;report[@"registry_id"]=@(device.registryID);id<MTLCommandQueue>queue=[device newCommandQueue];require(queue!=nil,@"Queue missing");
  NSData*library=[NSData dataWithContentsOfFile:@(argv[1])],*manifest=[NSData dataWithContentsOfFile:@(argv[2])];
  NSError*error=nil;scope=[KPCPUICBScope installOnDevice:device queue:queue libraryData:library expectedSHA256:sha(library) manifestData:manifest expectedManifestSHA256:sha(manifest) error:&error];
  require(scope!=nil,error.localizedDescription?:@"Registration failed");report[@"library_SHA256"]=sha(library);report[@"manifest_SHA256"]=sha(manifest);
  id<MTLBuffer>sync=[device newBufferWithLength:1024 options:MTLResourceStorageModeManaged],output=[device newBufferWithLength:1024 options:MTLResourceStorageModeManaged];
  id<MTLBuffer>parameters[2];for(unsigned r=0;r<2;++r)parameters[r]=[device newBufferWithLength:1024 options:MTLResourceStorageModeShared];
  require(sync&&output&&parameters[0]&&parameters[1],@"Witness buffers missing");
  auto initialize=[&](uint32_t nonce){
   for(id<MTLBuffer>b in @[sync,output]){uint32_t*p=(uint32_t*)b.contents;for(unsigned i=0;i<256;++i)p[i]=Poison;}
   uint32_t*s=(uint32_t*)sync.contents;s[64]=s[65]=s[66]=0;
   for(unsigned r=0;r<2;++r){memset(parameters[r].contents,0xa5,1024);Config c{4096,nonce,128,0};memcpy((char*)parameters[r].contents+256,&c,sizeof(c));}
   [sync didModifyRange:NSMakeRange(0,1024)];[output didModifyRange:NSMakeRange(0,1024)];
  };
  auto readback=[&](){id<MTLCommandBuffer>c=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[c blitCommandEncoder];[b synchronizeResource:sync];[b synchronizeResource:output];[b endEncoding];require(complete(c),@"Witness synchronization failed");};
  auto validate=[&](NSString*kind,uint32_t nonce)->NSDictionary*{
   const uint32_t*s=(const uint32_t*)sync.contents,*o=(const uint32_t*)output.contents;
   bool active[2]={![kind isEqual:@"none"]&&![kind isEqual:@"only-b"],![kind isEqual:@"none"]&&![kind isEqual:@"only-a"]};unsigned count=unsigned(active[0])+unsigned(active[1]),bad=0,guards=0;bool tags[5]={};
   for(unsigned i=0;i<256;++i){if((i<64||i>=67)&&s[i]!=Poison)++guards;bool used=active[0]&&i>=64&&i<72||active[1]&&i>=128&&i<136;if(!used&&o[i]!=Poison)++guards;}
   if(s[64]!=count*2||s[65]!=unsigned(active[0])||s[66]!=unsigned(active[1]))++bad;
   for(unsigned role=0;role<2;++role){if(!active[role])continue;const uint32_t*r=o+(role?128:64);
    if(r[0]<1||r[0]>=r[1]||r[1]>count*2)++bad;
    for(unsigned j=0;j<2;++j){if(r[j]<1||r[j]>count*2||tags[r[j]])++bad;else tags[r[j]]=true;}
    if(r[2]>1||r[3]<1||r[3]>4096||!r[2]&&r[3]!=4096||!active[1-role]&&r[2])++bad;
    if(r[4]!=oracle(nonce,role)||r[5]!=nonce||r[6]!=role||r[7]!=128)++bad;
    if([kind hasPrefix:@"serial-"]){bool first=role==([kind hasSuffix:@"-ba"]?1u:0u);if(r[0]!=(first?1u:3u)||r[1]!=(first?2u:4u)||r[2]!=(first?0u:1u))++bad;}
   }
   for(unsigned tag=1;tag<=count*2;++tag)if(!tags[tag])++bad;
   for(unsigned role=0;role<2;++role){unsigned char expected[1024];memset(expected,0xa5,1024);Config c{4096,nonce,128,0};memcpy(expected+256,&c,16);if(memcmp(expected,parameters[role].contents,1024))++guards;}
   bool overlap=count==2&&o[64]<o[129]&&o[128]<o[65];
   NSDictionary*r=@{@"kind":kind,@"nonce":@(nonce),@"sync_words":words(sync),@"output_words":words(output),@"arithmetic_mismatches":@(bad),@"guard_mismatches":@(guards),@"interleaved_lifetimes":@(overlap),@"active_dispatches":@(count)};
   require(bad==0&&guards==0,@"GPU numerical/order/guard witness differs");return r;
  };
  initialize(310019);
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=3;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
  id<MTLIndirectCommandBuffer>icb=[device newIndirectCommandBufferWithDescriptor:desc maxCommandCount:2 options:MTLResourceStorageModeShared];require(icb!=nil,@"Owned ICB missing");
  id<MTLIndirectComputeCommand>slots[2];
  for(unsigned role=0;role<2;++role){slots[role]=[icb indirectComputeCommandAtIndex:role];[slots[role]setComputePipelineState:[scope pipelineForFunction:role?@"observe_b":@"observe_a"]];[slots[role]setKernelBuffer:sync offset:256 atIndex:0];[slots[role]setKernelBuffer:output offset:role?512:256 atIndex:1];[slots[role]setKernelBuffer:parameters[role]offset:256 atIndex:2];[slots[role]concurrentDispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];}
  BOOL prepared=[scope prepareResidentComputeCommands:icb range:NSMakeRange(0,2) error:&error];
  require(prepared,error.localizedDescription?:@"Resident preparation failed");
  KPRecordedNativeCompute*records[2];
  for(unsigned role=0;role<2;++role){require([slots[role]respondsToSelector:@selector(record)],@"Owned SDK slot record getter missing");records[role]=[(id<KPLabRecordAccess>)slots[role]record];require([records[role]isKindOfClass:KPRecordedNativeCompute.class]&&records[role].residentDescriptorReady,@"Prepared record identity/readiness differs");}
  require(records[0]!=records[1]&&records[0].descriptor.gpuAddress!=records[1].descriptor.gpuAddress&&records[0].constants.gpuAddress!=records[1].constants.gpuAddress,@"Independent record state required");
  NSMutableArray*backing=[NSMutableArray new];
  for(unsigned role=0;role<2;++role){KPRecordedNativeCompute*r=records[role];id<MTLBuffer>q=[device newBufferWithLength:256 options:MTLResourceStorageModeManaged],c=[device newBufferWithLength:65536 options:MTLResourceStorageModeManaged];
   id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:r.descriptor sourceOffset:0 toBuffer:q destinationOffset:0 size:256];[b copyFromBuffer:r.constants sourceOffset:0 toBuffer:c destinationOffset:0 size:65536];[b synchronizeResource:q];[b synchronizeResource:c];[b endEncoding];require(complete(cb),@"Resident state readback failed");
   NSData*qmd=[NSData dataWithBytes:q.contents length:256],*constants=[NSData dataWithBytes:c.contents length:65536],*original=r.originalCommands,*relocated=r.relocatedCommands;
   require(original.length==464&&relocated.length==464&&[qmd isEqual:[relocated subdataWithRange:NSMakeRange(184,256)]],@"Actual GPU QMD differs from validated relocated bytes");
   require(u64(constants,8)==sync.gpuAddress+256&&u64(constants,40)==output.gpuAddress+(role?512:256)&&u64(constants,72)==parameters[role].gpuAddress+256,@"Actual resident buffer table differs");
   NSMutableArray*changes=[NSMutableArray new];NSArray*allowed=@[@12,@16,@168,@172,@308,@312,@444];
   for(unsigned i=0;i<464;i+=4)if(u32(original,i)!=u32(relocated,i)){require([allowed containsObject:@(i)],@"Unexpected original native command change");[changes addObject:@(i)];}
   require((u32(qmd,0x50)&255)==7&&(u32(qmd,0xb8)>>24)==17&&(u32(qmd,0x78)>>15)==256,@"Native literal bank/register metadata changed");
   NSString*prefix=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"record-%u",role]];
   require([qmd writeToFile:[prefix stringByAppendingString:@".QMD.bin"] atomically:YES]&&[constants writeToFile:[prefix stringByAppendingString:@".constants.bin"] atomically:YES]&&[original writeToFile:[prefix stringByAppendingString:@".original.bin"] atomically:YES]&&[relocated writeToFile:[prefix stringByAppendingString:@".relocated.bin"] atomically:YES],@"Cannot retain exact state evidence");
   [backing addObject:@{@"role":@(role),@"QMD_GPU_address":@(r.descriptor.gpuAddress),@"constants_GPU_address":@(r.constants.gpuAddress),@"QMD_SHA256":sha(qmd),@"constants_SHA256":sha(constants),@"original_SHA256":sha(original),@"relocated_SHA256":sha(relocated),@"changed_command_words":changes,@"relocation":r.relocationEvidence}];
  }
  readback();report[@"preparation_untouched_witness"]=validate(@"none",310019);report[@"resident_backing"]=backing;
  NSArray*owners=@[records[0],records[1]];NSMutableArray*runs=[NSMutableArray new],*rechecks=[NSMutableArray new];report[@"runs"]=runs;report[@"resident_state_rechecks"]=rechecks;unsigned dispatches=0,passedControls=0,waitRemovals=0;
  auto recheckState=[&](NSString*label){
   for(unsigned role=0;role<2;++role){id<MTLBuffer>q=[device newBufferWithLength:256 options:MTLResourceStorageModeManaged],c=[device newBufferWithLength:65536 options:MTLResourceStorageModeManaged];id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:records[role].descriptor sourceOffset:0 toBuffer:q destinationOffset:0 size:256];[b copyFromBuffer:records[role].constants sourceOffset:0 toBuffer:c destinationOffset:0 size:65536];[b synchronizeResource:q];[b synchronizeResource:c];[b endEncoding];require(complete(cb),@"Resident state recheck readback failed");NSData*qd=[NSData dataWithBytes:q.contents length:256],*cd=[NSData dataWithBytes:c.contents length:65536];require([sha(qd)isEqual:backing[role][@"QMD_SHA256"]]&&[sha(cd)isEqual:backing[role][@"constants_SHA256"]],@"Resident state changed across completed kernels");NSString*prefix=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"%@-%u",label,role]];require([qd writeToFile:[prefix stringByAppendingString:@".QMD.bin"]atomically:YES]&&[cd writeToFile:[prefix stringByAppendingString:@".constants.bin"]atomically:YES],@"Cannot preserve resident recheck");[rechecks addObject:@{@"label":label,@"role":@(role),@"QMD_SHA256":sha(qd),@"constants_SHA256":sha(cd)}];}
  };
  NSArray*kinds=[mode isEqual:@"overlap"]?@[@"none",@"only-a",@"only-b",@"serial-ab",@"serial-ba",@"overlap-ab",@"overlap-ba"]:@[@"none",@"only-a",@"only-b",@"serial-ab",@"serial-ba"];
  if(![mode isEqual:@"prepare"])for(NSString*kind in kinds)for(unsigned trial=0;trial<([mode isEqual:@"overlap"]&&![kind hasPrefix:@"overlap-"]?1u:trials);++trial){@autoreleasepool{
   BOOL experimental=[kind hasPrefix:@"overlap-"];
   if(experimental&&trial==0){require(passedControls==5,@"All current-process serial controls must pass first");recheckState([@"before-" stringByAppendingString:kind]);}
   uint32_t nonce=310031u+104729u*unsigned(runs.count);initialize(nonce);NSArray*sequence=[kind isEqual:@"none"]?@[]:[kind isEqual:@"only-a"]?@[records[0]]:[kind isEqual:@"only-b"]?@[records[1]]:[kind hasSuffix:@"-ba"]?@[records[1],records[0]]:owners;
   id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];NSDictionary*evidence=nil,*cursorEvidence=@{},*patchEvidence=@{};NSData*stream=[NSData data],*originalStream=nil;uintptr_t streamStart=0;
   @try{if(sequence.count){
    KPRecordedNativeCompute*first=sequence[0];Cursor before=cursor(e);
    BOOL encoded=[first encodeResidentSequence:sequence owners:owners encoder:e suppressElementIndexes:[NSIndexSet indexSet] evidence:&evidence error:&error];
    require(encoded,error.localizedDescription?:@"Resident serial encoding failed");Cursor after=cursor(e);NSUInteger length=24*sequence.count;
    // The public resident method first declares resources; that can initialize
    // the push cursor. Its internal validated stream ends at the returned cursor.
    require([evidence[@"command_bytes"]unsignedIntegerValue]==length&&after.push&&after.current>=length&&after.current<after.end,@"Resident returned stream/cursor bounds differ");
    uintptr_t start=after.current-length;streamStart=start;stream=memory(start,length);
    NSMutableData*wanted=[NSMutableData new];for(KPRecordedNativeCompute*r in sequence)[wanted appendData:[r.relocatedCommands subdataWithRange:NSMakeRange(440,24)]];
    require([stream isEqual:wanted]&&[sha(stream)isEqual:evidence[@"stream_SHA256"]],@"Resident sequence differs from exact native templates and transport readback");
    cursorEvidence=@{@"client_before_push":@(before.push),@"client_before_current":@(before.current),@"after_push":@(after.push),@"after_current":@(after.current),@"after_end":@(after.end),@"validated_native_stream_start":@(start),@"stream_bytes":@(length)};
    if(experimental){
     require(passedControls==5&&sequence.count==2&&rechecks.count>=2&&length==48&&cb.status==MTLCommandBufferStatusNotEnqueued&&cb.retainedReferences,@"Concurrent experiment prerequisites differ");
     require(before.push==after.push&&start>=before.current&&before.end==after.end&&writable(start,48),@"Own uncommitted candidate memory boundary/protection differs");
     require(u32(stream,16)==0x20012044&&u32(stream,20)==0&&u32(stream,40)==0x20012044&&u32(stream,44)==0,@"Expected intermediate and terminal waits missing");
     originalStream=stream;NSMutableData*candidate=[stream mutableCopy];uint32_t nop=0x20012040;memcpy((char*)candidate.mutableBytes+16,&nop,4);
     memcpy((void*)(start+16),&nop,4);NSData*observed=memory(start,48);require([observed isEqual:candidate]&&cursor(e).current==after.current,@"Isolated candidate word or cursor readback differs");
     stream=observed;waitRemovals++;report[@"experimental_wait_removals"]=@(waitRemovals);patchEvidence=@{@"changed_word_offset":@16,@"original_header":@0x20012044u,@"candidate_header":@0x20012040u,@"terminal_WAIT_FOR_IDLE_retained":@YES,@"QMD_or_constant_state_changed":@NO,@"native_shader_changed":@NO,@"original_stream_SHA256":sha(originalStream),@"candidate_stream_SHA256":sha(stream)};
    }
   }}
   @finally{[e endEncoding];}
   if(experimental)require([memory(streamStart,stream.length)isEqual:stream],@"Native endEncoding changed the validated candidate bytes");
   require(complete(cb),@"Resident user kernel command buffer failed");dispatches+=sequence.count;report[@"user_compute_dispatches"]=@(dispatches);readback();NSMutableDictionary*row=[validate(kind,nonce)mutableCopy];row[@"trial"]=@(trial);row[@"command_status"]=@(cb.status);row[@"stream_SHA256"]=sha(stream);row[@"stream_bytes"]=@(stream.length);row[@"resident_evidence"]=evidence?:@{};row[@"cursor_evidence"]=cursorEvidence;
   row[@"native_encoder_dispatch_type"]=@(e.dispatchType);row[@"experimental_patch"]=patchEvidence;
   NSString*path=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"trial-%lu.commands.bin",(unsigned long)runs.count]];require([stream writeToFile:path atomically:YES],@"Cannot retain command evidence");if(originalStream)require([originalStream writeToFile:[path stringByAppendingString:@".original"]atomically:YES],@"Cannot retain original stream");
   for(unsigned role=0;role<2;++role){NSData*data=[NSData dataWithBytes:parameters[role].contents length:1024];require([data writeToFile:[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"trial-%lu.params-%u.bin",(unsigned long)runs.count,role]]atomically:YES],@"Cannot retain parameter guards");}
   [runs addObject:row];if([mode isEqual:@"overlap"]&&!experimental)passedControls++;
  }}
  if([mode isEqual:@"overlap"])recheckState(@"after-overlap");
  report[@"runs"]=runs;report[@"scope_events"]=scope.events;[scope restore];report[@"scope_restored"]=@(object_getClass(device)==original);require(object_getClass(device)==original,@"Device scope not restored");report[@"status"]=@"PASS";
 }@catch(NSException*x){if(scope)[scope restore];report[@"scope_restored"]=@(device&&original&&object_getClass(device)==original);report[@"exception_name"]=x.name;report[@"reason"]=x.reason?:@"";}
 NSData*j=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return [report[@"status"]isEqual:@"PASS"]?0:1;
}}
