// Independent adapted client: only the public header and extracted static SDK.
// CPU creates raw input bits; conversions and dependent arithmetic run on GPU.
#import "KeplerFP64.h"
#import <objc/runtime.h>
#include <cstring>
#include <vector>

static BOOL done(id<MTLCommandBuffer> cb){[cb commit];[cb waitUntilCompleted];return cb.status==MTLCommandBufferStatusCompleted;}
static void emit(id object){NSData*j=[NSJSONSerialization dataWithJSONObject:object options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
static uint64_t inputBits(unsigned kind,NSUInteger local,NSUInteger i,NSUInteger trial,uint64_t random){
 static const uint64_t ints[]={0,1,2,0xffffffff,0x100000000,0x100000001,0xfffffffffffff,0x10000000000000,0x1fffffffffffff,0x20000000000000,0x20000000000001,0x20000000000003,0x3fffffffffffff,0x40000000000002,0x40000000000006,0xfffffffffffff80,0x1000000000000080,0x1000000000000180,0x7fffffffffffffff,0x8000000000000000,0x8000000000000001,0xffffffffffffffff};
 static const uint32_t floats[]={0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00042,0xffc00042,0x7f800001,0xff800001,0x3f800000,0xbf800000,0x3f800001,0x3f7fffff,0x40000000,0xc0000000,0x3f000000,0xbf000000,0x00800001,2};
 uint64_t raw=random;
 if(kind==2){if(i<26)raw=floats[(i+trial*11)%26];return (random&0xffffffff00000000ull)|(raw&0xffffffff);}
 if(i<43){NSUInteger k=(i+trial*11)%43;raw=k<22?ints[k]:0ull-ints[k-21];}return raw;
}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=5)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);NSUInteger trials=strtoul(argv[4],nullptr,10);
 BOOL prep=[mode isEqual:@"prepare"],negative=[mode isEqual:@"no_producer"];if((!prep&&!negative&&![mode isEqual:@"execute"])||(trials!=1&&trials!=9))return 1;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));IMP before=method?method_getImplementation(method):nil;Class deviceClass=object_getClass(d);if(!before)return 2;
 NSDictionary*manifest=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"fp64_manifest.json"]]options:0 error:nil];if([manifest[@"programs"]count]!=24&&[manifest[@"programs"]count]!=60)return 3;
 NSMutableData*carrier=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"fp64_carrier.metallib"]]mutableCopy];NSMutableDictionary*programs=[NSMutableDictionary dictionary];
 for(NSDictionary*row in manifest[@"programs"]){NSString*k=[NSString stringWithFormat:@"%@-l%@",row[@"operation"],row[@"local"]];NSMutableData*b=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[NSString stringWithFormat:@"fp64_%@.sass",k]]]mutableCopy];if(!b.length)return 3;programs[k]=b;}
 NSMutableDictionary*bad=[programs mutableCopy];NSMutableData*changed=[programs[@"from_f32-l32"]mutableCopy];((uint8_t*)changed.mutableBytes)[0]^=1;bad[@"from_f32-l32"]=changed;NSError*error=nil;
 if([KPBinary64Library libraryWithDevice:d carrierData:carrier programs:bad error:&error]||!error||method_getImplementation(method)!=before)return 4;
 KPBinary64Library*library=[KPBinary64Library libraryWithDevice:d carrierData:carrier programs:programs error:&error];if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 5;}NSDictionary*qualification=library.qualification;
 for(NSMutableData*b in programs.allValues)memset(b.mutableBytes,0,b.length);memset(carrier.mutableBytes,0,carrier.length);programs=nil;bad=nil;changed=nil;carrier=nil;
 id<MTLCommandQueue>queue=[d newCommandQueue];NSMutableArray*runs=[NSMutableArray array],*refusals=[NSMutableArray array];NSArray*names=@[@"from_i64",@"from_u64",@"from_f32"];
 for(NSUInteger t=0;t<trials;t++){@autoreleasepool{
  NSUInteger n=(NSUInteger[]){65,2057,12289}[t%3],local=(NSUInteger[]){32,128,1024}[t%3],recipeTrial=t%3,inputBytes=256+n*16+128,outputBytes=128+n*16+256;
  NSMutableArray*hostInputs=[NSMutableArray array],*gpuInputs=[NSMutableArray array],*hostOutputs=[NSMutableArray array],*gpuOutputs=[NSMutableArray array];
  for(unsigned kind=0;kind<3;kind++){
   id<MTLBuffer>h=[d newBufferWithLength:inputBytes options:MTLResourceStorageModeShared],g=[d newBufferWithLength:inputBytes options:MTLResourceStorageModePrivate];if(!h||!g)return 6;memset(h.contents,0xa5,inputBytes);
   uint64_t state=0x880c20261014ull+97*local+104729*recipeTrial;
   for(NSUInteger i=0;i<n;i++)for(unsigned col=0;col<3;col++){state=state*6364136223846793005ull+1442695040888963407ull;if(col==0){uint64_t raw=inputBits(kind,local,i,recipeTrial,state);memcpy((char*)h.contents+256+i*8,&raw,8);}}
   [hostInputs addObject:h];[gpuInputs addObject:g];
  }
  for(unsigned kind=0;kind<3;kind++){
   id<MTLBuffer>source=hostInputs[kind],h=[d newBufferWithLength:inputBytes options:MTLResourceStorageModeShared],g=[d newBufferWithLength:inputBytes options:MTLResourceStorageModePrivate];if(!h||!g)return 6;memset(h.contents,0xa5,inputBytes);
   for(NSUInteger i=0;i<n;i++){memcpy((char*)h.contents+256+i*16,(char*)source.contents+256+i*8,8);uint64_t marker=0x77aa55cc8899dd00ull;memcpy((char*)h.contents+256+i*16+8,&marker,8);}[hostInputs addObject:h];[gpuInputs addObject:g];
  }
  for(unsigned k=0;k<9;k++){id<MTLBuffer>h=[d newBufferWithLength:outputBytes options:MTLResourceStorageModeShared],g=[d newBufferWithLength:outputBytes options:MTLResourceStorageModePrivate];if(!h||!g)return 6;memset(h.contents,0xa5,outputBytes);memset((char*)h.contents+128,0xc7,n*16);[hostOutputs addObject:h];[gpuOutputs addObject:g];}
  id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>bl=[upload blitCommandEncoder];for(unsigned i=0;i<6;i++)[bl copyFromBuffer:hostInputs[i] sourceOffset:0 toBuffer:gpuInputs[i] destinationOffset:0 size:inputBytes];for(unsigned k=0;k<9;k++)[bl copyFromBuffer:hostOutputs[k] sourceOffset:0 toBuffer:gpuOutputs[k] destinationOffset:0 size:outputBytes];[bl endEncoding];if(!done(upload))return 7;
  if(t==0){
   for(unsigned kind=0;kind<3;kind++){KPBinary64Input*v=[KPBinary64Input inputWithBuffer:gpuInputs[kind] offset:256 stride:8];id<MTLCommandBuffer>cb=[queue commandBuffer];NSError*e=nil;NSDictionary*proof=nil;BOOL accepted=[library encodeOperation:(KPBinary64Operation)(KPBinary64FromSigned64+kind) commandBuffer:cb inputs:@[v,v] output:gpuOutputs[0] outputOffset:128 count:n threadsPerGroup:local stamp:0 error:&e evidence:&proof];if(accepted||!e||proof)return 8;[refusals addObject:@{@"case":[NSString stringWithFormat:@"wrong_arity_%@",names[kind]],@"committed":@NO,@"rejected":@YES}];}
   KPBinary64Input*dense=[KPBinary64Input inputWithBuffer:gpuInputs[2] offset:256 stride:4];id<MTLCommandBuffer>cb=[queue commandBuffer];NSError*e=nil;NSDictionary*proof=nil;if([library encodeOperation:KPBinary64FromFloat32Bits commandBuffer:cb inputs:@[dense] output:gpuOutputs[0] outputOffset:128 count:n threadsPerGroup:local stamp:0 error:&e evidence:&proof]||!e||proof)return 8;[refusals addObject:@{@"case":@"dense_f32_stride4",@"committed":@NO,@"rejected":@YES}];
   cb=[queue commandBuffer];e=nil;proof=nil;if([library encodeOperation:(KPBinary64Operation)99 commandBuffer:cb inputs:@[dense] output:gpuOutputs[0] outputOffset:128 count:n threadsPerGroup:local stamp:0 error:&e evidence:&proof]||!e||proof)return 8;[refusals addObject:@{@"case":@"unknown_operation",@"committed":@NO,@"rejected":@YES}];
  }
  id<MTLCommandBuffer>main=[queue commandBuffer];NSMutableArray*events=[NSMutableArray array];
  for(unsigned k=0;k<6;k++){
   unsigned kind=k/2,wide=k%2;if(negative&&k==0){[events addObject:@{@"skipped_producer":@YES,@"encoded_dispatches":@0}];continue;}
   KPBinary64Input*v=[KPBinary64Input inputWithBuffer:gpuInputs[kind+(wide?3:0)] offset:256 stride:wide?16:8];NSDictionary*proof=nil;uint32_t stamp=0x73c50000u^(uint32_t)(t*101)^(k*31);
   if(![library encodeOperation:(KPBinary64Operation)(KPBinary64FromSigned64+kind) commandBuffer:main inputs:@[v] output:gpuOutputs[k] outputOffset:128 count:n threadsPerGroup:local stamp:stamp error:&error evidence:&proof])return 9;[events addObject:proof];
  }
  for(unsigned kind=0;kind<3;kind++){
   KPBinary64Input*a=[KPBinary64Input inputWithBuffer:gpuOutputs[kind*2] offset:128 stride:16],*b=[KPBinary64Input inputWithBuffer:gpuOutputs[kind*2+1] offset:128 stride:16];NSDictionary*proof=nil;unsigned k=6+kind;uint32_t stamp=0x73c50000u^(uint32_t)(t*101)^(k*31);
   if(![library encodeOperation:KPBinary64Add commandBuffer:main inputs:@[a,b] output:gpuOutputs[k] outputOffset:128 count:n threadsPerGroup:local stamp:stamp error:&error evidence:&proof])return 10;[events addObject:proof];
  }
  auto readback=[&]()->BOOL{id<MTLCommandBuffer>cb=[queue commandBuffer];id<MTLBlitCommandEncoder>e=[cb blitCommandEncoder];for(unsigned k=0;k<9;k++)[e copyFromBuffer:gpuOutputs[k] sourceOffset:0 toBuffer:hostOutputs[k] destinationOffset:0 size:outputBytes];[e endEncoding];return done(cb);};
  if(!readback())return 11;for(id<MTLBuffer>h in hostOutputs)for(NSUInteger i=0;i<h.length;i++)if(((uint8_t*)h.contents)[i]!=(i>=128&&i<128+n*16?0xc7:0xa5))return 11;
  BOOL closed=t+1==trials;if(closed)library=nil;if(!prep&&!done(main))return 12;if(!readback())return 13;
  id<MTLCommandBuffer>check=[queue commandBuffer];bl=[check blitCommandEncoder];NSMutableArray*readInputs=[NSMutableArray array];for(unsigned i=0;i<6;i++){id<MTLBuffer>h=[d newBufferWithLength:inputBytes options:MTLResourceStorageModeShared];[bl copyFromBuffer:gpuInputs[i] sourceOffset:0 toBuffer:h destinationOffset:0 size:inputBytes];[readInputs addObject:h];}[bl endEncoding];if(!done(check))return 13;
  NSMutableArray*inputFiles=[NSMutableArray array],*outputFiles=[NSMutableArray array];for(unsigned i=0;i<6;i++){id<MTLBuffer>h=readInputs[i],original=hostInputs[i];if(memcmp(h.contents,original.contents,inputBytes))return 14;NSString*f=[NSString stringWithFormat:@"trial-%lu-input-%u.bin",(unsigned long)t,i];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES])return 15;[inputFiles addObject:f];}
  for(unsigned k=0;k<9;k++){id<MTLBuffer>h=hostOutputs[k];NSString*f=[NSString stringWithFormat:@"trial-%lu-output-%u.bin",(unsigned long)t,k];if(![[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES])return 15;[outputFiles addObject:f];}
  [runs addObject:@{@"trial":@(t),@"recipe_trial":@(recipeTrial),@"count":@(n),@"local":@(local),@"inputs":inputFiles,@"outputs":outputFiles,@"events":events,@"before_commit_untouched":@YES,@"library_released_before_commit":@(closed),@"committed":@(!prep),@"command_status":@(main.status)}];
 }}emit(@{@"mode":mode,@"registry_id":@(d.registryID),@"runs":runs,@"refusals":refusals,@"bad_program_rejected":@YES,@"caller_program_data_wiped":@YES,@"qualification":qualification,@"constructor_restored":@(method_getImplementation(method)==before),@"device_class_restored":@(object_getClass(d)==deviceClass),@"CPU_expected_answers_uploaded":@NO,@"intermediate_CPU_readback":@NO,@"system_modified":@NO,@"performance_benchmark":@NO});return method_getImplementation(method)==before?0:16;
}}
