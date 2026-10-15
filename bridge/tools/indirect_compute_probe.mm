// Native GPU-produced dispatch arguments; no ICB or program import.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <vector>
#include <cstdint>
#include <cstring>
struct P{uint32_t seed,groups,local,max_n;};
static void emit(NSDictionary*d){NSData*b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");}
static bool done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;NSString*mode=@(argv[3]);unsigned local=atoi(argv[4]),groups=atoi(argv[5]);
 bool direct=[mode isEqual:@"direct"],missing=[mode isEqual:@"missing_producer"];
 if((!direct&&!missing&&![mode isEqual:@"GPU_indirect"])||(local!=32&&local!=33&&local!=128)||(groups!=1&&groups!=3&&groups!=5)||(missing&&groups==1))return 1;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 NSError*error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
 id<MTLComputePipelineState>producer=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"produce_grid"] error:&error];
 id<MTLComputePipelineState>consumer=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"consume_grid"] error:&error];
 if(!producer||!consumer){emit(@{@"failure_stage":@"pipeline",@"error":error.description?:@"nil"});return 3;}
 unsigned n=local*groups;if(consumer.maxTotalThreadsPerThreadgroup<local)return 3;
 NSMutableArray*runs=[NSMutableArray new];id<MTLCommandQueue>q=[d newCommandQueue];unsigned totalBad=0;
 for(unsigned iteration=0;iteration<3;iteration++){@autoreleasepool{
  P params={0x1234u+37u*iteration,groups,local,640};const size_t outBytes=640*16+128,argsBytes=12+128,counterBytes=4+128;
  std::vector<uint8_t>outInitial(outBytes,0xa5),argsInitial(argsBytes,0xa5),counterInitial(counterBytes,0xa5);
  uint32_t initialGrid[3]={1,1,1},zero=0;memcpy(argsInitial.data()+64,initialGrid,12);memcpy(counterInitial.data()+64,&zero,4);
  id<MTLBuffer>output=[d newBufferWithLength:outBytes options:MTLResourceStorageModePrivate],args=[d newBufferWithLength:argsBytes options:MTLResourceStorageModePrivate],counter=[d newBufferWithLength:counterBytes options:MTLResourceStorageModePrivate];
  id<MTLBuffer>hostOut=[d newBufferWithBytes:outInitial.data() length:outBytes options:MTLResourceStorageModeManaged],hostArgs=[d newBufferWithBytes:argsInitial.data() length:argsBytes options:MTLResourceStorageModeManaged],hostCounter=[d newBufferWithBytes:counterInitial.data() length:counterBytes options:MTLResourceStorageModeManaged],p=[d newBufferWithBytes:&params length:sizeof params options:MTLResourceStorageModeShared];
  if(!output||!args||!counter||!hostOut||!hostArgs||!hostCounter||!p||args.storageMode!=MTLStorageModePrivate){emit(@{@"failure_stage":@"allocation",@"args_storage_mode":args?@(args.storageMode):@(-1),@"GPU_dispatch":@NO});return 4;}
  id<MTLCommandBuffer>up=[q commandBuffer];id<MTLBlitCommandEncoder>b=[up blitCommandEncoder];
  [b copyFromBuffer:hostOut sourceOffset:0 toBuffer:output destinationOffset:0 size:outBytes];[b copyFromBuffer:hostArgs sourceOffset:0 toBuffer:args destinationOffset:0 size:argsBytes];[b copyFromBuffer:hostCounter sourceOffset:0 toBuffer:counter destinationOffset:0 size:counterBytes];[b endEncoding];if(!done(up))return 5;
  id<MTLCommandBuffer>c=[q commandBuffer];
  if(!direct&&!missing){id<MTLComputeCommandEncoder>e=[c computeCommandEncoder];[e setComputePipelineState:producer];[e setBuffer:args offset:64 atIndex:0];[e setBuffer:p offset:0 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[e endEncoding];}
  id<MTLComputeCommandEncoder>e=[c computeCommandEncoder];[e setComputePipelineState:consumer];[e setBuffer:output offset:64 atIndex:0];[e setBuffer:counter offset:64 atIndex:1];[e setBuffer:p offset:0 atIndex:2];
  if(direct)[e dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];
  else [e dispatchThreadgroupsWithIndirectBuffer:args indirectBufferOffset:64 threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];
  if(!done(c)){emit(@{@"failure_stage":@"compute",@"status":@(c.status),@"error":c.error.description?:@""});return 6;}
  id<MTLCommandBuffer>read=[q commandBuffer];b=[read blitCommandEncoder];
  [b copyFromBuffer:output sourceOffset:0 toBuffer:hostOut destinationOffset:0 size:outBytes];[b copyFromBuffer:args sourceOffset:0 toBuffer:hostArgs destinationOffset:0 size:argsBytes];[b copyFromBuffer:counter sourceOffset:0 toBuffer:hostCounter destinationOffset:0 size:counterBytes];
  [b synchronizeResource:hostOut];[b synchronizeResource:hostArgs];[b synchronizeResource:hostCounter];[b endEncoding];if(!done(read))return 7;
  const uint8_t*raw=(const uint8_t*)hostOut.contents,*argRaw=(const uint8_t*)hostArgs.contents,*countRaw=(const uint8_t*)hostCounter.contents;
  const uint32_t*values=(const uint32_t*)(raw+64);uint32_t count=0;memcpy(&count,countRaw+64,4);unsigned actualGroups=missing?1:groups,actualN=actualGroups*local;
  unsigned bad=0,guardBad=0;
  for(unsigned i=0;i<actualN;i++){uint32_t wanted[4]={(params.seed*1664525u)^(i*1013904223u),i,actualGroups|0x01010000u,local};for(unsigned col=0;col<4;col++)bad+=values[4*i+col]!=wanted[col];}
  for(size_t i=0;i<64;i++){guardBad+=raw[i]!=0xa5;guardBad+=raw[outBytes-64+i]!=0xa5;guardBad+=argRaw[i]!=0xa5;guardBad+=argRaw[argsBytes-64+i]!=0xa5;guardBad+=countRaw[i]!=0xa5;guardBad+=countRaw[counterBytes-64+i]!=0xa5;}
  for(size_t i=64+actualN*16;i<outBytes-64;i++)guardBad+=raw[i]!=0xa5;
  uint32_t wantedArgs[3]={(!direct&&!missing)?groups:1u,1,1};bad+=count!=actualN;for(unsigned i=0;i<3;i++)bad+=((const uint32_t*)(argRaw+64))[i]!=wantedArgs[i];
  NSString*base=[@(argv[2]) stringByAppendingPathComponent:[NSString stringWithFormat:@"output-%u",iteration]];
  for(NSArray*item in @[@[@".bin",hostOut],@[@".args",hostArgs],@[@".count",hostCounter]]){id<MTLBuffer>buffer=item[1];if(![[NSData dataWithBytes:buffer.contents length:buffer.length]writeToFile:[base stringByAppendingString:item[0]] atomically:YES])return 8;}
  [runs addObject:@{@"iteration":@(iteration),@"seed":@(params.seed),@"base":base,@"actual_invocations":@(count),@"expected_direct_invocations":@(n),@"observed_groups":@(actualGroups),@"mismatches":@(bad),@"guard_mismatches":@(guardBad),@"command_status":@(c.status),@"readback_status":@(read.status),@"GPU_dispatch":@YES}];
  totalBad+=bad+guardBad;if(guardBad)break;
 }}
 emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"mode":mode,@"local":@(local),@"groups":@(groups),@"runs":runs,@"passed":@(!totalBad),@"guarded_max_elements":@640,@"args_private":@YES,@"args_CPU_read_before_dispatch":@NO,@"ICB_created":@NO,@"native_only":@YES,@"scope":@"Native indirect compute primitive, not an ICB implementation or performance benchmark"});return totalBad?10:0;
}}
