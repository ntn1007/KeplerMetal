#import "KeplerCPUICB.h"
#if !KP_GRID_NATIVE
#import "KeplerProgramImport.h"
#endif
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
struct Push{uint64_t root;uint32_t grid[3],local[3];};
static NSString*hash(NSData*d){unsigned char b[32];CC_SHA256(d.bytes,(CC_LONG)d.length,b);NSMutableString*s=[NSMutableString new];for(unsigned char v:b)[s appendFormat:@"%02x",v];return s;}
static void emit(id d){NSData*b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");}
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static id<MTLLibrary>load(id<MTLDevice>d,NSString*p,NSError**e){return[d newLibraryWithURL:[NSURL fileURLWithPath:p]error:e];}
static NSArray*shape(MTLSize s){return @[@(s.width),@(s.height),@(s.depth)];}
static NSUInteger volume(MTLSize s){return s.width*s.height*s.depth;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);BOOL copy=[mode isEqual:@"copy"],split=[mode isEqual:@"split"],producer=![mode isEqual:@"no_producer"],bad=[mode hasPrefix:@"bad_"];
 NSString*semantic=([mode isEqual:@"no_producer"]||split||bad)?@"basic":mode;if([mode isEqual:@"bad_threads"])semantic=@"threads";
 if(![@[@"basic",@"threads",@"barrier",@"copy",@"reset"]containsObject:semantic])return 1;
 NSUInteger rows=copy?2:1,candidates=6,slots=candidates+rows,nodeCount=slots+3,bytes=8192*16+512;
 id<MTLDevice>d=nil;
#if KP_GRID_NATIVE
 d=MTLCreateSystemDefaultDevice();if(![d.name isEqual:@"Apple M1 Max"]||bad)return 2;
#else
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
#endif
 if(!d)return 2;id<MTLCommandQueue>q=[d newCommandQueue];Class original=object_getClass(d);NSError*error=nil;KPCPUICBScope*scope=nil;
 NSData*libraryData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.metallib"]],*manifestData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"consumer.json"]];id<MTLComputePipelineState>consumer=nil,writer=nil,fieldPSO=nil;NSDictionary*importProof=@{},*info=@{};id<MTLFunction>producerFunction=nil;
#if KP_GRID_NATIVE
 id<MTLLibrary>library=load(d,[assets stringByAppendingPathComponent:@"consumer.metallib"],&error);MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];pd.computeFunction=[library newFunctionWithName:@"grid_coordinates"];pd.supportIndirectCommandBuffers=YES;consumer=[d newComputePipelineStateWithDescriptor:pd options:MTLPipelineOptionNone reflection:nil error:&error];
 id<MTLLibrary>pl=load(d,[assets stringByAppendingPathComponent:@"producer.metallib"],&error);producerFunction=[pl newFunctionWithName:[@"encode_grid_" stringByAppendingString:semantic]];writer=[d newComputePipelineStateWithFunction:producerFunction error:&error];
#else
 if(![hash(libraryData)isEqual:@"5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0"])return 3;
 scope=[KPCPUICBScope installOnDevice:d queue:q libraryData:libraryData expectedSHA256:hash(libraryData)manifestData:manifestData expectedManifestSHA256:hash(manifestData)error:&error];if(!scope){emit(@{@"failure":@"registration",@"error":error.description?:@"nil"});return 3;}consumer=[scope pipelineForFunction:@"grid_coordinates"];
 for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:a[0]]];BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[scope enableGPUCommandSelectionWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 1:ok=[scope enableGPUCommandGeometryWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 2:ok=[scope enableGPUCommandBindingsWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 3:ok=[scope enableGPUCommandIRv2WithLibraryData:b expectedSHA256:hash(b)error:&error];}if(!ok){emit(@{@"failure":@"enable",@"asset":a[0],@"error":error.description?:@"nil"});return 3;}}
 info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".json"]]]options:0 error:nil];if([info[@"command_ir_version"]unsignedIntValue]!=2||[info[@"buffer_slots"]unsignedIntValue]!=1||[info[@"grid_offset"]unsignedIntValue]!=8||[info[@"push_bytes"]unsignedIntValue]!=32||[info[@"scratch_bytes"]unsignedIntValue]||[info[@"crs_bytes"]unsignedIntValue])return 3;
 writer=KPCreatePipeline(d,[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"carrier.metallib"]],@"command_ir_carrier",[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".sass"]]],{[info[@"registers"]unsignedIntValue],576,576},&error,&importProof);
 id<MTLLibrary>f=load(d,[assets stringByAppendingPathComponent:@"field.metallib"],&error);fieldPSO=[d newComputePipelineStateWithFunction:[f newFunctionWithName:@"mutate_command_ir_data"]error:&error];
