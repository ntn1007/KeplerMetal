#import "KeplerCPUICB.h"
#import "KeplerNativeCommands.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>

static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*d=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}

// Mutated NSData is passed only to the CPU validator. It is never encoded,
// uploaded, imported as GPU code or substituted into native command memory.
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]);NSError*error=nil;id<MTLDevice>d=nil;
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];
 NSData*library=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"combined_shared.metallib"]];
 NSData*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"cpu_icb_combined_shared_manifest.json"]];
 KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:library expectedSHA256:sha(library)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error];if(!s)return 3;
 id<MTLBuffer>output=[d newBufferWithLength:131584 options:MTLResourceStorageModePrivate],counter=[d newBufferWithLength:208 options:MTLResourceStorageModePrivate],params=[d newBufferWithLength:2048 options:MTLResourceStorageModeShared];
 id<MTLBuffer>oh=[d newBufferWithLength:131584 options:MTLResourceStorageModeShared],ch=[d newBufferWithLength:208 options:MTLResourceStorageModeShared],snapshotHost=[d newBufferWithLength:65536 options:MTLResourceStorageModeShared];if(!output||!counter||!params||!oh||!ch||!snapshotHost)return 4;
 uint32_t p[5]={0x765431,3,32,96,12160};memset(params.contents,0xa5,params.length);memcpy((char*)params.contents+1024,p,sizeof(p));memset(oh.contents,0xa5,oh.length);memset(ch.contents,0xa5,ch.length);memset((char*)ch.contents+128,0,4);
 id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];[b copyFromBuffer:oh sourceOffset:0 toBuffer:output destinationOffset:0 size:oh.length];[b copyFromBuffer:ch sourceOffset:0 toBuffer:counter destinationOffset:0 size:ch.length];[b endEncoding];if(!done(init))return 5;
 MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=3;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
 id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];id<MTLIndirectComputeCommand>command=[icb indirectComputeCommandAtIndex:0];
 [command setComputePipelineState:[s pipelineForFunction:@"shared_mix_s128"]];[command setKernelBuffer:output offset:128 atIndex:0];[command setKernelBuffer:counter offset:128 atIndex:1];[command setKernelBuffer:params offset:1024 atIndex:2];[command setThreadgroupMemoryLength:48640 atIndex:0];[command concurrentDispatchThreadgroups:MTLSizeMake(3,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];
 if(![s prepareResidentComputeCommands:icb range:NSMakeRange(0,1)error:&error])return 6;
 KPRecordedNativeCompute*r=[(id)command valueForKey:@"record"];if(![r isKindOfClass:KPRecordedNativeCompute.class]||r.originalCommands.length!=496)return 7;
 id<MTLCommandBuffer>read=[q commandBuffer];b=[read blitCommandEncoder];[b copyFromBuffer:r.constants sourceOffset:0 toBuffer:snapshotHost destinationOffset:0 size:65536];[b endEncoding];if(!done(read))return 8;
 NSData*snapshot=[NSData dataWithBytes:snapshotHost.contents length:65536];NSDictionary*profile=[r valueForKey:@"profile"];
 auto make=[&](NSData*commands,NSData*constants)->KPRecordedNativeCompute*{
  error=nil;return[KPRecordedNativeCompute recordedCommands:commands queue:q pipeline:[r valueForKey:@"pipeline"]output:output counter:counter parameters:params nativeConstants:[r valueForKey:@"nativeConstants"]nativeDescriptor:[r valueForKey:@"nativeDescriptor"]constantSnapshot:constants groups:3 local:32 profile:profile error:&error];
 };
 KPRecordedNativeCompute*valid=make(r.originalCommands,snapshot);if(!valid)return 9;
 NSMutableArray*controls=[NSMutableArray new];
 for(NSString*name in @[@"base_zero",@"base_minus16",@"snapshot_base_zero",@"shared_total_plus16"]){
  NSMutableData*commands=[r.originalCommands mutableCopy],*constants=[snapshot mutableCopy];uint32_t value=0;
  if([name isEqual:@"base_minus16"])value=496;
  if([name hasPrefix:@"base_"])memcpy((char*)commands.mutableBytes+28,&value,4);
  else if([name isEqual:@"snapshot_base_zero"])memcpy((char*)constants.mutableBytes+0x640,&value,4);
  else{uint32_t field=0;memcpy(&field,(char*)commands.bytes+216+0x44,4);field=(field&~0x3ffffu)|49168;memcpy((char*)commands.mutableBytes+216+0x44,&field,4);}
  KPRecordedNativeCompute*bad=make(commands,constants);if(bad||!error)return 10;
  NSString*reason=error.localizedDescription;NSString*want=[name hasPrefix:@"base_"]?@"Dynamic threadgroup pointer prelude differs":[name isEqual:@"snapshot_base_zero"]?@"Captured dynamic threadgroup base word differs from native prelude":@"Native QMD static shared memory differs from reflected profile";if(![reason isEqual:want])return 10;
  [controls addObject:@{@"case":name,@"refused":@YES,@"reason":reason,@"CPU_validator_only":@YES,@"mutated_bytes_ever_encoded":@NO}];
 }
 id<MTLCommandBuffer>main=[q commandBuffer];id<MTLComputeCommandEncoder>e=[main computeCommandEncoder];if(![s adaptComputeEncoder:e error:&error])return 11;[e executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];[e endEncoding];if(!done(main))return 12;
 read=[q commandBuffer];b=[read blitCommandEncoder];[b copyFromBuffer:output sourceOffset:0 toBuffer:oh destinationOffset:0 size:oh.length];[b copyFromBuffer:counter sourceOffset:0 toBuffer:ch destinationOffset:0 size:ch.length];[b endEncoding];if(!done(read))return 13;
 [[NSData dataWithBytes:oh.contents length:oh.length]writeToFile:[out stringByAppendingPathComponent:@"output.bin"]atomically:YES];[[NSData dataWithBytes:ch.contents length:ch.length]writeToFile:[out stringByAppendingPathComponent:@"counter.bin"]atomically:YES];
 [s restore];emit(@{@"status":@"PASS_REJECTIONS_AND_VALID_REPLAY",@"device":d.name,@"registry_id":@(d.registryID),@"controls":controls,@"original_constructor_accepted":@YES,@"main_command_status":@(main.status),@"scope_restored":@(object_getClass(d)==original),@"system_modified":@NO,@"events":s.events,@"mutated_commands_ever_submitted":@NO,@"performance_benchmark":@NO});return 0;
}}
