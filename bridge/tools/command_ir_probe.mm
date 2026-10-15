// Bounded execution of the public-MSL command producer lowered to portable IR.
// Records are data only: no generated QMD is submitted by this probe.
#import "KeplerProgramImport.h"
#include "KeplerCommandIR.h"
#include <algorithm>
#include <cstring>
#include <vector>

struct ImportABI {uint64_t root;uint32_t grid[3],block[3];};
struct RootArguments {uint64_t commands,pipeline,output,counter,parameters;};
static_assert(sizeof(ImportABI)==32&&sizeof(RootArguments)==40,"Producer ABI");
static void emit(NSDictionary *d){NSData*b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(b)fwrite(b.bytes,1,b.length,stdout);puts("");fflush(stdout);}
static NSDictionary *finish(id<MTLCommandBuffer>cb){[cb commit];[cb waitUntilCompleted];return @{@"status":@(cb.status),@"error":cb.error.description?:@""};}
static bool complete(NSDictionary*d){return [d[@"status"]unsignedIntValue]==MTLCommandBufferStatusCompleted;}

int main(int argc,char **argv){@autoreleasepool {
 if(argc!=4&&argc!=5)return 1;
 NSString*build=@(argv[1]),*directory=@(argv[2]),*mode=@(argv[3]);
 NSString*semantic=argc==5?@(argv[4]):@"basic";
 if(![@[@"basic",@"barrier",@"clear",@"threads",@"copy"]containsObject:semantic])return 1;
 bool carrier=[mode isEqual:@"carrier"],absent=[mode isEqual:@"no_producer"];
 if(!carrier&&!absent&&![mode isEqual:@"producer"])return 1;
 NSDictionary*info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[build stringByAppendingPathComponent:@"backend-enabled/info.json"]]options:0 error:nil];
 if([info[@"sm"]unsignedIntValue]!=30||[info[@"buffer_slots"]unsignedIntValue]!=1||[info[@"grid_offset"]unsignedIntValue]!=8||[info[@"push_bytes"]unsignedIntValue]!=32||[info[@"command_ir_version"]unsignedIntValue]!=1||[info[@"shared_bytes"]unsignedIntValue]||[info[@"scratch_bytes"]unsignedIntValue]||[info[@"crs_bytes"]unsignedIntValue]||![info[@"local_size"]isEqual:@[@32,@1,@1]])return 2;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name isEqual:@"NVIDIA GeForce GTX 880M"]){d=x;break;}if(!d)return 3;
 NSError*error=nil;NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=nil;
 NSURL*url=[NSURL fileURLWithPath:[build stringByAppendingPathComponent:@"command_ir_carrier.metallib"]];
 if(carrier){id<MTLLibrary>lib=[d newLibraryWithURL:url error:&error];id<MTLFunction>fn=[lib newFunctionWithName:@"command_ir_carrier"];pipeline=[d newComputePipelineStateWithFunction:fn error:&error];[fn release];[lib release];}
 else pipeline=KPCreatePipeline(d,url,@"command_ir_carrier",[NSData dataWithContentsOfFile:[build stringByAppendingPathComponent:@"backend-enabled/program.sass"]],{std::max(24u,[info[@"registers"]unsignedIntValue]),576,576},&error,&proof);
 if(!pipeline){emit(@{@"stage":@"pipeline",@"error":error.description?:@"nil",@"import":proof?:@{}});return 4;}
 if(pipeline.maxTotalThreadsPerThreadgroup<32||pipeline.staticThreadgroupMemoryLength>512){emit(@{@"stage":@"pipeline_limits",@"threads":@(pipeline.maxTotalThreadsPerThreadgroup),@"static_shared":@(pipeline.staticThreadgroupMemoryLength),@"import":proof?:@{}});return 5;}
 id<MTLCommandQueue>q=[[d newCommandQueue]autorelease];if(!q)return 6;
 NSArray*cases=@[@"capacity1",@"capacity2",@"capacity8",@"bad_context_magic",@"bad_version",@"capacity0",@"capacity9",@"bad_record_bytes",@"bad_pipeline_tag",@"bad_pipeline_index",@"pipeline_count9",@"binding_limit2"];
 NSMutableArray*runs=[NSMutableArray array];unsigned totalBad=0,totalGuards=0;
 for(NSUInteger test=0;test<cases.count;test++)for(unsigned trial=0;trial<3;trial++){@autoreleasepool {
  NSString*name=cases[test];size_t length=64+8*128+64;std::vector<uint8_t>initial(length,0xa5),wanted=initial;
  id<MTLBuffer>records=[[d newBufferWithLength:length options:MTLResourceStorageModePrivate]autorelease];
  id<MTLBuffer>upload=[[d newBufferWithBytes:initial.data()length:length options:MTLResourceStorageModeShared]autorelease];
  id<MTLBuffer>readback=[[d newBufferWithLength:length options:MTLResourceStorageModeManaged]autorelease];
  id<MTLBuffer>out=[[d newBufferWithLength:2048 options:MTLResourceStorageModePrivate]autorelease];
  id<MTLBuffer>counter=[[d newBufferWithLength:128 options:MTLResourceStorageModePrivate]autorelease];
  uint32_t parameter=0x1234u+trial;id<MTLBuffer>parameters=[[d newBufferWithBytes:&parameter length:4 options:MTLResourceStorageModeShared]autorelease];
  if(!records||!upload||!readback||!out||!counter||!parameters)return 7;
  KPCommandContext context={KP_COMMAND_CONTEXT_MAGIC,1,2,3,records.gpuAddress+64,128,3};
  if(test==0)context.capacity=1;else if(test==2)context.capacity=8;
  if(test==3)context.magic^=1;if(test==4)context.version=2;if(test==5)context.capacity=0;if(test==6)context.capacity=9;if(test==7)context.record_bytes=64;if(test==10)context.pipeline_count=9;if(test==11)context.max_bindings=2;
  uint64_t token=(uint64_t(KP_COMMAND_PIPELINE_MAGIC)<<32)|trial;
  if(test==8)token^=uint64_t(1)<<32;if(test==9)token=(uint64_t(KP_COMMAND_PIPELINE_MAGIC)<<32)|3;
  id<MTLBuffer>ctxUpload=[[d newBufferWithBytes:&context length:sizeof context options:MTLResourceStorageModeShared]autorelease];
  id<MTLBuffer>ctx=[[d newBufferWithLength:sizeof context options:MTLResourceStorageModePrivate]autorelease];
  RootArguments root={ctx.gpuAddress,token,out.gpuAddress+128,counter.gpuAddress+64,parameters.gpuAddress};
  id<MTLBuffer>rootUpload=[[d newBufferWithBytes:&root length:sizeof root options:MTLResourceStorageModeShared]autorelease];
  id<MTLBuffer>rootBuffer=[[d newBufferWithLength:sizeof root options:MTLResourceStorageModePrivate]autorelease];
  if(!ctxUpload||!ctx||!rootUpload||!rootBuffer)return 7;
  ImportABI abi={rootBuffer.gpuAddress,{32,1,1},{32,1,1}};
  id<MTLBuffer>push=[[d newBufferWithBytes:&abi length:sizeof abi options:MTLResourceStorageModeShared]autorelease];if(!push)return 7;
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];
  [b copyFromBuffer:upload sourceOffset:0 toBuffer:records destinationOffset:0 size:length];
  [b copyFromBuffer:ctxUpload sourceOffset:0 toBuffer:ctx destinationOffset:0 size:sizeof context];
  [b copyFromBuffer:rootUpload sourceOffset:0 toBuffer:rootBuffer destinationOffset:0 size:sizeof root];[b endEncoding];
  if(!absent){id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:pipeline];[e setBuffer:push offset:0 atIndex:0];[e setBuffer:records offset:64 atIndex:1];
   for(id<MTLBuffer>r in @[rootBuffer,ctx,out,counter,parameters])[e useResource:r usage:MTLResourceUsageRead];
   [e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];}
  b=[cb blitCommandEncoder];[b copyFromBuffer:records sourceOffset:0 toBuffer:readback destinationOffset:0 size:length];[b synchronizeResource:readback];[b endEncoding];
  NSDictionary*state=finish(cb);if(!complete(state)){emit(@{@"stage":@"execute",@"case":name,@"trial":@(trial),@"command":state});return 8;}
  bool valid=context.magic==KP_COMMAND_CONTEXT_MAGIC&&context.version==1&&context.capacity<=8&&context.record_bytes==128;
  if(carrier){for(unsigned i=0;i<32;i++){uint32_t row[4]={32u^0x7a11beefu,0,0xdeadbeef,i};memcpy(wanted.data()+64+i*16,row,16);}}
  else if(!absent&&valid)for(unsigned i=0;i<context.capacity;i++){
   KPCommandRecord record={};record.magic=KP_COMMAND_RECORD_MAGIC;record.flags=KP_COMMAND_FLAG_DISPATCH|KP_COMMAND_FLAG_SHARED;
   if(uint32_t(token>>32)==KP_COMMAND_PIPELINE_MAGIC&&uint32_t(token)<context.pipeline_count&&context.pipeline_count<=8){record.pipeline_token=token;record.flags|=KP_COMMAND_FLAG_PIPELINE;}else{record.error=1;record.flags|=KP_COMMAND_FLAG_ERROR;}
   for(unsigned slot=0;slot<3;slot++)if(slot<context.max_bindings){record.buffers[slot]=slot==0?root.output:slot==1?root.counter:root.parameters;record.flags|=KP_COMMAND_FLAG_BUFFER0<<slot;}else{record.error=2;record.flags|=KP_COMMAND_FLAG_ERROR;}
   record.groups[0]=record.groups[1]=record.groups[2]=1;record.local[0]=32;record.local[1]=record.local[2]=1;record.shared_bytes=48640;
   if(![semantic isEqual:@"basic"]){record.flags|=KP_COMMAND_FLAG_STAGE_IN;uint32_t origin[3]={3,2,1},size[3]={17,4,2};memcpy(record.stage_origin,origin,12);memcpy(record.stage_size,size,12);if(![semantic isEqual:@"clear"])record.flags|=KP_COMMAND_FLAG_BARRIER;}
   if([semantic isEqual:@"threads"]){record.dispatch_kind=1;record.groups[0]=97;record.groups[1]=2;}
   if([semantic isEqual:@"copy"]){if(i==0){KPCommandRecord empty={};empty.magic=KP_COMMAND_RECORD_MAGIC;memcpy(wanted.data()+64,&empty,128);}else if(i==1)memcpy(wanted.data()+64+128,&record,128);}
   else memcpy(wanted.data()+64+i*128,&record,128);
  }
  const uint8_t*raw=(const uint8_t*)readback.contents;unsigned bad=0,guards=0;for(size_t i=0;i<length;i++){if(i<64||i>=length-64)guards+=raw[i]!=0xa5;else bad+=raw[i]!=wanted[i];}
  NSString*filename=[NSString stringWithFormat:@"%@-%u.bin",name,trial];if(![[NSData dataWithBytes:raw length:length]writeToFile:[directory stringByAppendingPathComponent:filename]atomically:YES])return 9;
  [runs addObject:@{@"case":name,@"case_index":@(test),@"trial":@(trial),@"capacity":@(context.capacity),@"context_magic":@(context.magic),@"context_version":@(context.version),@"record_bytes":@(context.record_bytes),@"max_bindings":@(context.max_bindings),@"pipeline_count":@(context.pipeline_count),@"pipeline_token":@(token),@"resource_addresses":@[@(root.output),@(root.counter),@(root.parameters)],@"output_file":filename,@"command":state,@"mismatch_bytes":@(bad),@"guard_mismatch_bytes":@(guards)}];totalBad+=bad;totalGuards+=guards;
  if(bad||guards)break;
 }}
 emit(@{@"mode":mode,@"semantic":semantic,@"device":d.name,@"registry_id":@(d.registryID),@"import":proof?:@{},@"compiled_info":info,@"pipeline_static_shared_bytes":@(pipeline.staticThreadgroupMemoryLength),@"record_writes_GPU":@(!carrier&&!absent),@"records_CPU_uploaded":@NO,@"GPU_command_execution":@NO,@"gpu_dispatch":@(!absent),@"runs":runs,@"mismatch_bytes":@(totalBad),@"guard_mismatch_bytes":@(totalGuards),@"passed":@(!totalBad&&!totalGuards),@"performance_benchmark":@NO,@"scope":@"public MSL command intrinsics compiled by experimental frontend; GPU writes portable IR records only; no installed compiler/driver patch"});[pipeline release];return totalBad||totalGuards?10:0;
}}
