#import "KeplerProgramImport.h"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <sys/resource.h>
#include <vector>
using Clock=std::chrono::steady_clock;
static double ms(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
static double cpuMS(){rusage r={};getrusage(RUSAGE_SELF,&r);return r.ru_utime.tv_sec*1000.+r.ru_utime.tv_usec*.001+r.ru_stime.tv_sec*1000.+r.ru_stime.tv_usec*.001;}
__attribute__((noinline)) static void add(const float*__restrict a,const float*__restrict b,float*__restrict c,size_t n){for(size_t i=0;i<n;i++)c[i]=a[i]+b[i];}
struct Parameters {uint64_t addresses[4];uint32_t grid[3],block[3];};
static_assert(sizeof(Parameters)==56,"CB2 ABI");
static bool finish(id<MTLCommandBuffer>command){[command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"%s\n",command.error.description.UTF8String);return false;}return true;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6){fprintf(stderr,"usage: nak_memory_bench CARRIER.metallib CODE.sass shared|managed|private|private_nocopy resident|roundtrip COUNT\n");return 1;}
 NSString*mode=@(argv[3]),*policy=@(argv[4]);
 bool noCopy=[mode isEqualToString:@"private_nocopy"],priv=[mode isEqualToString:@"private"]||noCopy,managed=[mode isEqualToString:@"managed"],resident=[policy isEqualToString:@"resident"];
 if(!priv&&!managed&&![mode isEqualToString:@"shared"])return 2;
 if(!resident&&![policy isEqualToString:@"roundtrip"])return 2;
 uint32_t count=(uint32_t)strtoul(argv[5],NULL,10);if(!count||count>1048576)return 2;
 uint32_t total=(count+78)&~31u;size_t bytes=total*sizeof(float);constexpr float guard=-123456.f;
 std::vector<float>a(total),b(total),initial(total,guard),reference(count),download(total);
 for(uint32_t i=0;i<total;i++){a[i]=float(int(i%127)-63)*.25f;b[i]=float(int(i%31)-15)*.5f;}
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 3;
 NSError*error=nil;NSDictionary*importEvidence=nil;
 id<MTLComputePipelineState>pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],@"add_buffers",[NSData dataWithContentsOfFile:@(argv[2])],{24,576,576},&error,&importEvidence);
 if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 4;}
 MTLResourceOptions storage=priv?MTLResourceStorageModePrivate:(managed?MTLResourceStorageModeManaged:MTLResourceStorageModeShared);
 id<MTLBuffer>ga=[device newBufferWithLength:bytes options:storage],gb=[device newBufferWithLength:bytes options:storage],go=[device newBufferWithLength:bytes options:storage];
 id<MTLBuffer>sa=priv?KPCreateHostBuffer(device,nullptr,bytes,noCopy):ga;
 id<MTLBuffer>sb=priv?KPCreateHostBuffer(device,nullptr,bytes,noCopy):gb;
 id<MTLBuffer>so=priv?KPCreateHostBuffer(device,nullptr,bytes,noCopy):go;
 id<MTLBuffer>gn=[device newBufferWithBytes:&count length:4 options:MTLResourceStorageModeShared];
 if(!ga||!gb||!go||!sa||!sb||!so||!gn||!ga.gpuAddress||!gb.gpuAddress||!go.gpuAddress||!gn.gpuAddress)return 5;
 Parameters p={{ga.gpuAddress,gb.gpuAddress,go.gpuAddress,gn.gpuAddress},{count,1,1},{32,1,1}};
 id<MTLBuffer>params=[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];
 id<MTLCommandQueue>queue=[device newCommandQueue];if(!params||!queue)return 5;
 auto upload=[&](double&gpu)->bool{
  memcpy(sa.contents,a.data(),bytes);memcpy(sb.contents,b.data(),bytes);memcpy(so.contents,initial.data(),bytes);
  if((priv&&!noCopy)||managed){[sa didModifyRange:NSMakeRange(0,bytes)];[sb didModifyRange:NSMakeRange(0,bytes)];[so didModifyRange:NSMakeRange(0,bytes)];}
  gpu=0;
  if(priv){id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[command blitCommandEncoder];
   [blit copyFromBuffer:sa sourceOffset:0 toBuffer:ga destinationOffset:0 size:bytes];
   [blit copyFromBuffer:sb sourceOffset:0 toBuffer:gb destinationOffset:0 size:bytes];
   [blit copyFromBuffer:so sourceOffset:0 toBuffer:go destinationOffset:0 size:bytes];
   [blit endEncoding];if(!finish(command))return false;gpu=(command.GPUEndTime-command.GPUStartTime)*1000;
  }return true;
 };
 auto readback=[&](double&gpu)->bool{
  gpu=0;
  if(priv||managed){id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[command blitCommandEncoder];
   if(priv)[blit copyFromBuffer:go sourceOffset:0 toBuffer:so destinationOffset:0 size:bytes];
   if(so.storageMode==MTLStorageModeManaged)[blit synchronizeResource:so];[blit endEncoding];if(!finish(command))return false;gpu=(command.GPUEndTime-command.GPUStartTime)*1000;
  }memcpy(download.data(),so.contents,bytes);return true;
 };
 Clock::time_point start=Clock::now();double initialUploadGPU=0,initialUploadCPU=cpuMS();if(!upload(initialUploadGPU))return 6;
 initialUploadCPU=cpuMS()-initialUploadCPU;double initialUploadMS=ms(start);
 NSMutableArray*samples=[NSMutableArray array];unsigned bad=0,badGuard=0;
 for(unsigned trial=0;trial<12;trial++){@autoreleasepool{
  start=Clock::now();double referenceCPU=cpuMS();add(a.data(),b.data(),reference.data(),count);referenceCPU=cpuMS()-referenceCPU;double referenceMS=ms(start);
  double uploadGPU=0,uploadMS=0,uploadCPU=0;
  if(!resident){start=Clock::now();uploadCPU=cpuMS();if(!upload(uploadGPU))return 6;uploadCPU=cpuMS()-uploadCPU;uploadMS=ms(start);}
  start=Clock::now();double hostCPU=cpuMS();
  id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];
  [encoder setComputePipelineState:pipeline];[encoder setBuffer:params offset:0 atIndex:0];[encoder setBuffer:go offset:0 atIndex:1];
  [encoder useResource:ga usage:MTLResourceUsageRead];[encoder useResource:gb usage:MTLResourceUsageRead];[encoder useResource:gn usage:MTLResourceUsageRead];[encoder useResource:go usage:MTLResourceUsageWrite];
  [encoder dispatchThreadgroups:MTLSizeMake(total/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[encoder endEncoding];if(!finish(command))return 7;
  hostCPU=cpuMS()-hostCPU;double computeWallMS=ms(start);
  double readGPU=0,readMS=0,readCPU=0;
  if(!resident){start=Clock::now();readCPU=cpuMS();if(!readback(readGPU))return 8;readCPU=cpuMS()-readCPU;readMS=ms(start);
   for(uint32_t i=0;i<count;i++)if(download[i]!=reference[i])bad++;
   for(uint32_t i=count;i<total;i++)if(download[i]!=guard)badGuard++;
  }
  if(trial>=3)[samples addObject:@{@"trial":@(trial-3),@"cpu_reference_wall_ms":@(referenceMS),@"cpu_reference_consumed_ms":@(referenceCPU),
   @"gpu_command_ms":@((command.GPUEndTime-command.GPUStartTime)*1000),@"compute_submit_wait_wall_ms":@(computeWallMS),@"compute_host_cpu_ms":@(hostCPU),
   @"upload_wall_ms":@(uploadMS),@"upload_cpu_ms":@(uploadCPU),@"upload_gpu_ms":@(uploadGPU),@"readback_wall_ms":@(readMS),@"readback_cpu_ms":@(readCPU),@"readback_gpu_ms":@(readGPU),
   @"wall_with_copies_ms":@(uploadMS+computeWallMS+readMS),@"host_cpu_with_copies_ms":@(uploadCPU+hostCPU+readCPU)}];
  if(bad||badGuard)break;
 }}
 start=Clock::now();double finalReadGPU=0,finalReadCPU=cpuMS();if(!readback(finalReadGPU))return 8;finalReadCPU=cpuMS()-finalReadCPU;double finalReadMS=ms(start);
 if(resident){for(uint32_t i=0;i<count;i++)if(download[i]!=reference[i])bad++;for(uint32_t i=count;i<total;i++)if(download[i]!=guard)badGuard++;}
 NSDictionary*result=@{@"device":device.name,@"registry_id":@(device.registryID),@"memory_mode":mode,@"policy":policy,@"elements":@(count),@"guards":@(total-count),@"warmups":@3,@"measured_trials":@(samples.count),
  @"mismatches":@(bad),@"changed_guards":@(badGuard),@"import":importEvidence,@"samples":samples,
  @"initial_upload_wall_ms":@(initialUploadMS),@"initial_upload_cpu_ms":@(initialUploadCPU),@"initial_upload_gpu_ms":@(initialUploadGPU),
  @"final_readback_wall_ms":@(finalReadMS),@"final_readback_cpu_ms":@(finalReadCPU),@"final_readback_gpu_ms":@(finalReadGPU),
  @"requested_private_bytes":@(priv?bytes*3:0),@"requested_managed_bytes":@(((priv&&!noCopy)||managed)?bytes*3:0),@"no_copy_host_pages":@(noCopy),@"metal_reported_allocated_bytes":@(device.currentAllocatedSize),
  @"memory_note":noCopy?@"Private GPU buffers with NoCopy Shared host pages and GPU blits; page pointer identity checked; physical VRAM occupancy not inferred":@"Private uses Managed staging and GPU blits; Managed readback explicitly synchronizes; physical VRAM occupancy not inferred from allocations",
  @"timing_note":@"three warmups and nine measured runs; resident excludes one initial upload and one final readback; CPU consumption is getrusage of this process"};
 NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(json)fwrite(json.bytes,1,json.length,stdout);putchar('\n');
 return bad||badGuard?10:0;
}}
