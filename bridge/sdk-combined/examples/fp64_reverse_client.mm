// Public SDK client: typed reverse conversions followed by GPU-only promotion.
#import "KeplerFP64.h"
#import <objc/runtime.h>
#include <cstring>

static BOOL done(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=5)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSUInteger trials=strtoul(argv[4],nullptr,10);BOOL prep=[mode isEqual:@"prepare"],negative=[mode isEqual:@"no_producer"];if((!prep&&!negative&&![mode isEqual:@"execute"])||(trials!=1&&trials!=9))return 1;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));IMP before=method?method_getImplementation(method):nil;Class deviceClass=object_getClass(d);if(!before)return 2;
 NSDictionary*manifest=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"fp64_manifest.json"]]options:0 error:nil];if([manifest[@"programs"]count]!=60)return 3;
 NSMutableData*carrier=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"fp64_carrier.metallib"]]mutableCopy];NSMutableDictionary*programs=[NSMutableDictionary dictionary];
 for(NSDictionary*row in manifest[@"programs"]){NSString*k=[NSString stringWithFormat:@"%@-l%@",row[@"operation"],row[@"local"]];NSMutableData*b=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[NSString stringWithFormat:@"fp64_%@.sass",k]]]mutableCopy];if(!b.length)return 3;programs[k]=b;}
 NSError*error=nil;NSMutableDictionary*bad=[programs mutableCopy];NSMutableData*changed=[programs[@"to_i64_rm-l32"]mutableCopy];((uint8_t*)changed.mutableBytes)[0]^=1;bad[@"to_i64_rm-l32"]=changed;
 if([KPBinary64Library libraryWithDevice:d carrierData:carrier programs:bad error:&error]||!error||method_getImplementation(method)!=before)return 4;
 KPBinary64Library*library=[KPBinary64Library libraryWithDevice:d carrierData:carrier programs:programs error:&error];if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 5;}NSDictionary*qualification=library.qualification;
 for(NSMutableData*b in programs.allValues)memset(b.mutableBytes,0,b.length);memset(carrier.mutableBytes,0,carrier.length);programs=nil;bad=nil;changed=nil;carrier=nil;
 id<MTLCommandQueue>queue=[d newCommandQueue];NSMutableArray*runs=[NSMutableArray array],*refusals=[NSMutableArray array];
 for(NSUInteger t=0;t<trials;t++){@autoreleasepool{
  NSUInteger n=(NSUInteger[]){65,2057,12289}[t%3],local=(NSUInteger[]){32,128,1024}[t%3],inputBytes=256+n*16+128,outputBytes=128+n*16+256;
  NSData*raw=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[NSString stringWithFormat:@"reverse-input-l%lu-t%lu.bin",(unsigned long)local,(unsigned long)(t%3)]]];if(raw.length!=n*8)return 6;
  NSMutableArray*hostInputs=[NSMutableArray array],*gpuInputs=[NSMutableArray array],*hostOutputs=[NSMutableArray array],*gpuOutputs=[NSMutableArray array];
  for(unsigned wide=0;wide<2;wide++){id<MTLBuffer>h=[d newBufferWithLength:inputBytes options:MTLResourceStorageModeShared],g=[d newBufferWithLength:inputBytes options:MTLResourceStorageModePrivate];if(!h||!g)return 6;memset(h.contents,0xa5,inputBytes);
   for(NSUInteger i=0;i<n;i++){memcpy((char*)h.contents+256+i*(wide?16:8),(char*)raw.bytes+i*8,8);if(wide){uint64_t marker=0x77aa55cc8899dd00ull;memcpy((char*)h.contents+256+i*16+8,&marker,8);}}[hostInputs addObject:h];[gpuInputs addObject:g];}
  for(unsigned k=0;k<36;k++){id<MTLBuffer>h=[d newBufferWithLength:outputBytes options:MTLResourceStorageModeShared],g=[d newBufferWithLength:outputBytes options:MTLResourceStorageModePrivate];if(!h||!g)return 6;memset(h.contents,0xa5,outputBytes);memset((char*)h.contents+128,0xc7,n*16);[hostOutputs addObject:h];[gpuOutputs addObject:g];}
  id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>bl=[upload blitCommandEncoder];for(unsigned i=0;i<2;i++)[bl copyFromBuffer:hostInputs[i] sourceOffset:0 toBuffer:gpuInputs[i] destinationOffset:0 size:inputBytes];for(unsigned k=0;k<36;k++)[bl copyFromBuffer:hostOutputs[k] sourceOffset:0 toBuffer:gpuOutputs[k] destinationOffset:0 size:outputBytes];[bl endEncoding];if(!done(upload))return 7;
  if(t==0){
   KPBinary64Input*v=[KPBinary64Input inputWithBuffer:gpuInputs[0] offset:256 stride:8];
   for(unsigned family=0;family<3;family++){NSError*e=nil;NSDictionary*proof=nil;id<MTLCommandBuffer>cb=[queue commandBuffer];if([library encodeOperation:(KPBinary64Operation)(KPBinary64ToFloat32Nearest+family*4) commandBuffer:cb inputs:@[v,v] output:gpuOutputs[0] outputOffset:128 count:n threadsPerGroup:local stamp:0 error:&e evidence:&proof]||!e||proof)return 8;[refusals addObject:@{@"case":[NSString stringWithFormat:@"wrong_arity_%u",family],@"rejected":@YES,@"committed":@NO}];}
   NSError*e=nil;NSDictionary*proof=nil;id<MTLCommandBuffer>cb=[queue commandBuffer];if([library encodeOperation:KPBinary64ToFloat32Nearest commandBuffer:cb inputs:@[v] output:gpuOutputs[0] outputOffset:129 count:n threadsPerGroup:local stamp:0 error:&e evidence:&proof]||!e||proof)return 8;[refusals addObject:@{@"case":@"misaligned_typed_output",@"rejected":@YES,@"committed":@NO}];
  }
  id<MTLCommandBuffer>main=[queue commandBuffer];NSMutableArray*events=[NSMutableArray array];
  for(unsigned k=0;k<24;k++){
   if(negative&&k==0){[events addObject:@{@"skipped_producer":@YES,@"encoded_dispatches":@0}];continue;}
   unsigned op=k/2,wide=k%2;KPBinary64Input*v=[KPBinary64Input inputWithBuffer:gpuInputs[wide] offset:256 stride:wide?16:8];NSDictionary*proof=nil;uint32_t stamp=0x85d10000u^(uint32_t)(t*101)^(k*31);
   if(![library encodeOperation:(KPBinary64Operation)(KPBinary64ToFloat32Nearest+op) commandBuffer:main inputs:@[v] output:gpuOutputs[k] outputOffset:128 count:n threadsPerGroup:local stamp:stamp error:&error evidence:&proof])return 9;[events addObject:proof];
  }
  for(unsigned op=0;op<12;op++){
   KPBinary64Input*v=[KPBinary64Input inputWithBuffer:gpuOutputs[op*2] offset:128 stride:16];KPBinary64Operation back=op<4?KPBinary64FromFloat32Bits:op<8?KPBinary64FromSigned64:KPBinary64FromUnsigned64;NSDictionary*proof=nil;unsigned k=24+op;uint32_t stamp=0x85d10000u^(uint32_t)(t*101)^(k*31);
   if(![library encodeOperation:back commandBuffer:main inputs:@[v] output:gpuOutputs[k] outputOffset:128 count:n threadsPerGroup:local stamp:stamp error:&error evidence:&proof])return 10;[events addObject:proof];
  }
  auto readback=[&]()->BOOL{id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>e=[cb blitCommandEncoder];for(unsigned k=0;k<36;k++)[e copyFromBuffer:gpuOutputs[k] sourceOffset:0 toBuffer:hostOutputs[k] destinationOffset:0 size:outputBytes];[e endEncoding];return done(cb);};
  if(!readback())return 11;for(id<MTLBuffer>h in hostOutputs)for(NSUInteger i=0;i<h.length;i++)if(((uint8_t*)h.contents)[i]!=(i>=128&&i<128+n*16?0xc7:0xa5))return 11;
  BOOL closed=t+1==trials;if(closed)library=nil;if(!prep&&!done(main))return 12;if(!readback())return 13;
  id<MTLCommandBuffer>check=[queue commandBuffer];bl=[check blitCommandEncoder];NSMutableArray*readInputs=[NSMutableArray array];for(unsigned i=0;i<2;i++){id<MTLBuffer>h=[d newBufferWithLength:inputBytes options:MTLResourceStorageModeShared];[bl copyFromBuffer:gpuInputs[i] sourceOffset:0 toBuffer:h destinationOffset:0 size:inputBytes];[readInputs addObject:h];}[bl endEncoding];if(!done(check))return 13;
  NSMutableArray*inputFiles=[NSMutableArray array],*outputFiles=[NSMutableArray array];for(unsigned i=0;i<2;i++){id<MTLBuffer>h=readInputs[i],original=hostInputs[i];if(memcmp(h.contents,original.contents,inputBytes))return 14;NSString*f=[NSString stringWithFormat:@"trial-%lu-input-%u.bin",(unsigned long)t,i];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES])return 15;[inputFiles addObject:f];}
  for(unsigned k=0;k<36;k++){id<MTLBuffer>h=hostOutputs[k];NSString*f=[NSString stringWithFormat:@"trial-%lu-output-%u.bin",(unsigned long)t,k];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES])return 15;[outputFiles addObject:f];}
  [runs addObject:@{@"trial":@(t),@"recipe_trial":@(t%3),@"count":@(n),@"local":@(local),@"inputs":inputFiles,@"outputs":outputFiles,@"events":events,@"before_commit_untouched":@YES,@"library_released_before_commit":@(closed),@"committed":@(!prep),@"command_status":@(main.status)}];
 }}emit(@{@"mode":mode,@"registry_id":@(d.registryID),@"runs":runs,@"refusals":refusals,@"bad_program_rejected":@YES,@"caller_program_data_wiped":@YES,@"qualification":qualification,@"constructor_restored":@(method_getImplementation(method)==before),@"device_class_restored":@(object_getClass(d)==deviceClass),@"CPU_expected_answers_uploaded":@NO,@"intermediate_CPU_readback":@NO,@"system_modified":@NO,@"performance_benchmark":@NO});return method_getImplementation(method)==before?0:16;
}}