#endif
 if(!consumer||!writer){emit(@{@"failure":@"pipeline",@"error":error.description?:@"nil"});return 3;}
 MTLSize maxGroups[6]={MTLSizeMake(7,4,1),MTLSizeMake(4,6,4),MTLSizeMake(3,4,2),MTLSizeMake(2,1,2),MTLSizeMake(2,3,1),MTLSizeMake(3,5,2)};
 MTLSize locals[6]={MTLSizeMake(8,4,1),MTLSizeMake(4,2,2),MTLSizeMake(5,3,2),MTLSizeMake(1,1,64),MTLSizeMake(32,32,1),MTLSizeMake(8,4,2)};
 NSMutableArray*runs=[NSMutableArray new];
 for(unsigned trial=0;trial<6;trial++){@autoreleasepool{
  unsigned candidate=trial,resource=(trial+1)%3;NSMutableArray*nodes=[NSMutableArray new],*specs=[NSMutableArray new];
  for(unsigned k=0;k<nodeCount;k++){
   unsigned specIndex=k<candidates?k:candidate;MTLSize g=maxGroups[specIndex],l=locals[specIndex];uint32_t seed=0x71931+trial*97+k*101;NSMutableDictionary*n=[NSMutableDictionary new];
   for(NSString*key in @[@"coordinates",@"geometry",@"counter"]){NSUInteger length=[key isEqual:@"counter"]?256:bytes;id<MTLBuffer>gpu=[d newBufferWithLength:length options:MTLResourceStorageModePrivate],h=[d newBufferWithLength:length options:MTLResourceStorageModeShared];if(!gpu||!h)return 4;n[key]=gpu;n[[key stringByAppendingString:@"Host"]]=h;memset(h.contents,0xa5,length);NSUInteger off=k<slots?128:128+([key isEqual:@"counter"]?4:32)*(k-slots);if([key isEqual:@"counter"]){uint32_t zero=0;memcpy((char*)h.contents+off,&zero,4);}}
   id<MTLBuffer>p=[d newBufferWithLength:1536 options:MTLResourceStorageModeShared];if(!p)return 4;memset(p.contents,0xa5,p.length);uint32_t words[10]={(uint32_t)(volume(g)*volume(l)),seed,0,0,(uint32_t)g.width,(uint32_t)g.height,(uint32_t)g.depth,(uint32_t)l.width,(uint32_t)l.height,(uint32_t)l.depth};memcpy((char*)p.contents+256,words,sizeof words);n[@"parameters"]=p;[nodes addObject:n];[specs addObject:@{@"groups":shape(g),@"local":shape(l),@"seed":@(seed),@"max_count":@(words[0])}];
  }
  id<MTLBuffer>records=[d newBufferWithLength:1216 options:MTLResourceStorageModePrivate],recordHost=[d newBufferWithLength:1216 options:MTLResourceStorageModeShared];if(!records||!recordHost)return 4;memset(recordHost.contents,0xa5,1216);
  id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];for(NSDictionary*n in nodes)for(NSString*key in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=n[[key stringByAppendingString:@"Host"]];[b copyFromBuffer:h sourceOffset:0 toBuffer:n[key]destinationOffset:0 size:h.length];}[b copyFromBuffer:recordHost sourceOffset:0 toBuffer:records destinationOffset:0 size:1216];[b endEncoding];if(!done(init))return 5;
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=4;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;id<MTLIndirectCommandBuffer>icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:slots options:MTLResourceStorageModeShared];if(!icb)return 6;
  for(unsigned k=0;k<slots;k++){id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:k];[c setComputePipelineState:consumer];for(unsigned i=0;i<4;i++)[c setKernelBuffer:nodes[k][@[@"coordinates",@"geometry",@"counter",@"parameters"][i]]offset:i==3?256:128 atIndex:i];[c concurrentDispatchThreadgroups:maxGroups[k<candidates?k:candidate]threadsPerThreadgroup:locals[k<candidates?k:candidate]];}
  NSDictionary*selected=nodes[slots+resource];NSUInteger outputOffset=128+32*resource,counterOffset=128+4*resource;KPGPUCommandSelection*plan=nil;id<MTLBuffer>root=nil,witness=nil,witnessHost=nil;id<MTLIndirectCommandBuffer>target=icb;NSUInteger executeIndex=candidates;
