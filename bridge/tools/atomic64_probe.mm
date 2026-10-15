#import "KeplerProgramImport.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <vector>
struct Parameters{uint64_t addresses[4];uint32_t grid[3],block[3];};
static bool finish(id<MTLCommandBuffer>command){[command commit];[command waitUntilCompleted];return command.status==MTLCommandBufferStatusCompleted;}
static void emit(NSDictionary *result){NSData *j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=8&&argc!=9)return 1;
 unsigned count=(unsigned)strtoul(argv[4],nullptr,10),variant=(unsigned)strtoul(argv[5],nullptr,10),rounds=(unsigned)strtoul(argv[6],nullptr,10);
 bool noCopy=!strcmp(argv[7],"nocopy");if(!noCopy&&strcmp(argv[7],"managed"))return 1;
 if(!count||count>4096||variant>2||!rounds||rounds>4)return 1;
 NSDictionary *info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[3])] options:0 error:nil];NSString *kind=info[@"operation"]?:info[@"kind"];
 bool returnValues=!info[@"return_values"]||[info[@"return_values"]boolValue],invocationCounter=[info[@"invocation_counter"]boolValue];
 bool add=[kind isEqualToString:@"add"],cas=[kind isEqualToString:@"cas"],exchange=[kind isEqualToString:@"exchange"];
 if(!info||(!add&&!cas&&!exchange)||[info[@"sm"]unsignedIntValue]!=30||[info[@"scratch_bytes"]unsignedIntValue]||[info[@"crs_bytes"]unsignedIntValue]||(!add&&rounds!=1))return 1;
 uint64_t initial=0x2fffffff0ULL;
 if(add)initial=variant==0?0x2ffffff00ULL:0xffffffffffffff00ULL;
 else if(cas)initial=variant==0?0x2fffffff0ULL:(variant==1?0x5fffffff0ULL:0x2fffffff8ULL);
 else if(variant)initial=0xffffffffffffff00ULL;
 constexpr uint64_t step=0x100000003ULL,compare=0x2fffffff0ULL,replacement=0x12345678abcdef00ULL,exchangeBase=0x12340000fffffff0ULL,exchangeStep=0x100000009ULL;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSError *error=nil;NSDictionary *evidence=nil;id<MTLComputePipelineState>pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],@"add_buffers",[NSData dataWithContentsOfFile:@(argv[2])],{[info[@"registers"]unsignedIntValue],576,576},&error,&evidence);
 if(!pipeline){emit(@{@"pipeline_created":@NO,@"error":error.description?:@"No pipeline"});return 3;}
 const size_t guard=64,returnsBytes=count*8+guard*2;
 // Reserve enough space for the original carrier's float outputs too. A wrong
 // import would alter sentinels, rather than escaping our resource allocation.
 const size_t counterBytes=std::max<size_t>(count*4,8)+guard*2;
 std::vector<unsigned char>counterInitial(counterBytes,0xa5),returnsInitial(returnsBytes,0xa5);memcpy(counterInitial.data()+guard,&initial,8);
 id<MTLBuffer>counter=[device newBufferWithLength:counterBytes options:MTLResourceStorageModePrivate],returned=[device newBufferWithLength:returnsBytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>counterHost=KPCreateHostBuffer(device,counterInitial.data(),counterBytes,noCopy),returnsHost=KPCreateHostBuffer(device,returnsInitial.data(),returnsBytes,noCopy);
 uint32_t word=invocationCounter?0:count;id<MTLBuffer>n=[device newBufferWithBytes:&word length:4 options:MTLResourceStorageModeShared];
 if(!counter||!returned||!counterHost||!returnsHost||!n||!counter.gpuAddress||!returned.gpuAddress)return 4;
 Parameters p={{returned.gpuAddress+guard,n.gpuAddress,counter.gpuAddress+guard,n.gpuAddress},{count,1,1},{32,1,1}};
 id<MTLBuffer>params=[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];id<MTLCommandQueue>queue=[device newCommandQueue];if(!params||!queue)return 4;
 id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[upload blitCommandEncoder];[blit copyFromBuffer:counterHost sourceOffset:0 toBuffer:counter destinationOffset:0 size:counterBytes];[blit copyFromBuffer:returnsHost sourceOffset:0 toBuffer:returned destinationOffset:0 size:returnsBytes];[blit endEncoding];if(!finish(upload))return 5;
 id<MTLCommandBuffer>command=[queue commandBuffer];for(unsigned r=0;r<rounds;r++){
  id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];[encoder setBuffer:params offset:0 atIndex:0];[encoder setBuffer:counter offset:guard atIndex:1];
  [encoder useResource:counter usage:MTLResourceUsageRead|MTLResourceUsageWrite];[encoder useResource:returned usage:MTLResourceUsageRead|MTLResourceUsageWrite];[encoder useResource:n usage:MTLResourceUsageRead|MTLResourceUsageWrite];
  [encoder dispatchThreadgroups:MTLSizeMake((count+31)/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[encoder endEncoding];
 }if(!finish(command))return 6;
 id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];[blit copyFromBuffer:counter sourceOffset:0 toBuffer:counterHost destinationOffset:0 size:counterBytes];[blit copyFromBuffer:returned sourceOffset:0 toBuffer:returnsHost destinationOffset:0 size:returnsBytes];if(!noCopy){[blit synchronizeResource:counterHost];[blit synchronizeResource:returnsHost];}[blit endEncoding];if(!finish(read))return 7;
 const unsigned char *counterOut=(const unsigned char*)counterHost.contents,*returnsOut=(const unsigned char*)returnsHost.contents;uint64_t actual=0;memcpy(&actual,counterOut+guard,8);
 std::vector<uint64_t>values(count),expected;for(unsigned i=0;i<count;i++)memcpy(&values[i],returnsOut+guard+i*8,8);
 uint64_t expectedFinal=actual;unsigned mismatches=0;expected.reserve(count+1);
 if(add){expectedFinal=initial+uint64_t(count)*rounds*step;uint64_t base=initial+uint64_t(count)*(rounds-1)*step;for(unsigned i=0;i<count;i++)expected.push_back(base+uint64_t(i)*step);}
 else if(cas){bool matches=initial==compare;expectedFinal=matches?replacement:initial;expected.assign(count,matches?replacement:initial);if(matches)expected[0]=initial;}
 else{values.push_back(actual);expected.push_back(initial);for(unsigned i=0;i<count;i++)expected.push_back(exchangeBase+uint64_t(i)*exchangeStep);}
 if(returnValues){std::sort(values.begin(),values.end());std::sort(expected.begin(),expected.end());for(size_t i=0;i<expected.size();i++)if(values[i]!=expected[i])mismatches++;}
 else if(exchange){bool valid=false;for(unsigned i=0;i<count;i++)valid|=actual==exchangeBase+uint64_t(i)*exchangeStep;if(!valid)mismatches++;}
 if(actual!=expectedFinal)mismatches++;
 uint32_t dispatched=0;memcpy(&dispatched,n.contents,4);if(invocationCounter&&dispatched!=count*rounds)mismatches++;
 unsigned guardBad=0;for(size_t i=0;i<counterBytes;i++)if((i<guard||i>=guard+8)&&counterOut[i]!=0xa5)guardBad++;
 for(size_t i=0;i<returnsBytes;i++)if((!returnValues||i<guard||i>=guard+count*8)&&returnsOut[i]!=0xa5)guardBad++;
 if(argc==9){NSString *prefix=@(argv[8]);[[NSData dataWithBytes:counterOut length:counterBytes]writeToFile:[prefix stringByAppendingString:@".counter.bin"] atomically:YES];[[NSData dataWithBytes:returnsOut length:returnsBytes]writeToFile:[prefix stringByAppendingString:@".returned.bin"] atomically:YES];}
 NSString *oracle=add?@"CPU uint64 modulo sum and exact permutation of last-dispatch returned values":(cas?@"CPU full64 compare and one successful exchange or no success":@"CPU exchange chain multiset: all returned values plus final equals initial plus all writes");
 emit(@{@"device":device.name,@"registry_id":@(device.registryID),@"kind":info[@"kind"],@"count":@(count),@"variant":@(variant),@"rounds":@(rounds),@"initial":@(initial),@"final":@(actual),@"expected_final":@(expectedFinal),@"returned_values_checked":@(returnValues?values.size():0),@"invocations_counted":@(dispatched),@"invocation_counter_enabled":@(invocationCounter),@"mismatches":@(mismatches),@"guard_mismatches":@(guardBad),@"command_status":@(command.status),@"import":evidence,@"shader_info":info,@"staging":noCopy?@"nocopy":@"managed",@"private_resource_bytes":@(counterBytes+returnsBytes),@"oracle":returnValues?oracle:@"CPU counter state, exact invocation count, unchanged returned-value buffer",@"performance_benchmark":@NO});return mismatches||guardBad?10:0;
}}
