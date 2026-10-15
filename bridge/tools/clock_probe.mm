#import "KeplerProgramImport.h"
#include <cmath>
#include <cstdio>
#include <cstring>
struct Parameters {uint64_t addresses[4];uint32_t grid[3],block[3];};
static bool finish(id<MTLCommandBuffer>command){[command commit];[command waitUntilCompleted];return command.status==MTLCommandBufferStatusCompleted;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=5)return 1;unsigned iterations=(unsigned)strtoul(argv[4],NULL,10);if(!iterations||iterations>1000000)return 2;
 NSDictionary*info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[3])] options:0 error:nil];
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();NSError*error=nil;NSDictionary*evidence=nil;
 id<MTLComputePipelineState>pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],@"add_buffers",[NSData dataWithContentsOfFile:@(argv[2])],{[info[@"registers"] unsignedIntValue],576,576},&error,&evidence);
 if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 unsigned char initial[64];memset(initial,0x5a,sizeof initial);
 id<MTLBuffer>out=[device newBufferWithLength:64 options:MTLResourceStorageModePrivate],host=KPCreateHostBuffer(device,initial,64,true);
 id<MTLBuffer>copyA=[device newBufferWithLength:1048576 options:MTLResourceStorageModePrivate],copyB=[device newBufferWithLength:1048576 options:MTLResourceStorageModePrivate];
 if(!out||!host||!copyA||!copyB)return 4;
 Parameters p={{0,0,out.gpuAddress,0},{iterations,1,1},{1,1,1}};
 id<MTLBuffer>params=[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];id<MTLCommandQueue>queue=[device newCommandQueue];
 id<MTLCommandBuffer>init=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[init blitCommandEncoder];[blit copyFromBuffer:host sourceOffset:0 toBuffer:out destinationOffset:0 size:64];[blit fillBuffer:copyA range:NSMakeRange(0,1048576) value:0];[blit endEncoding];if(!finish(init))return 4;
 float expected=0;for(unsigned i=0;i<iterations;i++)expected=std::fma(expected,.99999f,.125f);
 NSMutableArray*samples=[NSMutableArray array];unsigned bad=0;
 for(unsigned trial=0;trial<12;trial++){@autoreleasepool{
  bool withBlit=trial>=6;
  if(withBlit){id<MTLCommandBuffer>copy=[queue commandBuffer];blit=[copy blitCommandEncoder];[blit copyFromBuffer:copyA sourceOffset:0 toBuffer:copyB destinationOffset:0 size:1048576];[blit endEncoding];if(!finish(copy))return 4;}
  id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];[encoder setBuffer:params offset:0 atIndex:0];[encoder setBuffer:out offset:0 atIndex:1];[encoder useResource:out usage:MTLResourceUsageWrite];[encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[encoder endEncoding];if(!finish(command))return 5;
  id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];[blit copyFromBuffer:out sourceOffset:0 toBuffer:host destinationOffset:0 size:64];[blit endEncoding];if(!finish(read))return 6;
  uint64_t begin=0,end=0;float value=0;memcpy(&begin,host.contents,8);memcpy(&end,(const char*)host.contents+8,8);memcpy(&value,(const char*)host.contents+16,4);
  bool guards=memcmp((const char*)host.contents+20,initial+20,44)==0;
  if(end<=begin||value!=expected||!guards)bad++;
  double gpuSeconds=command.GPUEndTime-command.GPUStartTime;
  [samples addObject:@{@"trial":@(trial),@"preceded_by_blit":@(withBlit),@"clock_start":@(begin),@"clock_end":@(end),@"delta_cycles":@(end-begin),@"gpu_command_ms":@(gpuSeconds*1000),@"cycles_per_command_ns":@(double(end-begin)/(gpuSeconds*1e9)),@"value":@(value),@"expected":@(expected),@"guards_ok":@(guards)}];
 }}
 NSDictionary*result=@{@"device":device.name,@"import":evidence,@"iterations":@(iterations),@"failures":@(bad),@"samples":samples,@"note":@"cycles/whole-command time is an approximate lower estimate of SM clock, not a driver frequency query; one active thread, no clock changes"};NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(json)fwrite(json.bytes,1,json.length,stdout);putchar('\n');return bad?10:0;
}}
