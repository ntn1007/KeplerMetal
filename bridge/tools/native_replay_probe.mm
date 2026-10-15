// Pinned-profile lab integration: real native command bytes, not CPU API replay.
#import "KeplerNativeCommands.h"
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <vector>
#include <cstdint>
#include <cstring>
struct P{uint32_t seed,groups,local,max_n;};
static void emit(NSDictionary*d){NSData*b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");}
static NSString*sha(NSData*d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
static NSData*readMemory(uintptr_t p,size_t bytes){if(!p||!bytes||bytes>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:bytes];mach_vm_size_t n=0;return mach_vm_read_overwrite(mach_task_self(),p,bytes,(mach_vm_address_t)d.mutableBytes,&n)==KERN_SUCCESS&&n==bytes?d:nil;}
static uint64_t word(NSData*d,size_t o){uint64_t v=0;if(o+8<=d.length)memcpy(&v,(const char*)d.bytes+o,8);return v;}
struct Cursor{uintptr_t push,current,end;};
static Cursor cursor(id<MTLComputeCommandEncoder>e){Cursor c={};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;uintptr_t impl=0;memcpy(&impl,(const char*)(__bridge const void*)e+120,8);c.push=word(readMemory(impl,64),32);NSData*d=readMemory(c.push,144);c.current=word(d,0);c.end=word(d,136);return c;}
static id<MTLBuffer>queueBuffer(id<MTLCommandQueue>q,unsigned o){Ivar v=class_getInstanceVariable(object_getClass(q),"_queue");if(!v||ivar_getOffset(v)!=680)return nil;uintptr_t cpp=0;memcpy(&cpp,(const char*)(__bridge const void*)q+680,8);uintptr_t p=word(readMemory(cpp,64),o);if(!p)return nil;id x=(__bridge id)(void*)p;return [x isKindOfClass:objc_getClass("NVMTLBuffer")]?x:nil;}
static bool done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static bool saveBuffer(id<MTLBuffer>b,NSString*p){return [[NSData dataWithBytes:b.contents length:b.length]writeToFile:p atomically:YES];}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;NSString*dir=@(argv[2]),*mode=@(argv[3]);unsigned local=atoi(argv[4]),groups=atoi(argv[5]);bool execute=[mode isEqual:@"execute"];
 if((!execute&&![mode isEqual:@"prepare"])||(local!=32&&local!=33&&local!=128)||(groups!=1&&groups!=3&&groups!=5)||groups*local>640)return 1;
 NSData*libBytes=[NSData dataWithContentsOfFile:@(argv[1])];if(![sha(libBytes)isEqual:@"b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d"])return 2;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name isEqual:@"NVIDIA GeForce GTX 880M"]&&x.registryID==4294968458){d=x;break;}if(!d)return 2;
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSError*error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];id<MTLComputePipelineState>pipe=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"consume_grid"] error:&error];if(!pipe)return 3;
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLBuffer>nativeCB=queueBuffer(q,32),nativeQMD=queueBuffer(q,16);
 const size_t outBytes=10368,counterBytes=132;std::vector<uint8_t>outInit(outBytes,0xa5),counterInit(counterBytes,0xa5),cbInit(65536+128,0xa5),qmdInit(4096+128,0xa5),paramInit(512,0xa5);uint32_t zero=0;memcpy(counterInit.data()+64,&zero,4);P params={0x1234,groups,local,640};memcpy(paramInit.data(),&params,16);
 id<MTLBuffer>output=[d newBufferWithLength:outBytes options:MTLResourceStorageModePrivate],counter=[d newBufferWithLength:counterBytes options:MTLResourceStorageModePrivate],parameters=[d newBufferWithBytes:paramInit.data() length:512 options:MTLResourceStorageModeShared];
 id<MTLBuffer>hostOut=[d newBufferWithBytes:outInit.data() length:outBytes options:MTLResourceStorageModeManaged],hostCounter=[d newBufferWithBytes:counterInit.data() length:counterBytes options:MTLResourceStorageModeManaged],hostCB=[d newBufferWithBytes:cbInit.data() length:cbInit.size() options:MTLResourceStorageModeManaged],hostQMD=[d newBufferWithBytes:qmdInit.data() length:qmdInit.size() options:MTLResourceStorageModeManaged];
 if(!output||!counter||!parameters||!hostOut||!hostCounter||!hostCB||!hostQMD||nativeCB.length!=393216||nativeQMD.length!=4096)return 4;
 auto reset=[&](){memcpy(hostOut.contents,outInit.data(),outBytes);memcpy(hostCounter.contents,counterInit.data(),counterBytes);[hostOut didModifyRange:NSMakeRange(0,outBytes)];[hostCounter didModifyRange:NSMakeRange(0,counterBytes)];id<MTLCommandBuffer>c=[q commandBuffer];id<MTLBlitCommandEncoder>b=[c blitCommandEncoder];[b copyFromBuffer:hostOut sourceOffset:0 toBuffer:output destinationOffset:0 size:outBytes];[b copyFromBuffer:hostCounter sourceOffset:0 toBuffer:counter destinationOffset:0 size:counterBytes];[b endEncoding];return done(c);};
 auto readback=[&](KPRecordedNativeCompute*sequence){id<MTLCommandBuffer>c=[q commandBuffer];id<MTLBlitCommandEncoder>b=[c blitCommandEncoder];[b copyFromBuffer:output sourceOffset:0 toBuffer:hostOut destinationOffset:0 size:outBytes];[b copyFromBuffer:counter sourceOffset:0 toBuffer:hostCounter destinationOffset:0 size:counterBytes];[b copyFromBuffer:sequence?sequence.constants:nativeCB sourceOffset:0 toBuffer:hostCB destinationOffset:64 size:65536];[b copyFromBuffer:sequence?sequence.descriptor:nativeQMD sourceOffset:0 toBuffer:hostQMD destinationOffset:64 size:4096];for(id<MTLResource>r in @[hostOut,hostCounter,hostCB,hostQMD])[b synchronizeResource:r];[b endEncoding];return done(c);};
 if(!reset())return 5;id<MTLCommandBuffer>record=[q commandBuffer];id<MTLComputeCommandEncoder>e=[record computeCommandEncoder];[e setComputePipelineState:pipe];[e setBuffer:output offset:64 atIndex:0];[e setBuffer:counter offset:64 atIndex:1];[e setBuffer:parameters offset:0 atIndex:2];Cursor before=cursor(e);[e dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];Cursor after=cursor(e);
 NSData*original=(before.push==after.push&&after.current>before.current&&after.current<=before.end)?readMemory(before.current,after.current-before.current):nil;if(!original||original.length!=464)return 6;
 [original writeToFile:[dir stringByAppendingPathComponent:@"original.commands.bin"] atomically:YES];[e endEncoding];if(!done(record)||!readback(nil))return 7;
 uint32_t referenceCount=0;memcpy(&referenceCount,(char*)hostCounter.contents+64,4);if(referenceCount!=local*groups)return 8;
 for(NSArray*x in @[@[@"reference.output.bin",hostOut],@[@"reference.counter.bin",hostCounter],@[@"native.constants.bin",hostCB],@[@"native.descriptor.bin",hostQMD]])if(!saveBuffer(x[1],[dir stringByAppendingPathComponent:x[0]]))return 9;
 NSData*snapshot=[NSData dataWithBytes:(char*)hostCB.contents+64 length:65536];
 auto build=[&](NSData*cmd,NSData*cbSnapshot,unsigned requestedGroups){return [KPRecordedNativeCompute recordedCommands:cmd queue:q pipeline:pipe output:output counter:counter parameters:parameters nativeConstants:nativeCB nativeDescriptor:nativeQMD constantSnapshot:cbSnapshot groups:requestedGroups local:local error:&error];};
 NSMutableArray*rejections=[NSMutableArray new];NSMutableData*bad=[original mutableCopy];((uint8_t*)bad.mutableBytes)[0]^=1;
 for(NSString*reason in @[@"bad_packet_header",@"wrong_binding",@"wrong_geometry"]){error=nil;NSMutableData*wrongTable=[snapshot mutableCopy];uint64_t z=0;memcpy((char*)wrongTable.mutableBytes+8,&z,8);KPRecordedNativeCompute*x=build([reason isEqual:@"bad_packet_header"]?bad:original,[reason isEqual:@"wrong_binding"]?wrongTable:snapshot,[reason isEqual:@"wrong_geometry"]?groups+1:groups);if(x||!error)return 10;[rejections addObject:@{@"case":reason,@"rejected":@YES,@"error":error.localizedDescription,@"GPU_replay":@NO}];}
 error=nil;KPRecordedNativeCompute*sequence=build(original,snapshot,groups);if(!sequence){emit(@{@"failure_stage":@"template",@"error":error.localizedDescription?:@"nil",@"GPU_replay":@NO});return 11;}
 [sequence.relocatedCommands writeToFile:[dir stringByAppendingPathComponent:@"relocated.commands.bin"] atomically:YES];
 id<MTLCommandBuffer>copy=[q commandBuffer];id<MTLBlitCommandEncoder>b=[copy blitCommandEncoder];[b copyFromBuffer:nativeCB sourceOffset:0 toBuffer:sequence.constants destinationOffset:0 size:65536];[b endEncoding];if(!done(copy))return 12;
 NSMutableArray*runs=[NSMutableArray new];unsigned badTotal=0;
 for(unsigned iteration=0;iteration<(execute?2u:1u)&&!badTotal;iteration++)for(unsigned variant=0;variant<(execute?4u:1u);variant++){@autoreleasepool{
  unsigned copies=variant==0?1:variant==1?4:variant==2?16:8;bool noLaunch=variant==3;params.seed=0x1234+37*iteration;memcpy(parameters.contents,&params,16);if(!reset())return 13;
  id<MTLCommandBuffer>c=[q commandBuffer];e=[c computeCommandEncoder];NSDictionary*evidence=nil;error=nil;
  if(![sequence encodeCopies:copies encoder:e suppressLaunches:noLaunch evidence:&evidence error:&error]){emit(@{@"failure_stage":@"encode",@"error":error.localizedDescription?:@"nil",@"GPU_replay":@NO,@"relocation":sequence.relocationEvidence});return 14;}
  Cursor end=cursor(e);NSData*encoded=readMemory(end.current-copies*464,copies*464);NSString*base=[dir stringByAppendingPathComponent:[NSString stringWithFormat:@"trial-%u-%u",iteration,variant]];[encoded writeToFile:[base stringByAppendingString:@".commands.bin"] atomically:YES];[e endEncoding];
  if(!execute){[runs addObject:@{@"iteration":@(iteration),@"variant":@(variant),@"base":base,@"copies":@(copies),@"GPU_replay":@NO,@"committed":@NO,@"evidence":evidence}];continue;}
  if(!done(c)){emit(@{@"failure_stage":@"GPU_replay",@"status":@(c.status),@"error":c.error.description?:@""});return 15;}
  if(!readback(sequence))return 16;unsigned n=local*groups;uint32_t count=0;memcpy(&count,(char*)hostCounter.contents+64,4);unsigned expectedCount=noLaunch?0:copies*n,badValues=count!=expectedCount,guards=0;const uint8_t*raw=(const uint8_t*)hostOut.contents;const uint32_t*values=(const uint32_t*)(raw+64);
  if(noLaunch){for(size_t i=0;i<outBytes;i++)badValues+=raw[i]!=0xa5;}else{for(unsigned i=0;i<n;i++){uint32_t w[4]={(params.seed*1664525u)^(i*1013904223u),i,groups|0x01010000u,local};for(unsigned col=0;col<4;col++)badValues+=values[i*4+col]!=w[col];}for(size_t i=64+n*16;i<outBytes-64;i++)guards+=raw[i]!=0xa5;}
  for(id<MTLBuffer>buf in @[hostOut,hostCounter,hostCB,hostQMD]){const uint8_t*p=(const uint8_t*)buf.contents;for(size_t i=0;i<64;i++)guards+=p[i]!=0xa5||p[buf.length-64+i]!=0xa5;}
  for(NSArray*x in @[@[@".output.bin",hostOut],@[@".counter.bin",hostCounter],@[@".constants.bin",hostCB],@[@".descriptor.bin",hostQMD]])if(!saveBuffer(x[1],[base stringByAppendingString:x[0]]))return 17;
  [runs addObject:@{@"iteration":@(iteration),@"variant":@(variant),@"base":base,@"seed":@(params.seed),@"copies":@(copies),@"suppress_launches":@(noLaunch),@"actual_invocations":@(count),@"expected_invocations":@(expectedCount),@"mismatches":@(badValues),@"guard_mismatches":@(guards),@"GPU_replay":@YES,@"command_status":@(c.status),@"evidence":evidence}];badTotal+=badValues+guards;if(badTotal)break;
 }}
 emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"mode":mode,@"local":@(local),@"groups":@(groups),@"reference_native_invocations":@(referenceCount),@"source_library_SHA256":sha(libBytes),@"relocation":sequence.relocationEvidence,@"rejections":rejections,@"runs":runs,@"passed":@(!badTotal),@"ICB_implemented":@NO,@"system_modifications":@NO,@"integration_level":@1,@"scope":@"Pinned native direct-compute packets with dedicated CB/QMD, reused in fresh own command buffers. One native preparation call per CB removed before commit; no ordinary-app integration or ICB contract claim."});return badTotal?18:0;
}}
