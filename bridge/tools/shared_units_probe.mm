#import "KeplerProgramImport.h"
#include <algorithm>
#include <cstring>
#include <vector>
struct Parameters {uint64_t outputAddress;uint32_t seed,active,variant,operand;};
static void emit(NSDictionary *d){NSData *b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");fflush(stdout);}
static bool finish(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static NSDictionary *runCase(id<MTLDevice>device,NSMutableDictionary *pipelines,NSDictionary *c,int *status){
 NSString *kind=c[@"info"][@"kind"],*mode=c[@"mode"];NSDictionary *info=c[@"info"];
 bool capacity=[kind isEqual:@"capacity"],add=[kind isEqual:@"add"],exchange=[kind isEqual:@"exchange"],cas=[kind isEqual:@"cas"],nak=[mode isEqual:@"nak"],control=[mode isEqual:@"control"],noCopy=[c[@"staging"]isEqual:@"nocopy"];
 unsigned local=[c[@"local"]unsignedIntValue],groups=[c[@"groups"]unsignedIntValue],active=[c[@"active"]unsignedIntValue],variant=[c[@"variant"]unsignedIntValue],shared=[info[@"shared_bytes"]unsignedIntValue];
 if((!capacity&&!add&&!exchange&&!cas)||(!nak&&!control&&![mode isEqual:@"reference"])||(!noCopy&&![c[@"staging"]isEqual:@"managed"])||!local||local>1024||!groups||groups>3||variant>1||(!capacity&&(!active||active>local))||[info[@"sm"]unsignedIntValue]!=30||[info[@"scratch_bytes"]unsignedIntValue]||[info[@"crs_bytes"]unsignedIntValue]||shared>device.maxThreadgroupMemoryLength){*status=2;return @{@"error":@"unqualified fixture configuration"};}
 NSString *function=[NSString stringWithFormat:@"shared_%@_%@",kind,nak?@"carrier":(control?@"control":@"reference")];
 NSString *cacheKey=[NSString stringWithFormat:@"%@|%@|%@|%@",c[@"carrier"],c[@"code"],function,info[@"registers"]];
 NSDictionary *cached=pipelines[cacheKey];bool reused=cached!=nil;
 NSError *error=nil;NSDictionary *proof=nil;id<MTLComputePipelineState>pipeline=nil;
 if(cached){pipeline=cached[@"pipeline"];proof=cached[@"proof"];}
 else if(nak)pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:c[@"carrier"]],function,[NSData dataWithContentsOfFile:c[@"code"]],{[info[@"registers"]unsignedIntValue],576,576},&error,&proof);
 else{ id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:c[@"carrier"]] error:&error];id<MTLFunction>entry=[library newFunctionWithName:function];if(entry)pipeline=[device newComputePipelineStateWithFunction:entry error:&error];[entry release];[library release]; }
 if(!pipeline){*status=3;return @{@"error":error.description?:@"pipeline failed",@"import":proof?:@{}};}if(!reused){pipelines[cacheKey]=@{@"pipeline":pipeline,@"proof":proof?:@{}};[pipeline release];}
 if(pipeline.staticThreadgroupMemoryLength<shared||pipeline.maxTotalThreadsPerThreadgroup<local){*status=4;return @{@"error":@"carrier limits insufficient",@"static_threadgroup_bytes":@(pipeline.staticThreadgroupMemoryLength),@"max_total_threads":@(pipeline.maxTotalThreadsPerThreadgroup)};}
 const unsigned words=shared/4,count=capacity?groups*words*2:groups*(local+1);size_t bytes=count*4+128;std::vector<unsigned char>initial(bytes,0xa5);
 id<MTLBuffer>output=[[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate]autorelease],host=[KPCreateHostBuffer(device,initial.data(),bytes,noCopy)autorelease];if(!output||!host||!output.gpuAddress){*status=5;return @{@"error":@"resource allocation failed"};}
 Parameters p={output.gpuAddress+64,variant?0xfffffff0u:0xf00d5000u,active,variant,0x12345678u};
 id<MTLBuffer>params=[[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared]autorelease];id<MTLCommandQueue>queue=[[device newCommandQueue]autorelease];if(!params||!queue){*status=5;return @{@"error":@"params/queue failed"};}
 id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[upload blitCommandEncoder];[blit copyFromBuffer:host sourceOffset:0 toBuffer:output destinationOffset:0 size:bytes];[blit endEncoding];if(!finish(upload)){*status=6;return @{@"error":@"upload failed"};}
 id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];[encoder setBuffer:params offset:0 atIndex:0];[encoder setBuffer:output offset:64 atIndex:1];[encoder dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[encoder endEncoding];if(!finish(command)){*status=7;return @{@"error":command.error.description?:@"GPU command failed",@"command_status":@(command.status)};}
 id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];[blit copyFromBuffer:output sourceOffset:0 toBuffer:host destinationOffset:0 size:bytes];if(!noCopy)[blit synchronizeResource:host];[blit endEncoding];if(!finish(read)){*status=8;return @{@"error":@"readback failed",@"command_status":@(command.status),@"readback_status":@(read.status),@"readback_error":read.error.localizedDescription?:@"",@"readback_error_domain":read.error.domain?:@"",@"readback_error_code":@(read.error.code),@"device":device.name};}
 const uint32_t *values=(const uint32_t*)((const unsigned char*)host.contents+64);unsigned bad=0,guardBad=0;const uint32_t groupKey=0x00100001u,controlKey=control?0xabad1deau:0;
 if(capacity){for(unsigned g=0;g<groups;g++)for(unsigned phase=0;phase<2;phase++)for(unsigned i=0;i<words;i++){
  unsigned index=(i*(phase?7:5)+(phase?13:7))%words;uint32_t expected=(index*0x9e3779b9u)^(p.seed^(g*groupKey))^(phase?0x6a09e667u:0)^controlKey;
  if(values[g*words*2+phase*words+i]!=expected)bad++;
 }}else for(unsigned g=0;g<groups;g++){
  uint32_t initialValue=p.seed+g*groupKey,final=values[g*(local+1)+local];std::vector<uint32_t>returned(values+g*(local+1),values+g*(local+1)+active),expected;
  if(add){unsigned step=control?2:1;if(final!=initialValue+active*step)bad++;for(unsigned i=0;i<active;i++)expected.push_back(initialValue+i*step);}
  else if(cas){bool matches=!variant;uint32_t replacement=p.operand^controlKey;if(final!=(matches?replacement:initialValue))bad++;expected.assign(active,matches?replacement:initialValue);if(matches)expected[0]=initialValue;}
  else{expected.push_back(initialValue);for(unsigned i=0;i<active;i++)expected.push_back((p.operand^i)^controlKey);returned.push_back(final);}
  std::sort(returned.begin(),returned.end());std::sort(expected.begin(),expected.end());if(returned!=expected)bad++;
  for(unsigned i=active;i<local;i++)if(values[g*(local+1)+i]!=0xa5a5a5a5u)guardBad++;
 }
 const unsigned char *b=(const unsigned char*)host.contents;for(size_t i=0;i<64;i++){if(b[i]!=0xa5)guardBad++;if(b[bytes-64+i]!=0xa5)guardBad++;}
 NSString *prefix=c[@"dump_prefix"];[[NSData dataWithBytes:host.contents length:bytes]writeToFile:[prefix stringByAppendingString:@".output.bin"]atomically:YES];
 NSDictionary *result=@{@"device":device.name,@"registry_id":@(device.registryID),@"kind":kind,@"mode":mode,@"pipeline_reused":@(reused),@"local":@(local),@"groups":@(groups),@"active":@(active),@"variant":@(variant),@"seed":@(p.seed),@"operand":@(p.operand),@"staging":c[@"staging"],@"shared_bytes":@(shared),@"static_threadgroup_bytes":@(pipeline.staticThreadgroupMemoryLength),@"reported_max_threadgroup_bytes":@(device.maxThreadgroupMemoryLength),@"pipeline_max_threads":@(pipeline.maxTotalThreadsPerThreadgroup),@"output_words":@(count),@"mismatches":@(bad),@"guard_mismatches":@(guardBad),@"command_status":@(command.status),@"import":proof?:@{}};*status=bad||guardBad?10:0;return result;
}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=2)return 1;NSArray *plan=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])]options:0 error:nil];if(![plan isKindOfClass:[NSArray class]]||!plan.count||plan.count>128)return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;unsigned completed=0;NSMutableDictionary *pipelines=[NSMutableDictionary dictionary];
 for(NSDictionary *c in plan){@autoreleasepool{int status=0;NSDictionary *result=runCase(device,pipelines,c,&status);NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(!json||![json writeToFile:[c[@"dump_prefix"]stringByAppendingString:@".json"]atomically:YES])return 11;emit(@{@"label":c[@"label"],@"exit_code":@(status),@"mismatches":result[@"mismatches"]?:@(-1),@"guards":result[@"guard_mismatches"]?:@(-1)});if(status)return status;completed++;}}
 emit(@{@"completed_cases":@(completed),@"device":device.name});return 0;
}}