#if KP_GRID_NATIVE
  target=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:rows options:MTLResourceStorageModeShared];[target resetWithRange:NSMakeRange(0,rows)];executeIndex=0;id<MTLArgumentEncoder>ae=[producerFunction newArgumentEncoderWithBufferIndex:0];root=[d newBufferWithLength:ae.encodedLength options:MTLResourceStorageModeShared];[ae setArgumentBuffer:root offset:0];[ae setIndirectCommandBuffer:target atIndex:0];[ae setComputePipelineState:consumer atIndex:1];[ae setBuffer:selected[@"coordinates"]offset:outputOffset atIndex:2];[ae setBuffer:selected[@"geometry"]offset:outputOffset atIndex:3];[ae setBuffer:selected[@"counter"]offset:counterOffset atIndex:4];[ae setBuffer:nodes[candidate][@"parameters"]offset:256 atIndex:5];
#else
  if(![scope prepareResidentComputeCommands:icb range:NSMakeRange(0,slots)error:&error]){emit(@{@"failure":@"prepare",@"error":error.description?:@"nil"});return 7;}
  NSMutableArray*entries=[NSMutableArray new];for(unsigned k=0;k<3;k++){NSDictionary*n=nodes[slots+k];[entries addObject:@{@"bindings":@[@{@"buffer":n[@"coordinates"],@"offset":@(128+32*k)},@{@"buffer":n[@"geometry"],@"offset":@(128+32*k)},@{@"buffer":n[@"counter"],@"offset":@(128+4*k)}]}];}
  plan=[scope newGPUCommandIRv2FromBuffer:icb sourceRange:NSMakeRange(0,candidates)destination:icb destinationRange:NSMakeRange(candidates,rows)resources:entries records:records recordOffset:128 error:&error];if(!plan){emit(@{@"failure":@"plan",@"error":error.description?:@"nil"});return 8;}
  root=[plan newCommandIRArgumentsForCandidateIndex:candidate resourceIndex:resource error:&error];witness=plan.generatedGeometry;witnessHost=[d newBufferWithLength:witness.length options:MTLResourceStorageModeShared];if(!root||!witnessHost)return 8;
#endif
  id<MTLCommandBuffer>main=[q commandBuffer],pbuf=split?[q commandBuffer]:main;
  if(producer){id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:writer];
#if KP_GRID_NATIVE
   [e setBuffer:root offset:0 atIndex:0];[e useResource:target usage:MTLResourceUsageRead|MTLResourceUsageWrite];for(NSDictionary*n in nodes)for(NSString*key in @[@"coordinates",@"geometry",@"counter",@"parameters"])[e useResource:n[key]usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(rows,1,1)];
#else
   Push p={root.gpuAddress,{32,1,1},{32,1,1}};id<MTLBuffer>push=[d newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];[e setBuffer:push offset:0 atIndex:0];[e setBuffer:records offset:128 atIndex:1];[e useResource:root usage:MTLResourceUsageRead];for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];NSArray*keep=@[push,root,writer,plan.commandIRProducerResources];[pbuf addCompletedHandler:^(id<MTLCommandBuffer>c){(void)keep.count;}];
#endif
   [e endEncoding];}
#if !KP_GRID_NATIVE
  if(bad){NSDictionary*changes=@{@"bad_flags":@[@1,@0x1f3],@"bad_pipeline":@[@2,@8],@"bad_address0":@[@12,@1],@"bad_address1":@[@14,@1],@"bad_address2":@[@16,@1],@"bad_parameters":@[@26,@1],@"bad_groups_x":@[@4,@0],@"bad_groups_y":@[@5,@65536],@"bad_groups_z":@[@6,@65536],@"bad_local_z":@[@10,@0],@"bad_kind":@[@7,@9],@"bad_stage":@[@20,@1],@"bad_reserved":@[@28,@1],@"bad_shared":@[@18,@16],@"bad_threads":@[@4,@1]};NSArray*c=changes[mode];if(!c)return 9;uint32_t v[2]={[c[0]unsignedIntValue],[c[1]unsignedIntValue]};if([mode isEqual:@"bad_threads"]){MTLSize l=locals[candidate];v[0]=l.width>1?4:l.height>1?5:6;}
   id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];[e setComputePipelineState:fieldPSO];[e setBuffer:records offset:128 atIndex:0];[e setBytes:v length:8 atIndex:1];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];[e endEncoding];}
