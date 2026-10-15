#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <vector>
#include <cstring>

struct Params {uint32_t seed,groups,local,max_n;};
static NSString *sha(NSData *d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
static void emit(NSDictionary *d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
static bool complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}

int main(int argc,char **argv){@autoreleasepool{
 if(argc!=4)return 1;bool execute=[@(argv[3])isEqual:@"execute"];if(!execute&&![@(argv[3])isEqual:@"prepare"])return 1;
 NSData*libraryBytes=[NSData dataWithContentsOfFile:@(argv[1])];if(![sha(libraryBytes)isEqual:@"b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d"])return 2;
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(d.registryID==4294968458){device=d;break;}if(!device)return 2;
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];id<MTLComputePipelineState>pipeline=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"consume_grid"] error:&error];id<MTLCommandQueue>queue=[device newCommandQueue];if(!pipeline||!queue)return 3;
 Class original=object_getClass(device);NSMutableArray*rows=[NSMutableArray new];unsigned mismatches=0;
 for(unsigned test=0;test<3;test++){@autoreleasepool{
  NSString*name=@[@"default_retained_drop_ICB",@"unretained_drop_ICB_not_submitted",@"automatic_scope_restore_before_commit"][test];
  bool unretained=test==1;uint32_t seed=0x7654+97*test;
  id<MTLCommandBuffer>commandBuffer=nil;KPCPUICBScope*manualScope=nil;
  __weak id<MTLIndirectCommandBuffer>weakICB;__weak id<MTLBuffer>weakOutput,weakCounter,weakParameters;
  __weak KPCPUICBScope*weakScope;__weak id<MTLComputeCommandEncoder>weakEncoder;
  id<MTLBuffer>hostOutput=[device newBufferWithLength:10368 options:MTLResourceStorageModeManaged];
  id<MTLBuffer>hostCounter=[device newBufferWithLength:132 options:MTLResourceStorageModeManaged];
  if(!hostOutput||!hostCounter)return 4;
  memset(hostOutput.contents,0xa5,hostOutput.length);memset(hostCounter.contents,0xa5,hostCounter.length);uint32_t zero=0;memcpy((char*)hostCounter.contents+64,&zero,4);
  [hostOutput didModifyRange:NSMakeRange(0,hostOutput.length)];[hostCounter didModifyRange:NSMakeRange(0,hostCounter.length)];
  @autoreleasepool{
   KPCPUICBScope*scope=[KPCPUICBScope installOnDevice:device queue:queue pipeline:pipeline error:&error];if(!scope)return 5;weakScope=scope;if(test!=2)manualScope=scope;
   id<MTLBuffer>output=[device newBufferWithLength:10368 options:MTLResourceStorageModePrivate];
   id<MTLBuffer>counter=[device newBufferWithLength:132 options:MTLResourceStorageModePrivate];
   Params p={seed,3,33,640};std::vector<uint8_t>bytes(512,0xa5);memcpy(bytes.data(),&p,sizeof(p));
   id<MTLBuffer>parameters=[device newBufferWithBytes:bytes.data() length:512 options:MTLResourceStorageModeShared];if(!output||!counter||!parameters)return 6;
   weakOutput=output;weakCounter=counter;weakParameters=parameters;
   id<MTLCommandBuffer>init=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];
   [b copyFromBuffer:hostOutput sourceOffset:0 toBuffer:output destinationOffset:0 size:10368];
   [b copyFromBuffer:hostCounter sourceOffset:0 toBuffer:counter destinationOffset:0 size:132];[b endEncoding];if(!complete(init))return 7;
   MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;desc.maxKernelBufferBindCount=3;
   id<MTLIndirectCommandBuffer>icb=[device newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];if(!icb)return 8;weakICB=icb;
   id<MTLIndirectComputeCommand>command=[icb indirectComputeCommandAtIndex:0];[command setComputePipelineState:pipeline];[command setKernelBuffer:output offset:64 atIndex:0];[command setKernelBuffer:counter offset:64 atIndex:1];[command setKernelBuffer:parameters offset:0 atIndex:2];[command concurrentDispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(33,1,1)];
   commandBuffer=unretained?[queue commandBufferWithUnretainedReferences]:[queue commandBuffer];
   id<MTLComputeCommandEncoder>encoder=[commandBuffer computeCommandEncoder];weakEncoder=encoder;if(![scope adaptComputeEncoder:encoder error:&error])return 9;
   @try{[encoder executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];}@catch(NSException*x){emit(@{@"failure_stage":@"lifetime_encode",@"case":name,@"reason":x.reason?:@"nil"});return 10;}[encoder endEncoding];
  }
  // The ICB and all application references to its private resources are gone.
  // These observations precede any new strong readback reference.
  bool icbReleased=weakICB==nil,outputAlive=weakOutput!=nil,counterAlive=weakCounter!=nil;
  bool parameterAlive=weakParameters!=nil,encoderReleased=weakEncoder==nil;
  bool automaticReleased=test==2&&weakScope==nil;
  if(!icbReleased)return 11;
  if(unretained){if(outputAlive||counterAlive)return 12;}else if(!outputAlive||!counterAlive)return 13;
  if(test==2&&(!automaticReleased||object_getClass(device)!=original))return 14;
  NSArray*events=@[];if(manualScope){[manualScope restore];events=manualScope.events;manualScope=nil;}
  bool restored=object_getClass(device)==original,scopeReleased=weakScope==nil;if(!restored||!scopeReleased)return 15;
  unsigned count=0,bad=0;bool submitted=false;
  if(!unretained){
   // Completion may release retained resources. Observe ownership first, then
   // place the readback in the same CB rather than reacquiring freed buffers.
   @autoreleasepool{
    id<MTLBuffer>output=weakOutput,counter=weakCounter;if(!output||!counter)return 17;
    id<MTLCommandBuffer>read=execute?commandBuffer:[queue commandBuffer];id<MTLBlitCommandEncoder>b=[read blitCommandEncoder];
    [b copyFromBuffer:output sourceOffset:0 toBuffer:hostOutput destinationOffset:0 size:10368];
    [b copyFromBuffer:counter sourceOffset:0 toBuffer:hostCounter destinationOffset:0 size:132];
    [b synchronizeResource:hostOutput];[b synchronizeResource:hostCounter];[b endEncoding];if(!execute&&!complete(read))return 18;
   }
   if(execute){if(!complete(commandBuffer))return 16;submitted=true;}
   memcpy(&count,(char*)hostCounter.contents+64,4);bad+=count!=(execute?99u:0u);
   const uint8_t*raw=(const uint8_t*)hostOutput.contents;
   if(execute){const uint32_t*v=(const uint32_t*)(raw+64);for(unsigned i=0;i<99;i++){uint32_t wanted[4]={(seed*1664525u)^(i*1013904223u),i,0x01010003u,33};for(unsigned j=0;j<4;j++)bad+=v[4*i+j]!=wanted[j];}for(size_t i=64+99*16;i<hostOutput.length;i++)bad+=raw[i]!=0xa5;}
   else for(size_t i=0;i<hostOutput.length;i++)bad+=raw[i]!=0xa5;
   for(size_t i=0;i<64;i++)bad+=raw[i]!=0xa5;
   const uint8_t*c=(const uint8_t*)hostCounter.contents;for(size_t i=0;i<64;i++)bad+=c[i]!=0xa5||c[hostCounter.length-64+i]!=0xa5;
  }
  NSString*base=[@(argv[2])stringByAppendingPathComponent:[NSString stringWithFormat:@"case-%u",test]];
  for(NSArray*f in @[@[@".output.bin",hostOutput],@[@".counter.bin",hostCounter]]){id<MTLBuffer>b=f[1];[[NSData dataWithBytes:b.contents length:b.length]writeToFile:[base stringByAppendingString:f[0]] atomically:YES];}
  [rows addObject:@{@"case":name,@"seed":@(seed),@"command_buffer_retainedReferences":@(commandBuffer.retainedReferences),@"ICB_released_before_commit":@(icbReleased),@"private_output_alive_before_commit":@(outputAlive),@"private_counter_alive_before_commit":@(counterAlive),@"shared_parameters_alive_before_commit":@(parameterAlive),@"ended_encoder_already_released":@(encoderReleased),@"scope_released_before_commit":@(scopeReleased),@"automatic_scope_release":@(automaticReleased),@"device_class_restored_before_commit":@(restored),@"main_command_buffer_committed":@(submitted),@"readback_encoded_before_submit":@(execute&&!unretained),@"unretained_control_never_submitted":@(unretained),@"actual_invocations":@(count),@"mismatches":@(bad),@"events":events}];mismatches+=bad;
 }}
 emit(@{@"mode":execute?@"execute":@"prepare",@"cases":rows,@"passed":@(!mismatches),@"integration_level":@1,@"system_modified":@NO,@"device_class_restored":@(object_getClass(device)==original),@"scope":@"Pinned native CPU ICB lifetime subset. Default command buffers retain private bindings after application ICB release; unretained negative is never submitted. Shared buffer destruction/cache and general concurrent lifecycle are not qualified."});return mismatches?19:0;
}}
