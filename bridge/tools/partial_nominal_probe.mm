// SPDX-License-Identifier: MIT
// Laboratory experiment: existing NVIDIA-compiled grid_coordinates shader and
// existing resident launch; only bounded built-in data constants are changed, not packets.
#import "KeplerCPUICB.h"
#import "KeplerNativeCommands.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#include <cstdlib>
#include <unistd.h>

@protocol KPLabOriginRecord <NSObject>
@property(nonatomic,readonly) KPRecordedNativeCompute *record;
@end
struct Parameters { uint32_t count,seed,reserved0,reserved1; };
static void require(bool ok,NSString *message){if(!ok)@throw [NSException exceptionWithName:@"OriginProbeFailure" reason:message userInfo:nil];}
static bool complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static NSString*sha(NSData*d){unsigned char v[32];CC_SHA256(d.bytes,(CC_LONG)d.length,v);NSMutableString*s=[NSMutableString new];for(auto c:v)[s appendFormat:@"%02x",c];return s;}
static void save(NSData*d,NSString*p){require(d&&[d writeToFile:p atomically:YES],@"Cannot preserve evidence");}
static NSUInteger vol(MTLSize x){return x.width*x.height*x.depth;}
static uint32_t packed(MTLSize x){return (uint32_t)(x.width|(x.height<<10)|(x.depth<<20));}
static uint32_t word(NSData*d,NSUInteger o){uint32_t n=0;require(o+4<=d.length,@"Out of bounds state read");memcpy(&n,(char*)d.bytes+o,4);return n;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 2;NSString*dir=@(argv[3]),*mode=@(argv[4]);char*end=nullptr;uint64_t registry=strtoull(argv[5],&end,10);if(!registry||!end||*end||(![mode isEqual:@"prepare"]&&![mode isEqual:@"execute"]))return 2;
 id<MTLDevice>d=nil;KPCPUICBScope*scope=nil;Class original=nil;NSMutableDictionary*report=[@{@"mode":mode,@"status":@"FAIL",@"pid":@(getpid()),@"user_dispatches":@0,@"system_modified":@NO,@"driver_modified":@NO,@"shader_modified":@NO,@"partial_threadgroups_implemented":@NO}mutableCopy];
 @try{
  for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==registry)d=x;require([d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"Pinned GTX identity missing");original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
  scope=[KPCPUICBScope installOnDevice:d queue:q libraryURL:[NSURL fileURLWithPath:@(argv[1])] expectedSHA256:@"5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0" manifestURL:[NSURL fileURLWithPath:@(argv[2])] expectedManifestSHA256:@"fa081fc43d24d54873d069006f9581f6b73b631f505ed9b854cb3429107ec4f3" error:&error];require(scope!=nil,error.localizedDescription?:@"Scope failed");
  const MTLSize groups[3]={MTLSizeMake(1,1,1),MTLSizeMake(1,1,1),MTLSizeMake(1,1,1)},local[3]={MTLSizeMake(3,1,1),MTLSizeMake(4,1,1),MTLSizeMake(4,2,1)};
  const uint32_t origins[3][3]={{8,0,0},{0,4,0},{0,0,4}},nominal[3][3]={{4,1,1},{4,2,1},{4,2,2}},logicalGroups[3][3]={{3,1,1},{2,3,1},{2,2,3}},logicalGrid[3][3]={{11,1,1},{8,5,1},{8,4,5}};NSMutableArray*nodes=[NSMutableArray new];
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
  id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:3 options:MTLResourceStorageModeShared];require(icb!=nil,@"ICB allocation failed");
  for(unsigned i=0;i<3;i++){
   NSMutableDictionary*n=[NSMutableDictionary new];for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){NSUInteger size=[k isEqual:@"counter"]?132:1024*16+128;id<MTLBuffer>gpu=[d newBufferWithLength:size options:MTLResourceStorageModePrivate],host=[d newBufferWithLength:size options:MTLResourceStorageModeManaged];require(gpu&&host,@"Witness allocation failed");n[k]=gpu;n[[k stringByAppendingString:@"Host"]]=host;}
   id<MTLBuffer>p=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];require(p!=nil,@"Parameter allocation failed");memset(p.contents,0xa5,p.length);Parameters value={1024,0x3141u+101*i,0,0};memcpy((char*)p.contents+256,&value,sizeof(value));n[@"p"]=p;[nodes addObject:n];
   id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:i];[c setComputePipelineState:[scope pipelineForFunction:@"grid_coordinates"]];for(unsigned j=0;j<4;j++)[c setKernelBuffer:n[@[@"coordinates",@"geometry",@"counter",@"p"][j]] offset:j==3?256:64 atIndex:j];[c concurrentDispatchThreadgroups:groups[i] threadsPerThreadgroup:local[i]];
  }
  require([scope prepareResidentComputeCommands:icb range:NSMakeRange(0,3) error:&error],error.localizedDescription?:@"Resident preparation failed");
  NSMutableArray*records=[NSMutableArray new],*baselines=[NSMutableArray new],*descriptors=[NSMutableArray new];
  auto readResource=[&](id<MTLBuffer>src)->NSData*{id<MTLBuffer>h=[d newBufferWithLength:src.length options:MTLResourceStorageModeManaged];require(h!=nil,@"Readback allocation failed");id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:src sourceOffset:0 toBuffer:h destinationOffset:0 size:src.length];[b synchronizeResource:h];[b endEncoding];require(complete(cb),@"Readback failed");return [NSData dataWithBytes:h.contents length:h.length];};
  for(unsigned i=0;i<3;i++){id<KPLabOriginRecord>slot=(id<KPLabOriginRecord>)[icb indirectComputeCommandAtIndex:i];require([slot respondsToSelector:@selector(record)],@"Record accessor missing");KPRecordedNativeCompute*r=slot.record;require(r&&r.residentDescriptorReady&&r.constants.length==65536&&r.descriptor.length==4096,@"Resident record invalid");NSData*c=readResource(r.constants),*qmd=readResource(r.descriptor);require(word(c,0x710)==0&&word(c,0x714)==0&&word(c,0x718)==0,@"Native initial origin is not zero");require([qmd subdataWithRange:NSMakeRange(0,256)]&&[[qmd subdataWithRange:NSMakeRange(0,256)]isEqual:[r.relocatedCommands subdataWithRange:NSMakeRange(184,256)]],@"Resident QMD differs");[records addObject:r];[baselines addObject:c];[descriptors addObject:qmd];save(c,[dir stringByAppendingPathComponent:[NSString stringWithFormat:@"baseline-%u.constants.bin",i]]);save(qmd,[dir stringByAppendingPathComponent:[NSString stringWithFormat:@"baseline-%u.qmd.bin",i]]);}
  NSMutableArray*runs=[NSMutableArray new];report[@"runs"]=runs;
  unsigned count=[mode isEqual:@"execute"]?7:1;
  for(unsigned trial=0;trial<count;trial++){@autoreleasepool{
   unsigned i=trial==0?0:(trial-1)/2;bool suppress=trial==0;bool shifted=trial>=2&&trial%2==0;NSDictionary*n=nodes[i];KPRecordedNativeCompute*r=records[i];uint32_t offsets[3]={0,0,0};if(shifted)memcpy(offsets,origins[i],sizeof(offsets));
   NSMutableData*expected=[baselines[i]mutableCopy];if(shifted){memcpy((char*)expected.mutableBytes+0x710,offsets,12);memcpy((char*)expected.mutableBytes+0x720,logicalGrid[i],12);memcpy((char*)expected.mutableBytes+0x730,nominal[i],12);memcpy((char*)expected.mutableBytes+0x740,logicalGroups[i],12);}id<MTLBuffer>stage=[d newBufferWithBytes:(char*)expected.bytes+0x710 length:64 options:MTLResourceStorageModeShared];require(stage!=nil,@"Builtin staging missing");id<MTLCommandBuffer>update=[q commandBuffer];id<MTLBlitCommandEncoder>b=[update blitCommandEncoder];[b copyFromBuffer:stage sourceOffset:0 toBuffer:r.constants destinationOffset:0x710 size:64];
   for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=n[[k stringByAppendingString:@"Host"]];memset(h.contents,0xa5,h.length);if([k isEqual:@"counter"])memset((char*)h.contents+64,0,4);[h didModifyRange:NSMakeRange(0,h.length)];[b copyFromBuffer:h sourceOffset:0 toBuffer:n[k] destinationOffset:0 size:h.length];}[b endEncoding];require(complete(update),@"Origin update failed");
   NSData*before=readResource(r.constants),*beforeQ=readResource(r.descriptor);require([before isEqual:expected]&&[beforeQ isEqual:descriptors[i]],@"Unexpected pre-execution constant or descriptor change");NSString*prefix=[dir stringByAppendingPathComponent:[NSString stringWithFormat:@"trial-%u",trial]];save(before,[prefix stringByAppendingString:@".before.constants.bin"]);save(beforeQ,[prefix stringByAppendingString:@".before.qmd.bin"]);
   id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];NSDictionary*proof=nil;error=nil;require([r encodeResidentDescriptorWithOwners:@[r] encoder:e suppress:suppress evidence:&proof error:&error],error.localizedDescription?:@"Resident encoding failed");[e endEncoding];
   if([mode isEqual:@"prepare"]){[runs addObject:@{@"trial":@(trial),@"node":@(i),@"suppressed":@(suppress),@"committed":@NO,@"proof":proof}];continue;}
   require(complete(cb),@"Resident launch failed");if(!suppress)report[@"user_dispatches"]=@([report[@"user_dispatches"]unsignedIntValue]+1);
   id<MTLCommandBuffer>read=[q commandBuffer];b=[read blitCommandEncoder];for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=n[[k stringByAppendingString:@"Host"]];[b copyFromBuffer:n[k] sourceOffset:0 toBuffer:h destinationOffset:0 size:h.length];[b synchronizeResource:h];}[b endEncoding];require(complete(read),@"Result readback failed");
   for(NSString*k in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=n[[k stringByAppendingString:@"Host"]];save([NSData dataWithBytes:h.contents length:h.length],[prefix stringByAppendingFormat:@".%@.bin",k]);}
   NSData*after=readResource(r.constants),*afterQ=readResource(r.descriptor);save(after,[prefix stringByAppendingString:@".after.constants.bin"]);save(afterQ,[prefix stringByAppendingString:@".after.qmd.bin"]);require([after isEqual:before]&&[afterQ isEqual:beforeQ],@"Resident state changed during execution");
   [runs addObject:@{@"trial":@(trial),@"node":@(i),@"origin":@[@(offsets[0]),@(offsets[1]),@(offsets[2])],@"suppressed":@(suppress),@"committed":@YES,@"command_status":@(cb.status),@"constants_SHA256":sha(before),@"QMD_SHA256":sha(beforeQ),@"proof":proof}];
  }}
  [scope restore];report[@"scope_restored"]=@(object_getClass(d)==original);require(object_getClass(d)==original,@"Scope was not restored");report[@"device"]=d.name;report[@"registry_id"]=@(d.registryID);report[@"status"]=@"PASS";
 }@catch(NSException*x){if(scope)[scope restore];report[@"scope_restored"]=@(d&&original&&object_getClass(d)==original);report[@"reason"]=x.reason?:@"";}
 NSData*j=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return [report[@"status"]isEqual:@"PASS"]?0:1;
}}
