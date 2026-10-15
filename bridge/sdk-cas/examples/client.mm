#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerNativeCAS.h"
#include <CommonCrypto/CommonDigest.h>
#include <cstring>

static NSString *digest(NSData *data) {
 unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);
 NSMutableString *s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;
}
static NSData *json(id value) {return[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];}
static id<MTLComputePipelineState>native(id<MTLDevice>d,NSData*data,NSString*f,NSError**error) {
 dispatch_data_t p=dispatch_data_create(data.bytes,data.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)data.length;});
 id<MTLLibrary>library=[d newLibraryWithData:p error:error];id<MTLFunction>entry=[library newFunctionWithName:f];return entry?[d newComputePipelineStateWithFunction:entry error:error]:nil;
}
struct Params {uint32_t seed,n,local,groups,variant;};
static_assert(sizeof(Params)==20,"Client shader parameter ABI");
int main(int argc,char**argv){@autoreleasepool {
 if(argc!=5)return 1;NSString *assets=@(argv[1]),*out=@(argv[3]),*mode=@(argv[4]);
 BOOL negative=[mode isEqual:@"negative"],prepare=[mode isEqual:@"prepare"],baseline=[mode isEqual:@"native"];
 if(!negative&&!prepare&&!baseline&&![mode isEqual:@"execute"])return 1;
 NSDictionary *manifest=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[2])] options:0 error:nil];
 NSMutableData *library=[NSMutableData dataWithContentsOfFile:[assets stringByAppendingPathComponent:manifest[@"library"]]];
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(d.registryID==4294968458)device=d;if(!device)return 2;
 NSMutableArray *certificates=[NSMutableArray new];for(NSDictionary *profile in manifest[@"profiles"])[certificates addObject:[NSMutableData dataWithContentsOfFile:[assets stringByAppendingPathComponent:profile[@"certificate"]]]];
 NSError *error=nil;NSMutableArray *proofs=[NSMutableArray new],*pipelines=[NSMutableArray new],*runs=[NSMutableArray new];
 if(negative) {
  NSDictionary *profile=manifest[@"profiles"][0];NSDictionary *original=[NSJSONSerialization JSONObjectWithData:certificates[0] options:0 error:nil];
  for(NSUInteger test=0;test<8;test++) {
   NSData *inputLibrary=library,*inputCertificate=certificates[0];NSString *libraryHash=manifest[@"library_SHA256"],*certificateHash=profile[@"certificate_SHA256"];
   if(test==0){NSMutableData *changed=[library mutableCopy];((unsigned char*)changed.mutableBytes)[changed.length-1]^=1;inputLibrary=changed;}
   if(test==1){NSMutableData *changed=[certificates[0] mutableCopy];((unsigned char*)changed.mutableBytes)[changed.length-1]^=1;inputCertificate=changed;}
   if(test==2){inputCertificate=certificates.lastObject;certificateHash=[manifest[@"profiles"]lastObject][@"certificate_SHA256"];}
   if(test>=3) {
    NSMutableDictionary *changed=[original mutableCopy];
    if(test==3){changed[@"function"]=@"sdk_keep_comparand";NSMutableDictionary*m=[changed[@"embedded_AIR"]mutableCopy];m[@"name"]=@"sdk_keep_comparand";changed[@"embedded_AIR"]=m;}
    if(test==4){NSMutableDictionary *sass=[changed[@"SASS"]mutableCopy];sass[@"expected_output_component"]=@3;changed[@"SASS"]=sass;}
    if(test==5){NSMutableData *code=[[[NSData alloc]initWithBase64EncodedString:changed[@"repaired_code_base64"] options:0]mutableCopy];NSUInteger n=code.length-64;uint64_t nop=0x4000000000001de4ULL;memcpy((char*)code.mutableBytes+n+16,&nop,8);changed[@"repaired_code_base64"]=[code base64EncodedStringWithOptions:0];changed[@"repaired_code_SHA256"]=digest(code);}
    if(test==6){NSMutableData *code=[[[NSData alloc]initWithBase64EncodedString:changed[@"original_code_base64"] options:0]mutableCopy];NSMutableData *repair=[[[NSData alloc]initWithBase64EncodedString:changed[@"repaired_code_base64"] options:0]mutableCopy];((unsigned char*)code.mutableBytes)[0]^=1;((unsigned char*)repair.mutableBytes)[0]^=1;changed[@"original_code_base64"]=[code base64EncodedStringWithOptions:0];changed[@"original_code_SHA256"]=digest(code);changed[@"repaired_code_base64"]=[repair base64EncodedStringWithOptions:0];changed[@"repaired_code_SHA256"]=digest(repair);}
    if(test==7){changed=[[NSJSONSerialization JSONObjectWithData:certificates[2] options:NSJSONReadingMutableContainers error:nil]mutableCopy];NSMutableData *metadata=[[[NSData alloc]initWithBase64EncodedString:changed[@"native_metadata_base64"] options:0]mutableCopy];((unsigned char*)metadata.mutableBytes)[100]^=1;changed[@"native_metadata_base64"]=[metadata base64EncodedStringWithOptions:0];changed[@"native_metadata_SHA256"]=digest(metadata);}
    inputCertificate=json(changed);certificateHash=digest(inputCertificate);
   }
   NSDictionary *proof=nil;id<MTLComputePipelineState>p=KPCreateCertifiedNativeCASPipeline(device,inputLibrary,libraryHash,inputCertificate,certificateHash,&error,&proof);
   if(p||!error)return 3;[proofs addObject:@{@"case":@(test),@"pipeline_created":@NO,@"error":error.description,@"evidence":proof?:@{}}];
  }
 }else {
  NSUInteger i=0;for(NSDictionary *profile in manifest[@"profiles"]) {
   NSDictionary *proof=nil;id<MTLComputePipelineState>p=nil;
   if(baseline||![profile[@"candidate"]boolValue])p=native(device,library,profile[@"function"],&error);
   else p=KPCreateCertifiedNativeCASPipeline(device,library,manifest[@"library_SHA256"],certificates[i],profile[@"certificate_SHA256"],&error,&proof);
   if(!p){fprintf(stderr,"%s\n",error.description.UTF8String);return 4;}
   [pipelines addObject:p];[proofs addObject:@{@"function":profile[@"function"],@"evidence":proof?:@{},@"pipeline_max_threads":@(p.maxTotalThreadsPerThreadgroup),@"static_shared_bytes":@(p.staticThreadgroupMemoryLength)}];i++;
  }
  // Caller-owned inputs are destroyed before any user command buffer commit.
  memset(library.mutableBytes,0,library.length);for(NSMutableData*c in certificates)memset(c.mutableBytes,0,c.length);[certificates removeAllObjects];
  id<MTLCommandQueue>queue=[device newCommandQueue];NSUInteger profileIndex=0;
  for(NSDictionary *profile in manifest[@"profiles"]) {
   id<MTLComputePipelineState>p=pipelines[profileIndex++];
   for(NSNumber *localValue in @[@33,@128,@1024])for(NSUInteger variant=0;variant<2;variant++)for(NSUInteger iteration=0;iteration<3;iteration++){@autoreleasepool {
    uint32_t local=localValue.unsignedIntValue;Params params={0x2468u+53u*(uint32_t)iteration,local*3,local,3,(uint32_t)variant};if(p.maxTotalThreadsPerThreadgroup<local)return 5;
    NSUInteger bytes=params.n*16+128;id<MTLBuffer>staging=[device newBufferWithLength:bytes options:MTLResourceStorageModeShared],output=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate],unusedGlobal=[device newBufferWithLength:params.n*4 options:MTLResourceStorageModePrivate];memset(staging.contents,0xa5,bytes);
    id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:staging sourceOffset:0 toBuffer:output destinationOffset:0 size:bytes];[b endEncoding];
    id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:p];[e setBytes:&params length:sizeof params atIndex:0];[e setBuffer:output offset:64 atIndex:1];[e setBuffer:unusedGlobal offset:0 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];
    b=[cb blitCommandEncoder];[b copyFromBuffer:output sourceOffset:0 toBuffer:staging destinationOffset:0 size:bytes];[b endEncoding];if(!prepare){[cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return 6;}
    NSString *file=[NSString stringWithFormat:@"%@-l%u-v%lu-i%lu.bin",profile[@"function"],local,(unsigned long)variant,(unsigned long)iteration];if(![[NSData dataWithBytes:staging.contents length:bytes]writeToFile:[out stringByAppendingPathComponent:file] atomically:YES])return 7;
    [runs addObject:@{@"function":profile[@"function"],@"candidate":profile[@"candidate"],@"layout":profile[@"layout"],@"local":@(local),@"groups":@3,@"variant":@(variant),@"iteration":@(iteration),@"seed":@(params.seed),@"file":file,@"committed":@(!prepare),@"command_status":@(cb.status)}];
   }}
  }
 }
 NSDictionary *result=@{@"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"proofs":proofs,@"runs":runs,@"caller_inputs_wiped_before_commit":@(!negative),@"system_modified":@NO,@"performance_benchmark":@NO};NSData *data=json(result);fwrite(data.bytes,1,data.length,stdout);puts("");return 0;
}}