#endif
  if(split)[pbuf commit];
#if !KP_GRID_NATIVE
  if(![plan encodeCommandIRInCommandBuffer:main afterProducer:producer?pbuf:nil error:&error]){emit(@{@"failure":@"materialize",@"error":error.description?:@"nil"});return 10;}
#endif
  id<MTLComputeCommandEncoder>consumerEncoder=[main computeCommandEncoder];
#if !KP_GRID_NATIVE
  if(![scope adaptComputeEncoder:consumerEncoder error:&error])return 11;
#endif
  for(NSDictionary*n in nodes)for(NSString*key in @[@"coordinates",@"geometry",@"counter",@"parameters"])[consumerEncoder useResource:n[key]usage:MTLResourceUsageRead|MTLResourceUsageWrite];
  @try{[consumerEncoder executeCommandsInBuffer:target withRange:NSMakeRange(executeIndex,rows)];}@catch(NSException*x){[consumerEncoder endEncoding];emit(@{@"failure":@"execute",@"trial":@(trial),@"error":x.reason?:@"nil"});return 11;}[consumerEncoder endEncoding];
  b=[main blitCommandEncoder];for(NSDictionary*n in nodes)for(NSString*key in @[@"coordinates",@"geometry",@"counter"]){id<MTLBuffer>h=n[[key stringByAppendingString:@"Host"]];[b copyFromBuffer:n[key]sourceOffset:0 toBuffer:h destinationOffset:0 size:h.length];}[b copyFromBuffer:records sourceOffset:0 toBuffer:recordHost destinationOffset:0 size:1216];if(witness)[b copyFromBuffer:witness sourceOffset:0 toBuffer:witnessHost destinationOffset:0 size:witness.length];[b endEncoding];if(!done(main))return 12;
  NSMutableArray*files=[NSMutableArray new];for(unsigned k=0;k<nodeCount;k++){NSMutableDictionary*f=[NSMutableDictionary new];for(NSString*key in @[@"coordinates",@"geometry",@"counter"]){NSString*name=[NSString stringWithFormat:@"trial-%u-node-%u-%@.bin",trial,k,key];id<MTLBuffer>h=nodes[k][[key stringByAppendingString:@"Host"]];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:name]atomically:YES];f[key]=name;}[files addObject:f];}
  NSString*recordName=[NSString stringWithFormat:@"trial-%u-records.bin",trial],*witnessName=[NSString stringWithFormat:@"trial-%u-witness.bin",trial];[[NSData dataWithBytes:recordHost.contents length:recordHost.length]writeToFile:[out stringByAppendingPathComponent:recordName]atomically:YES];if(witnessHost)[[NSData dataWithBytes:witnessHost.contents length:witnessHost.length]writeToFile:[out stringByAppendingPathComponent:witnessName]atomically:YES];
  [runs addObject:@{@"trial":@(trial),@"candidate":@(candidate),@"resource":@(resource),@"node_specs":specs,@"files":files,@"record_file":recordName,@"witness_file":witnessName,@"command_status":@(main.status),@"intermediate_CPU_waits":@0,@"events":scope?plan.events:@[]}];
 }}
 if(scope)[scope restore];BOOL restored=object_getClass(d)==original;emit(@{@"mode":mode,@"native_reference":@(KP_GRID_NATIVE),@"device":d.name,@"registry_id":@(d.registryID),@"runs":runs,@"rows":@(rows),@"candidates":@(candidates),@"scope_restored":@(restored),@"producer_info":info,@"producer_import":importProof,@"IR_CPU_read_before_execution":@NO,@"CPU_expected_answers_uploaded":@NO,@"performance_benchmark":@NO,@"system_modified":@NO});return restored?0:13;
}}
