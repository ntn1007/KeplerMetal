#import "KeplerCPUICB.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
struct P{uint32_t seed,n,local,groups,variant;};
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char x:h)[s appendFormat:@"%02x",x];return s;}
static void emit(id r){NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;NSString*assets=@(argv[1]),*out=@(argv[3]),*mode=@(argv[5]);BOOL prepare=[mode isEqual:@"prepare"],baseline=[mode isEqual:@"native"],registration=[mode isEqual:@"register"];
 if(!prepare&&!baseline&&!registration&&![mode isEqual:@"execute"])return 1;
 NSDictionary*input=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"client-manifest.json"]] options:0 error:nil];
 NSMutableData*lib=[NSMutableData dataWithContentsOfFile:[assets stringByAppendingPathComponent:input[@"library"]]],*abi=[NSMutableData dataWithContentsOfFile:@(argv[2])];NSString*libSHA=sha(lib),*abiSHA=sha(abi);if(![libSHA isEqual:input[@"library_SHA256"]]||![abiSHA isEqual:@(argv[4])])return 2;
 NSMutableDictionary*certificates=[NSMutableDictionary new],*pins=[NSMutableDictionary new];for(NSDictionary*p in input[@"profiles"])if([p[@"candidate"]boolValue]){certificates[p[@"function"]]=[NSMutableData dataWithContentsOfFile:[assets stringByAppendingPathComponent:p[@"certificate"]]];pins[p[@"function"]]=p[@"certificate_SHA256"];}
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 KPCPUICBScope*s=baseline?[KPCPUICBScope installOnDevice:d queue:q libraryData:lib expectedSHA256:libSHA manifestData:abi expectedManifestSHA256:abiSHA error:&error]:[KPCPUICBScope installOnDevice:d queue:q libraryData:lib expectedSHA256:libSHA manifestData:abi expectedManifestSHA256:abiSHA nativeCASCertificates:certificates expectedCertificateSHA256:pins error:&error];
 if(!s){emit(@{@"failure_stage":@"register",@"error":error.description?:@"nil",@"device_class_unchanged":@(object_getClass(d)==original)});return 3;}
 NSDictionary*registered=s.events.lastObject;memset(lib.mutableBytes,0,lib.length);memset(abi.mutableBytes,0,abi.length);for(NSMutableData*c in certificates.allValues)memset(c.mutableBytes,0,c.length);[certificates removeAllObjects];
 NSMutableArray*runs=[NSMutableArray new],*refusals=[NSMutableArray new],*nodes=[NSMutableArray new];
 if(!registration){
  NSUInteger bytes=3072*16+128;unsigned initialLocals[5]={33,128,1024,33,128};
  for(NSUInteger i=0;i<5;i++){id<MTLBuffer>p=[d newBufferWithLength:1024 options:MTLResourceStorageModeShared],o=[d newBufferWithLength:bytes options:MTLResourceStorageModePrivate],h=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];[nodes addObject:[@{@"p":p,@"out":o,@"host":h,@"profile":input[@"profiles"][i],@"local":@(initialLocals[i])}mutableCopy]];}
  MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;desc.maxKernelBufferBindCount=2;desc.inheritBuffers=NO;desc.inheritPipelineState=NO;
  id<MTLIndirectCommandBuffer>source=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:5 options:MTLResourceStorageModeShared],copy=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:5 options:MTLResourceStorageModeShared];
  auto bind=[&](id<MTLIndirectCommandBuffer>icb,NSUInteger i){NSDictionary*n=nodes[i];id<MTLIndirectComputeCommand>c=[icb indirectComputeCommandAtIndex:i];[c setComputePipelineState:[s pipelineForFunction:n[@"profile"][@"function"]]];[c setKernelBuffer:n[@"p"] offset:256 atIndex:0];[c setKernelBuffer:n[@"out"] offset:64 atIndex:1];[c concurrentDispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake([n[@"local"]unsignedIntValue],1,1)];};
  for(NSUInteger i=0;i<5;i++)bind(source,i);
  for(NSUInteger test=0;test<3;test++){BOOL refused=NO;@try{id<MTLIndirectComputeCommand>c=[source indirectComputeCommandAtIndex:0];if(test==0)[c setKernelBuffer:nodes[0][@"p"] offset:0 atIndex:3];if(test==1)[c setKernelBuffer:nodes[0][@"p"] offset:4 atIndex:0];if(test==2)[c concurrentDispatchThreadgroups:MTLSizeMake(4,1,1) threadsPerThreadgroup:MTLSizeMake(1024,1,1)];}@catch(NSException*x){refused=YES;[refusals addObject:@{@"case":@(test),@"reason":x.reason}];}if(!refused)return 4;}
  auto readback=[&](){id<MTLCommandBuffer>c=[q commandBuffer];id<MTLBlitCommandEncoder>b=[c blitCommandEncoder];for(NSDictionary*n in nodes)[b copyFromBuffer:n[@"out"] sourceOffset:0 toBuffer:n[@"host"] destinationOffset:0 size:bytes];[b endEncoding];return done(c);};
  for(NSUInteger trial=0;trial<6;trial++){@autoreleasepool{
   if(trial==2){if(!KPCopyCPUICBCommands(source,NSMakeRange(0,5),copy,0,&error))return 5;[source resetWithRange:NSMakeRange(0,5)];}
   if(trial==3){for(NSUInteger i=0;i<5;i++){nodes[i][@"local"]=@1024;bind(copy,i);}}
   NSUInteger variant=(trial==1||trial==3)?1:0;id<MTLCommandBuffer>init=[q commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];
   for(NSUInteger i=0;i<5;i++){NSDictionary*n=nodes[i];id<MTLBuffer>p=n[@"p"],h=n[@"host"];uint32_t local=[n[@"local"]unsignedIntValue];P v={0x468au+61u*(uint32_t)trial+17u*(uint32_t)i,local*3,local,3,(uint32_t)variant};memset(p.contents,0xa5,p.length);memcpy((char*)p.contents+256,&v,sizeof(v));memset(h.contents,0xa5,bytes);[b copyFromBuffer:h sourceOffset:0 toBuffer:n[@"out"] destinationOffset:0 size:bytes];}
   [b endEncoding];if(!done(init))return 6;
   id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(![s adaptComputeEncoder:e error:&error])return 7;Class nativeEncoder=class_getSuperclass(object_getClass(e));NSRange range=trial==2?NSMakeRange(1,3):trial==4?NSMakeRange(0,0):NSMakeRange(0,5);
   @try{[e executeCommandsInBuffer:trial>=2?copy:source withRange:range];}@catch(NSException*x){[e endEncoding];emit(@{@"failure_stage":@"encode",@"trial":@(trial),@"reason":x.reason?:@"nil",@"events":s.events});return 8;}
   NSDictionary*event=s.events.lastObject;[e endEncoding];if(!readback())return 9;for(NSDictionary*n in nodes){id<MTLBuffer>h=n[@"host"];for(NSUInteger j=0;j<bytes;j++)if(((unsigned char*)h.contents)[j]!=0xa5)return 10;}
   BOOL restoredBefore=NO;if(trial==5){[s restore];restoredBefore=object_getClass(d)==original&&object_getClass(e)==nativeEncoder;s=nil;source=nil;copy=nil;}
   if(!prepare&&!done(cb))return 11;if(!readback())return 12;NSMutableArray*outputs=[NSMutableArray new];
   for(NSUInteger i=0;i<5;i++){NSDictionary*n=nodes[i];NSString*file=[NSString stringWithFormat:@"trial-%lu-node-%lu.bin",(unsigned long)trial,(unsigned long)i];id<MTLBuffer>h=n[@"host"],p=n[@"p"];if(![[NSData dataWithBytes:h.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:file] atomically:YES])return 13;P v;memcpy(&v,(char*)p.contents+256,sizeof(v));[outputs addObject:@{@"file":file,@"node":@(i),@"function":n[@"profile"][@"function"],@"candidate":n[@"profile"][@"candidate"],@"layout":n[@"profile"][@"layout"],@"local":@(v.local),@"groups":@3,@"seed":@(v.seed),@"variant":@(v.variant),@"active":@(trial!=4&&(trial!=2||(i>=1&&i<=3)))}];}
   [runs addObject:@{@"trial":@(trial),@"outputs":outputs,@"command_status":@(cb.status),@"committed":@(!prepare),@"preparation_outputs_untouched":@YES,@"execution_event":event,@"scope_restored_before_commit":@(restoredBefore)}];
  }}
 }
 if(s)[s restore];BOOL restored=object_getClass(d)==original;emit(@{@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),@"registration":registered,@"runs":runs,@"refusals":refusals,@"caller_data_wiped_before_materialization":@YES,@"scope_restored":@(restored),@"system_modified":@NO,@"performance_benchmark":@NO});return restored?0:14;
}}
