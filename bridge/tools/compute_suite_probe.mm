#import "KeplerProgramImport.h"
#import <Accelerate/Accelerate.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <sys/resource.h>
#include <vector>
using Clock=std::chrono::steady_clock;
static double ms(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
static double cpuMS(){rusage r={};getrusage(RUSAGE_SELF,&r);return r.ru_utime.tv_sec*1000.+r.ru_utime.tv_usec*.001+r.ru_stime.tv_sec*1000.+r.ru_stime.tv_usec*.001;}
struct Parameters {uint64_t addresses[4];uint32_t grid[3],block[3];};
static uint32_t hash32(uint32_t bits){bits^=bits>>16;bits*=0x7feb352du;bits^=bits>>15;bits*=0x846ca68bu;return bits^(bits>>16);}
static bool finish(id<MTLCommandBuffer>command){[command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"%s\n",command.error.description.UTF8String);return false;}return true;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc<5||argc>8){fprintf(stderr,"usage: compute_suite_probe CARRIER.metallib CODE.sass INFO.json COUNT [managed|nocopy [resident|roundtrip [BATCH]]]\n");return 1;}
 bool noCopy=argc>=6&&!strcmp(argv[5],"nocopy"),roundtrip=argc>=7&&!strcmp(argv[6],"roundtrip");
 if(argc>=6&&!noCopy&&strcmp(argv[5],"managed"))return 2;
 if(argc>=7&&!roundtrip&&strcmp(argv[6],"resident"))return 2;
 unsigned batch=argc==8?(unsigned)strtoul(argv[7],NULL,10):1;if(!batch||batch>12)return 2;
 NSDictionary*info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[3])] options:0 error:nil];
 if(!info||[info[@"sm"] unsignedIntValue]!=30||[info[@"scratch_bytes"] unsignedIntValue]||[info[@"crs_bytes"] unsignedIntValue])return 2;
 NSString*kind=info[@"kind"];bool fp64=[kind isEqualToString:@"fp64"],atomic=[kind isEqualToString:@"atomic32"],shared=[kind isEqualToString:@"shared_reduce"],shuffle=[kind isEqualToString:@"shuffle"],counted=[kind isEqualToString:@"tiled_counted"],tiled=[kind isEqualToString:@"tiled_matmul"]||counted,matrix=[kind isEqualToString:@"matmul"]||tiled;
 if(batch>1&&(!counted||roundtrip))return 2;
 if(!fp64&&!atomic&&!shared&&!shuffle&&!matrix)return 2;
 uint32_t count=(uint32_t)strtoul(argv[4],NULL,10);if(!count||count>1048576||(shuffle&&count%32))return 2;
 unsigned dimension=[info[@"matrix_size"] unsignedIntValue],local=[info[@"local_size"][0] unsignedIntValue];
 if((matrix&&(dimension<(tiled?16:8)||dimension>1024||count!=dimension*dimension))||(local!=(tiled?256:(shared?128:32))))return 2;
 unsigned total=(count+78)&~31u,active=atomic?1:count;size_t elementBytes=fp64?8:4,bytes=total*elementBytes;
 std::vector<unsigned char>inputA(bytes),inputB(bytes),initial(bytes),download(bytes);
 constexpr uint32_t guard32=0xdeadbeef;constexpr uint64_t guard64=0x7ff4deadbeef1234ULL;
 for(unsigned i=0;i<total;i++){
  if(fp64){double a=1.0+std::ldexp(double(i%17+1),-42),b=-1.0+std::ldexp(double(i%11+1),-44);memcpy(inputA.data()+i*8,&a,8);memcpy(inputB.data()+i*8,&b,8);memcpy(initial.data()+i*8,&guard64,8);}
  else {float a=float(int(hash32(i+0x85ebca6bu)&63)-32)/64.f,b=float(int(hash32(i+0xc2b2ae35u)&63)-32)/64.f;memcpy(inputA.data()+i*4,&a,4);memcpy(inputB.data()+i*4,&b,4);memcpy(initial.data()+i*4,&guard32,4);}
 }
 if(atomic){uint32_t zero=0;memcpy(initial.data(),&zero,4);}
 std::vector<float>matrixReference(matrix?count:0),blasOutput(matrix?count:0);
 if(matrix){
  for(unsigned row=0;row<dimension;row++)for(unsigned col=0;col<dimension;col++){
   double sum=0;for(unsigned k=0;k<dimension;k++)sum+=double(((float*)inputA.data())[row*dimension+k])*double(((float*)inputB.data())[k*dimension+col]);
   matrixReference[row*dimension+col]=float(sum);
  }
 }
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 3;
 NSError*error=nil;NSDictionary*importEvidence=nil;KeplerImportConfig config={[info[@"registers"] unsignedIntValue],576,576};
 id<MTLComputePipelineState>pipeline=nil;
 @autoreleasepool {pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],@"add_buffers",[NSData dataWithContentsOfFile:@(argv[2])],config,&error,&importEvidence);[error retain];[importEvidence retain];}
 if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 4;}
 if([info[@"shared_bytes"] unsignedIntValue]>pipeline.staticThreadgroupMemoryLength){fprintf(stderr,"Insufficient carrier threadgroup memory: %lu\n",pipeline.staticThreadgroupMemoryLength);return 4;}
 id<MTLBuffer>a=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate],b=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate],out=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>sa=KPCreateHostBuffer(device,inputA.data(),bytes,noCopy),sb=KPCreateHostBuffer(device,inputB.data(),bytes,noCopy),so=KPCreateHostBuffer(device,initial.data(),bytes,noCopy);
 uint32_t countWord=counted?0:count;
 id<MTLBuffer>n=[device newBufferWithBytes:&countWord length:4 options:MTLResourceStorageModeShared];
 if(!a||!b||!out||!sa||!sb||!so||!n||!a.gpuAddress||!b.gpuAddress||!out.gpuAddress||!n.gpuAddress)return 5;
 if(!noCopy){[sa didModifyRange:NSMakeRange(0,bytes)];[sb didModifyRange:NSMakeRange(0,bytes)];[so didModifyRange:NSMakeRange(0,bytes)];}
 Parameters p={{a.gpuAddress,b.gpuAddress,out.gpuAddress,n.gpuAddress},{count,dimension,dimension},{local,1,1}};
 id<MTLBuffer>params=[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];id<MTLCommandQueue>queue=[device newCommandQueue];if(!params||!queue)return 5;
 Clock::time_point start=Clock::now();id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[upload blitCommandEncoder];
 [blit copyFromBuffer:sa sourceOffset:0 toBuffer:a destinationOffset:0 size:bytes];[blit copyFromBuffer:sb sourceOffset:0 toBuffer:b destinationOffset:0 size:bytes];[blit copyFromBuffer:so sourceOffset:0 toBuffer:out destinationOffset:0 size:bytes];[blit endEncoding];if(!finish(upload))return 6;double uploadMS=ms(start);
 NSMutableArray*samples=[NSMutableArray array];const unsigned warmups=matrix?3:1,trials=matrix?9:3;
 for(unsigned trial=0;trial<warmups+trials;trial++){@autoreleasepool{
  double repeatedUpload=0,repeatedRead=0,transferCPU=0;
  double cpuWall=0,cpuConsumed=0;
  if(matrix){start=Clock::now();cpuConsumed=cpuMS();
   for(unsigned repeat=0;repeat<batch;repeat++)cblas_sgemm(CblasRowMajor,CblasNoTrans,CblasNoTrans,(int)dimension,(int)dimension,(int)dimension,1.f,(const float*)inputA.data(),(int)dimension,(const float*)inputB.data(),(int)dimension,0.f,blasOutput.data(),(int)dimension);
   cpuConsumed=(cpuMS()-cpuConsumed)/batch;cpuWall=ms(start)/batch;
  }
  if(roundtrip){start=Clock::now();double transferStart=cpuMS();memcpy(sa.contents,inputA.data(),bytes);memcpy(sb.contents,inputB.data(),bytes);memcpy(so.contents,initial.data(),bytes);
   if(!noCopy){[sa didModifyRange:NSMakeRange(0,bytes)];[sb didModifyRange:NSMakeRange(0,bytes)];[so didModifyRange:NSMakeRange(0,bytes)];}
   id<MTLCommandBuffer>transfer=[queue commandBuffer];id<MTLBlitCommandEncoder>copy=[transfer blitCommandEncoder];
   [copy copyFromBuffer:sa sourceOffset:0 toBuffer:a destinationOffset:0 size:bytes];[copy copyFromBuffer:sb sourceOffset:0 toBuffer:b destinationOffset:0 size:bytes];[copy copyFromBuffer:so sourceOffset:0 toBuffer:out destinationOffset:0 size:bytes];[copy endEncoding];if(!finish(transfer))return 6;transferCPU+=cpuMS()-transferStart;repeatedUpload=ms(start);
  }
  start=Clock::now();double hostCPU=cpuMS();id<MTLCommandBuffer>command=[queue commandBuffer];
  for(unsigned repeat=0;repeat<batch;repeat++){id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];
   [encoder setComputePipelineState:pipeline];[encoder setBuffer:params offset:0 atIndex:0];[encoder setBuffer:out offset:0 atIndex:1];
   [encoder useResource:a usage:MTLResourceUsageRead];[encoder useResource:b usage:MTLResourceUsageRead];[encoder useResource:n usage:counted?(MTLResourceUsageRead|MTLResourceUsageWrite):MTLResourceUsageRead];[encoder useResource:out usage:MTLResourceUsageRead|MTLResourceUsageWrite];
   [encoder dispatchThreadgroups:MTLSizeMake(tiled?count/256:(shared?count:((count+31)/32)),1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[encoder endEncoding];
  }if(!finish(command))return 7;hostCPU=(cpuMS()-hostCPU)/batch;double wall=ms(start)/batch;
  if(roundtrip){start=Clock::now();double transferStart=cpuMS();id<MTLCommandBuffer>transfer=[queue commandBuffer];id<MTLBlitCommandEncoder>copy=[transfer blitCommandEncoder];
   [copy copyFromBuffer:out sourceOffset:0 toBuffer:so destinationOffset:0 size:bytes];if(!noCopy)[copy synchronizeResource:so];[copy endEncoding];if(!finish(transfer))return 8;
   memcpy(download.data(),so.contents,bytes);transferCPU+=cpuMS()-transferStart;repeatedRead=ms(start);
   if(matrix){for(unsigned i=0;i<count;i++){float value;memcpy(&value,download.data()+i*4,4);if(value!=matrixReference[i]){fprintf(stderr,"Per-trial matrix validation failed at %u\n",i);return 10;}}}
   for(unsigned i=active;i<total;i++)if(memcmp(download.data()+i*elementBytes,initial.data()+i*elementBytes,elementBytes)){fprintf(stderr,"Per-trial guard validation failed at %u\n",i);return 10;}
  }
  if(trial>=warmups)[samples addObject:@{@"trial":@(trial-warmups),@"gpu_command_ms":@((command.GPUEndTime-command.GPUStartTime)*1000/batch),@"compute_submit_wait_wall_ms":@(wall),@"host_cpu_ms":@(hostCPU),@"cpu_blas_wall_ms":@(cpuWall),@"cpu_blas_consumed_ms":@(cpuConsumed),@"upload_wall_ms":@(repeatedUpload),@"readback_wall_ms":@(repeatedRead),@"wall_with_copies_ms":@(repeatedUpload+wall+repeatedRead),@"host_cpu_with_copies_ms":@(hostCPU+transferCPU)}];
 }}
 start=Clock::now();id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];[blit copyFromBuffer:out sourceOffset:0 toBuffer:so destinationOffset:0 size:bytes];if(!noCopy)[blit synchronizeResource:so];[blit endEncoding];if(!finish(read))return 8;memcpy(download.data(),so.contents,bytes);double readMS=ms(start);
 unsigned bad=0,badGuard=0,blasBad=0;double maxError=0;
 for(unsigned i=0;i<active;i++){
  if(fp64){double va,vb,actual;memcpy(&va,inputA.data()+i*8,8);memcpy(&vb,inputB.data()+i*8,8);memcpy(&actual,download.data()+i*8,8);double expected=va+vb;if(actual!=expected)bad++;if(std::isfinite(actual))maxError=std::max(maxError,std::abs(actual-expected));else maxError=INFINITY;}
  else if(matrix){float actual;memcpy(&actual,download.data()+i*4,4);double error=std::abs(double(actual)-matrixReference[i]);maxError=std::max(maxError,error);if(!std::isfinite(actual)||error>1e-6+2e-5*std::abs(matrixReference[i]))bad++;if(blasOutput[i]!=matrixReference[i])blasBad++;}
  else {uint32_t actual;memcpy(&actual,download.data()+i*4,4);uint32_t expected=atomic?count*(roundtrip?1:(warmups+trials)):(shuffle?((i%32)^16)+1:0);if(shared){float value;memcpy(&value,&actual,4);if(value!=8384.f)bad++;}else if(actual!=expected)bad++;}
 }
 for(unsigned i=active;i<total;i++)if(memcmp(download.data()+i*elementBytes,initial.data()+i*elementBytes,elementBytes))badGuard++;
 uint32_t dispatchCounter=0;memcpy(&dispatchCounter,n.contents,4);bool dispatchesVerified=!counted||dispatchCounter==batch*(warmups+trials);
 NSDictionary*result=@{@"device":device.name,@"registry_id":@(device.registryID),@"kind":kind,@"shader_info":info,@"import":importEvidence,@"elements":@(count),@"output_elements":@(active),@"guards":@(total-active),@"warmups":@(warmups),@"measured_trials":@(samples.count),@"samples":samples,@"mismatches":@(bad),@"changed_guards":@(badGuard),@"max_absolute_error":@(maxError),@"blas_reference_mismatches":@(blasBad),@"batch":@(batch),@"dispatch_counter":@(dispatchCounter),@"dispatch_count_verified":@(dispatchesVerified),
  @"initial_upload_wall_ms":@(uploadMS),@"final_readback_wall_ms":@(readMS),@"requested_private_bytes":@(3*bytes),@"carrier_static_threadgroup_bytes":@(pipeline.staticThreadgroupMemoryLength),
  @"expected_atomic_total":@(atomic?count*(roundtrip?1:(warmups+trials)):0),@"expected_shared_sum":@(shared?8384:0),@"staging":noCopy?@"NoCopy Shared host pages":@"Managed",@"policy":roundtrip?@"roundtrip":@"resident",
  @"fp64_note":@"double values differ from 1/-1 below float32 precision; direct NIR/SM30, not a claim of MSL double support",
  @"input_pattern":@"matrix uses independently hashed dyadic float32 values (-32..31)/64, non-periodic short patterns; products and accumulation exactly representable through N=1024",
  @"timing_note":@"Private buffers; upload and readback separated; matrix CPU uses Accelerate SGEMM; correctness also compared to scalar double accumulation; process CPU measured with getrusage"};
 NSMutableDictionary*serializable=[result mutableCopy];if(!std::isfinite(maxError))serializable[@"max_absolute_error"]=[NSNull null];
 NSData*json=[NSJSONSerialization dataWithJSONObject:serializable options:NSJSONWritingPrettyPrinted error:nil];if(json)fwrite(json.bytes,1,json.length,stdout);putchar('\n');return bad||badGuard||blasBad||!dispatchesVerified?10:0;
}}
