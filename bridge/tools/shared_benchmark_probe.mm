#import "KeplerProgramImport.h"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <sys/resource.h>
#include <vector>
using Clock=std::chrono::steady_clock;
static double elapsed(Clock::time_point t){return std::chrono::duration<double,std::milli>(Clock::now()-t).count();}
static double cpu(){rusage r={};getrusage(RUSAGE_SELF,&r);return r.ru_utime.tv_sec*1000.+r.ru_utime.tv_usec*.001+r.ru_stime.tv_sec*1000.+r.ru_stime.tv_usec*.001;}
static bool finish(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
struct Parameters {uint64_t outputAddress;uint32_t seed,active,variant,operand;uint64_t progressAddress;};
static NSDictionary*run(id<MTLDevice>d,NSDictionary*c,NSMutableDictionary*cache,int*exitCode){
 NSDictionary*info=c[@"info"];NSString*kind=info[@"kind"];bool capacity=[kind isEqual:@"capacity"];
 unsigned local=[c[@"local"]unsignedIntValue],groups=[c[@"groups"]unsignedIntValue],batch=[c[@"batch"]unsignedIntValue],shared=[info[@"shared_bytes"]unsignedIntValue],words=shared/4;
 if((!capacity&&![kind isEqual:@"add"])||!groups||groups>64||!batch||batch>64||!local||local>1024||[info[@"scratch_bytes"]unsignedIntValue]||[info[@"crs_bytes"]unsignedIntValue]){*exitCode=2;return @{@"error":@"unqualified benchmark case"};}
 id<MTLComputePipelineState>pipelines[2]={nil,nil};NSDictionary*proof=nil;double setup[2]={0,0};
 for(unsigned path=0;path<2;path++){
  NSString*function=[NSString stringWithFormat:@"shared_%@_%@",kind,path?@"carrier":@"reference"],*key=[NSString stringWithFormat:@"%@|%@|%@",c[@"carrier"],c[@"code"],function];NSDictionary*entry=cache[key];
  if(entry){pipelines[path]=entry[@"pipeline"];if(path)proof=entry[@"proof"];continue;}
  NSError*error=nil;Clock::time_point start=Clock::now();
  if(path)pipelines[path]=KPCreatePipeline(d,[NSURL fileURLWithPath:c[@"carrier"]],function,[NSData dataWithContentsOfFile:c[@"code"]],{[info[@"registers"]unsignedIntValue],576,576},&error,&proof);
  else{id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:c[@"carrier"]]error:&error];id<MTLFunction>f=[lib newFunctionWithName:function];if(f)pipelines[path]=[d newComputePipelineStateWithFunction:f error:&error];[f release];[lib release];}
  setup[path]=elapsed(start);if(!pipelines[path]){*exitCode=3;return @{@"error":error.localizedDescription?:@"pipeline failed"};}
  cache[key]=@{@"pipeline":pipelines[path],@"proof":path?proof:@{}};[pipelines[path]release];
 }
 if(![proof[@"contract_verified"]boolValue]){*exitCode=3;return @{@"error":@"import not verified"};}
 for(unsigned path=0;path<2;path++)if(pipelines[path].staticThreadgroupMemoryLength<shared||pipelines[path].maxTotalThreadsPerThreadgroup<local){*exitCode=4;return @{@"error":@"pipeline limits"};}
 const unsigned count=capacity?groups*words*2:groups*(local+1);const size_t bytes=count*4+128;std::vector<unsigned char>initial(bytes,0xa5),progressInitial(136,0xa5);memset(progressInitial.data()+64,0,8);
 id<MTLBuffer>out=[[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate]autorelease],progress=[[d newBufferWithLength:136 options:MTLResourceStorageModePrivate]autorelease];
 id<MTLBuffer>host=[KPCreateHostBuffer(d,initial.data(),bytes,false)autorelease],hostProgress=[KPCreateHostBuffer(d,progressInitial.data(),136,false)autorelease];
 Parameters p={out.gpuAddress+64,0,local,0,0x12345678u,progress.gpuAddress+64};id<MTLBuffer>params=[[d newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared]autorelease];id<MTLCommandQueue>queue=[[d newCommandQueue]autorelease];
 if(!out||!progress||!host||!hostProgress||!params||!queue||!out.gpuAddress||!progress.gpuAddress){*exitCode=5;return @{@"error":@"allocation failed"};}
 id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[upload blitCommandEncoder];[blit copyFromBuffer:host sourceOffset:0 toBuffer:out destinationOffset:0 size:bytes];[blit copyFromBuffer:hostProgress sourceOffset:0 toBuffer:progress destinationOffset:0 size:136];[blit endEncoding];if(!finish(upload)){*exitCode=6;return @{@"error":@"upload failed"};}
 NSMutableArray*samples=[NSMutableArray array];const unsigned warmups=3,trials=9;unsigned mismatches=0,guards=0;
 // Alternate compiler order each round. Both paths use the same seed/workload.
 for(unsigned round=0;round<warmups+trials+1;round++)for(unsigned turn=0;turn<2;turn++){@autoreleasepool{
  unsigned path=(round+turn)&1;p.seed=0xfffffc00u+round*0x9e3779b9u;memcpy(params.contents,&p,sizeof p);
  auto resetStart=Clock::now();memset((unsigned char*)hostProgress.contents+64,0,8);[hostProgress didModifyRange:NSMakeRange(64,8)];id<MTLCommandBuffer>reset=[queue commandBuffer];blit=[reset blitCommandEncoder];[blit copyFromBuffer:hostProgress sourceOffset:64 toBuffer:progress destinationOffset:64 size:8];[blit endEncoding];if(!finish(reset)){*exitCode=6;return @{@"error":@"counter reset failed"};}double resetMS=elapsed(resetStart);
  auto start=Clock::now();double cpuStart=cpu();id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipelines[path]];[encoder setBuffer:params offset:0 atIndex:0];[encoder setBuffer:out offset:64 atIndex:1];[encoder setBuffer:progress offset:64 atIndex:2];for(unsigned i=0;i<batch;i++)[encoder dispatchThreadgroups:MTLSizeMake(groups,1,1)threadsPerThreadgroup:MTLSizeMake(local,1,1)];[encoder endEncoding];if(!finish(command)){*exitCode=7;return @{@"error":command.error.localizedDescription?:@"compute failed"};}double computeMS=elapsed(start),computeCPU=cpu()-cpuStart;
  start=Clock::now();cpuStart=cpu();id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];[blit copyFromBuffer:out sourceOffset:0 toBuffer:host destinationOffset:0 size:bytes];[blit copyFromBuffer:progress sourceOffset:0 toBuffer:hostProgress destinationOffset:0 size:136];[blit synchronizeResource:host];[blit synchronizeResource:hostProgress];[blit endEncoding];if(!finish(read)){*exitCode=8;return @{@"error":read.error.localizedDescription?:@"readback failed",@"error_code":@(read.error.code)};}double readMS=elapsed(start),readCPU=cpu()-cpuStart;
  const uint32_t*data=(const uint32_t*)((unsigned char*)host.contents+64);const uint32_t*marks=(const uint32_t*)((unsigned char*)hostProgress.contents+64);uint32_t checksum=0;
  for(unsigned g=0;g<groups;g++){
   if(capacity){for(unsigned phase=0;phase<2;phase++)for(unsigned i=0;i<words;i++){unsigned index=(i*(phase?7:5)+(phase?13:7))%words;uint32_t expected=(index*0x9e3779b9u)^(p.seed^(g*0x100001u))^(phase?0x6a09e667u:0);if(data[g*words*2+phase*words+i]!=expected)mismatches++;}checksum+=(7u*0x9e3779b9u)^(p.seed^(g*0x100001u));}
   else{uint32_t init=p.seed+g*0x100001u,final=data[g*(local+1)+local];if(final!=init+local)mismatches++;checksum+=init+local;std::vector<uint32_t>got(data+g*(local+1),data+g*(local+1)+local),expected;for(unsigned i=0;i<local;i++)expected.push_back(init+i);std::sort(got.begin(),got.end());std::sort(expected.begin(),expected.end());if(got!=expected)mismatches++;}
  }
  if(marks[0]!=groups*batch||marks[1]!=checksum*batch)mismatches++;
  for(size_t i=0;i<64;i++){if(((unsigned char*)host.contents)[i]!=0xa5||((unsigned char*)host.contents)[bytes-64+i]!=0xa5)guards++;if(((unsigned char*)hostProgress.contents)[i]!=0xa5||((unsigned char*)hostProgress.contents)[136-64+i]!=0xa5)guards++;}
  if(mismatches||guards){*exitCode=10;return @{@"error":@"numerical, progress or guard failure",@"mismatches":@(mismatches),@"guards":@(guards),@"path":path?@"nak":@"metal",@"actual_progress":@(marks[0]),@"expected_progress":@(groups*batch),@"actual_checksum":@(marks[1]),@"expected_checksum":@(checksum*batch)};}
  if(round>=warmups&&round<warmups+trials)[samples addObject:@{@"round":@(round-warmups),@"path":path?@"nak":@"metal",@"order":@(turn),@"seed":@(p.seed),@"counter_reset_wall_ms":@(resetMS),@"compute_submit_wait_wall_ms":@(computeMS),@"compute_host_cpu_ms":@(computeCPU),@"readback_wall_ms":@(readMS),@"readback_host_cpu_ms":@(readCPU),@"compute_plus_readback_wall_ms":@(computeMS+readMS),@"reported_GPU_command_ms":@((command.GPUEndTime-command.GPUStartTime)*1000),@"GPU_completed_groups":@(marks[0]),@"GPU_result_checksum":@(marks[1])}];
  if(round==warmups+trials){NSString*prefix=[[c[@"result"]stringByDeletingPathExtension]stringByAppendingString:path?@"-nak":@"-metal"];[[NSData dataWithBytes:host.contents length:bytes]writeToFile:[prefix stringByAppendingString:@".output.bin"]atomically:YES];[[NSData dataWithBytes:hostProgress.contents length:136]writeToFile:[prefix stringByAppendingString:@".progress.bin"]atomically:YES];}
 }}
 return @{@"device":d.name,@"registry_id":@(d.registryID),@"kind":kind,@"groups":@(groups),@"local":@(local),@"batch":@(batch),@"shared_bytes":@(shared),@"static_shared_bytes_metal":@(pipelines[0].staticThreadgroupMemoryLength),@"static_shared_bytes_nak":@(pipelines[1].staticThreadgroupMemoryLength),@"requested_Private_buffer_bytes":@(bytes+136),@"readback_bytes":@(bytes+136),@"warmups_per_path":@(warmups),@"trials_per_path":@(trials),@"samples":samples,@"mismatches":@(mismatches),@"guard_mismatches":@(guards),@"pipeline_setup_ms_metal":@(setup[0]),@"pipeline_setup_ms_nak":@(setup[1]),@"import":proof,@"actual_occupancy_measured":@NO,@"GPU_timestamps_qualified":@NO,@"scope":@"equivalent instrumented kernels; completion/checksum counters on GPU; repeated resident dispatches, separate reset/readback; no compiler setup or CPU validation in measured compute/readback time"};
}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;NSArray*plan=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])]options:0 error:nil];if(![plan isKindOfClass:[NSArray class]]||!plan.count||plan.count>16)return 1;id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(![device.name isEqual:@"NVIDIA GeForce GTX 880M"])return 2;NSMutableDictionary*cache=[NSMutableDictionary dictionary];
 for(NSDictionary*c in plan){@autoreleasepool{int status=0;NSDictionary*result=run(device,c,cache,&status);NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];[json writeToFile:c[@"result"]atomically:YES];printf("%s %d\n",[c[@"label"]UTF8String],status);fflush(stdout);if(status)return status;}}
 return 0;
}}
