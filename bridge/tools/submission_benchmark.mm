#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <sys/resource.h>
#include <time.h>
#include <vector>

struct Params { uint32_t seed,n,step; };
static double wall() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
static double threadCPU() { struct timespec t; clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t); return t.tv_sec+t.tv_nsec*1e-9; }
static double processCPU() { struct rusage u; getrusage(RUSAGE_SELF,&u); return u.ru_utime.tv_sec+u.ru_utime.tv_usec*1e-6+u.ru_stime.tv_sec+u.ru_stime.tv_usec*1e-6; }
static void emit(NSDictionary*d) { NSData*b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil]; fwrite(b.bytes,1,b.length,stdout);puts("");fflush(stdout); }
static bool finish(id<MTLCommandBuffer>c) { [c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted; }
int main(int argc,char**argv) { @autoreleasepool {
 if(argc!=3&&argc!=4)return 1;bool threeModes=argc==4&&strcmp(argv[3],"three_modes")==0;id<MTLDevice>d=nil;
 for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 NSError*error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
 id<MTLComputePipelineState>prod=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"benchmark_produce"] error:&error];
 id<MTLComputePipelineState>cons=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"benchmark_consume"] error:&error];
 if(!prod||!cons){emit(@{@"failure_stage":@"pipeline",@"error":error.description?:@"nil"});return 3;}
 const unsigned n=32768,steps=32,local=128;const size_t bytes=n*4+128;
 if(local>prod.maxTotalThreadsPerThreadgroup||local>cons.maxTotalThreadsPerThreadgroup)return 4;
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLBuffer>a=[d newBufferWithLength:n*4 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>b=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>params=[d newBufferWithLength:steps*256 options:MTLResourceStorageModeShared];
 id<MTLBuffer>host=[d newBufferWithLength:bytes options:MTLResourceStorageModeManaged];
 id<MTLBuffer>counter=[d newBufferWithLength:132 options:MTLResourceStorageModePrivate],audit=[d newBufferWithLength:384 options:MTLResourceStorageModePrivate];
 id<MTLBuffer>counterHost=[d newBufferWithLength:132 options:MTLResourceStorageModeManaged],auditHost=[d newBufferWithLength:384 options:MTLResourceStorageModeManaged];
 std::vector<uint8_t>initial(bytes,0xa5);id<MTLBuffer>staging=[d newBufferWithBytes:initial.data() length:bytes options:MTLResourceStorageModeShared];
 if(!a||!b||!params||!host||!staging||!counter||!audit||!counterHost||!auditHost)return 5;
 NSMutableArray*records=[NSMutableArray new];
 unsigned modeCount=threeModes?3:2;
 for(unsigned pair=0;pair<12;pair++)for(unsigned position=0;position<modeCount;position++){@autoreleasepool{
  unsigned choice=threeModes?(position+pair%3)%3:(position^(pair&1))*2;
  bool batched=choice==2,deferred=choice==1;NSString*mode=batched?@"batch32":deferred?@"submit32_wait_end":@"wait_each";
  for(unsigned k=0;k<steps;k++){Params p={0x1234u+pair*37u+k*101u,n,k};memcpy((uint8_t*)params.contents+k*256,&p,sizeof p);}
  double t=wall();id<MTLCommandBuffer>up=[q commandBuffer];id<MTLBlitCommandEncoder>be=[up blitCommandEncoder];
  [be fillBuffer:a range:NSMakeRange(0,a.length) value:0];[be copyFromBuffer:staging sourceOffset:0 toBuffer:b destinationOffset:0 size:bytes];[be endEncoding];
  be=[up blitCommandEncoder];[be fillBuffer:counter range:NSMakeRange(0,132) value:0xa5];[be fillBuffer:counter range:NSMakeRange(64,4) value:0];
  [be fillBuffer:audit range:NSMakeRange(0,384) value:0xa5];[be endEncoding];
  if(!finish(up))return 6;double upload=wall()-t;
  double totalStart=wall(),cpuStart=processCPU(),threadStart=threadCPU();double encodeWall=0,encodeCPU=0,submitWall=0,submitCPU=0,waitWall=0,waitCPU=0;
  unsigned count=batched?1:steps;NSMutableArray*pending=[NSMutableArray new];
  for(unsigned cbIndex=0;cbIndex<count;cbIndex++){@autoreleasepool{
   double ew=wall(),ec=threadCPU();id<MTLCommandBuffer>c=[q commandBuffer];unsigned begin=batched?0:cbIndex,end=batched?steps:cbIndex+1;
   for(unsigned k=begin;k<end;k++){
    id<MTLComputeCommandEncoder>e=[c computeCommandEncoder];[e setComputePipelineState:prod];[e setBuffer:a offset:0 atIndex:0];[e setBuffer:params offset:k*256 atIndex:2];
    [e setBuffer:counter offset:64 atIndex:3];[e setBuffer:audit offset:64 atIndex:4];
    [e dispatchThreadgroups:MTLSizeMake(n/local,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];
    e=[c computeCommandEncoder];[e setComputePipelineState:cons];[e setBuffer:a offset:0 atIndex:0];[e setBuffer:b offset:64 atIndex:1];[e setBuffer:params offset:k*256 atIndex:2];
    [e setBuffer:counter offset:64 atIndex:3];[e setBuffer:audit offset:64 atIndex:4];
    [e dispatchThreadgroups:MTLSizeMake(n/local,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];
   }
   encodeWall+=wall()-ew;encodeCPU+=threadCPU()-ec;
   double sw=wall(),sc=threadCPU();[c commit];submitWall+=wall()-sw;submitCPU+=threadCPU()-sc;
   if(deferred)[pending addObject:c];
   else{
    double ww=wall(),wc=threadCPU();[c waitUntilCompleted];waitWall+=wall()-ww;waitCPU+=threadCPU()-wc;
    if(c.status!=MTLCommandBufferStatusCompleted){emit(@{@"failure_stage":@"GPU_execution",@"mode":mode,@"status":@(c.status),@"error":c.error.description?:@""});return 7;}
   }
  }}
  if(deferred){
   double ww=wall(),wc=threadCPU();[(id<MTLCommandBuffer>)pending.lastObject waitUntilCompleted];waitWall+=wall()-ww;waitCPU+=threadCPU()-wc;
   for(id<MTLCommandBuffer>c in pending)if(c.status!=MTLCommandBufferStatusCompleted){emit(@{@"failure_stage":@"GPU_execution",@"mode":mode,@"status":@(c.status),@"error":c.error.description?:@""});return 7;}
  }
  double total=wall()-totalStart,processCost=processCPU()-cpuStart,threadCost=threadCPU()-threadStart;
  t=wall();id<MTLCommandBuffer>read=[q commandBuffer];be=[read blitCommandEncoder];[be copyFromBuffer:b sourceOffset:0 toBuffer:host destinationOffset:0 size:bytes];[be synchronizeResource:host];
  [be copyFromBuffer:counter sourceOffset:0 toBuffer:counterHost destinationOffset:0 size:132];[be synchronizeResource:counterHost];
  [be copyFromBuffer:audit sourceOffset:0 toBuffer:auditHost destinationOffset:0 size:384];[be synchronizeResource:auditHost];[be endEncoding];
  if(!finish(read))return 8;double readback=wall()-t;
  unsigned bad=0,guards=0;const uint8_t*data=(const uint8_t*)host.contents;unsigned seed=0x1234u+pair*37u+(steps-1)*101u;
  for(unsigned i=0;i<n;i++){uint32_t observed,expected=(((i*1664525u)^seed)+i*1013904223u)^(seed*747796405u);memcpy(&observed,data+64+i*4,4);bad+=observed!=expected;}
  for(unsigned i=0;i<64;i++)guards+=(data[i]!=0xa5)+(data[bytes-64+i]!=0xa5);
  NSString*path=[@(argv[2]) stringByAppendingPathComponent:[NSString stringWithFormat:@"pair-%u-%@.bin",pair,mode]];
  [[NSData dataWithBytes:data length:bytes]writeToFile:path atomically:YES];
  NSString*counterPath=[path stringByAppendingString:@".counter"],*auditPath=[path stringByAppendingString:@".audit"];
  [[NSData dataWithBytes:counterHost.contents length:132]writeToFile:counterPath atomically:YES];
  [[NSData dataWithBytes:auditHost.contents length:384]writeToFile:auditPath atomically:YES];
  uint32_t actualDispatches;memcpy(&actualDispatches,(uint8_t*)counterHost.contents+64,4);
  for(unsigned k=0;k<steps;k++){
   unsigned s=0x1234u+pair*37u+k*101u;const uint32_t*v=(const uint32_t*)((uint8_t*)auditHost.contents+64);
   bad+=(v[2*k]!=s)+(v[2*k+1]!=(s^(s*747796405u)));
  }
  bad+=actualDispatches!=2*steps;
  [records addObject:@{@"pair":@(pair),@"warmup":@(pair<3),@"position":@(position),@"mode":mode,@"final_seed":@(seed),@"elements":@(n),@"steps":@(steps),@"dispatches":@(2*steps),@"command_buffers":@(count),
     @"wait_calls":@(deferred||batched?1:steps),@"all_command_buffers_completed":@YES,
     @"total_wall_ms":@(total*1000),@"thread_cpu_ms":@(threadCost*1000),@"process_cpu_ms":@(processCost*1000),@"encoding_wall_ms":@(encodeWall*1000),@"encoding_thread_cpu_ms":@(encodeCPU*1000),
     @"submit_wall_ms":@(submitWall*1000),@"submit_thread_cpu_ms":@(submitCPU*1000),@"wait_wall_ms":@(waitWall*1000),@"wait_thread_cpu_ms":@(waitCPU*1000),
     @"upload_wall_ms":@(upload*1000),@"readback_wall_ms":@(readback*1000),@"mismatches":@(bad),@"guard_mismatches":@(guards),@"output_file":path,
     @"GPU_dispatch_count":@(actualDispatches),@"counter_file":counterPath,@"audit_file":auditPath}];
  if(bad||guards){emit(@{@"failure_stage":@"numeric_validation",@"records":records});return 9;}
 }}
 emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"passed":@YES,@"records":records,@"same_GPU_work_per_sample":@YES,
        @"warmup_pairs":@3,@"measured_pairs":@9,@"mode_count":@(modeCount),@"resource_lifetime":@"same buffers/pipelines throughout all modes",
        @"GPU_exclusive_time_measured":@NO,@"scope":@"Native application submission batching, not a driver patch or CPU-vs-GPU arithmetic benchmark"});return 0;
}}
