// SPDX-License-Identifier: MIT
// Metal metadata/lifetime contracts: no command buffer is submitted.
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
static NSString*hash(NSData*d){unsigned char b[32];CC_SHA256(d.bytes,(CC_LONG)d.length,b);NSMutableString*s=[NSMutableString new];for(unsigned char x:b)[s appendFormat:@"%02x",x];return s;}
static void emit(id x){NSData*j=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
#include "NativeSourceLibraryReception.inc"
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;NSString*assets=@(argv[1]);BOOL tagged=atoi(argv[2])==1;id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}if(!d)return 2;
 id<MTLCommandQueue>q=[d newCommandQueue];Class deviceBefore=object_getClass(d),queueBefore=object_getClass(q);NSError*error=nil;
 auto bytes=[&](NSString*n){return[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:n]];};
 NSData*consumer=bytes(@"consumer.metallib"),*manifest=bytes(@"consumer.json");KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:consumer expectedSHA256:hash(consumer)manifestData:manifest expectedManifestSHA256:hash(manifest)error:&error];if(!s)return 3;
 for(NSArray*a in @[@[@"gpu_command_selector.metallib",@0],@[@"gpu_command_geometry.metallib",@1],@[@"gpu_command_bindings.metallib",@2],@[@"materializer.metallib",@3]]){NSData*b=bytes(a[0]);BOOL ok=NO;switch([a[1]intValue]){case 0:ok=[s enableGPUCommandSelectionWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 1:ok=[s enableGPUCommandGeometryWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 2:ok=[s enableGPUCommandBindingsWithLibraryData:b expectedSHA256:hash(b)error:&error];break;case 3:ok=[s enableGPUCommandIRv2WithLibraryData:b expectedSHA256:hash(b)error:&error];}if(!ok)return 3;}
 NSData*source=bytes(tagged?@"reusable_producer.metallib":@"native_producer.metallib");NSString*digest=hash(source);NSArray*selected=@[@"encode_dataflow_basic",@"encode_dataflow_barrier"];NSMutableArray*cases=[NSMutableArray new],*factories=[NSMutableArray new];
 auto check=[&](NSString*name,BOOL ok){[cases addObject:@{@"case":name,@"PASS":@(ok)}];if(!ok)fprintf(stderr,"FAIL %s\n",name.UTF8String);return ok;};
 Class scopedDevice=object_getClass(d);NSUInteger eventCount=s.events.count;
 for(NSString*test in @[@"empty_source",@"bad_hash",@"empty_names",@"duplicate_names",@"wrong_name_type",@"missing_function",@"partial_after_valid",@"opposite_ABI",@"old_opaque"]){
  NSData*input=source;NSString*pin=digest;NSArray*names=selected;BOOL mode=tagged;
  if([test isEqual:@"empty_source"])input=[NSData data];else if([test isEqual:@"bad_hash"])pin=@"0000000000000000000000000000000000000000000000000000000000000000";
  else if([test isEqual:@"empty_names"])names=@[];else if([test isEqual:@"duplicate_names"])names=@[selected[0],selected[0]];else if([test isEqual:@"wrong_name_type"])names=(id)@[@7];else if([test isEqual:@"missing_function"])names=@[@"absent"];
  else if([test isEqual:@"partial_after_valid"])names=@[selected[0],@"absent"];else if([test isEqual:@"opposite_ABI"])mode=!tagged;else{input=bytes(@"opaque_producer.metallib");pin=hash(input);}
  error=nil;BOOL accepted=[s registerNativeSourceCommandIRLibraryData:input expectedSHA256:pin functionNames:names reusableContexts:mode error:&error];
  if(!check(test,!accepted&&error&&s.events.count==eventCount&&object_getClass(q)==queueBefore&&object_getClass(d)==scopedDevice))return 4;
 }
 NSMutableData*mutableSource=[source mutableCopy];NSMutableString*mutableName=[selected[0]mutableCopy];NSMutableArray*mutableNames=[NSMutableArray arrayWithObject:mutableName];
 if(![s registerNativeSourceCommandIRLibraryData:mutableSource expectedSHA256:digest functionNames:mutableNames reusableContexts:tagged error:&error])return 5;
 [mutableSource setLength:0];[mutableName setString:@"mutated"];[mutableNames removeAllObjects];
 if(!check(@"immutable_registration",s.events.count>eventCount&&object_getClass(q)!=queueBefore))return 5;
 eventCount=s.events.count;error=nil;if(!check(@"duplicate_registration",![s registerNativeSourceCommandIRLibraryData:source expectedSHA256:digest functionNames:selected reusableContexts:tagged error:&error]&&error&&s.events.count==eventCount))return 5;
 NSMutableArray*liveLibraries=[NSMutableArray new],*liveFunctions=[NSMutableArray new];
 for(NSUInteger l=0;l<3;l++){error=nil;
  id<MTLLibrary>library=nil;if(l==0){dispatch_data_t data=dispatch_data_create(source.bytes,source.length,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{(void)source.length;});library=[d newLibraryWithData:data error:&error];}else if(l==1)library=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:tagged?@"reusable_producer.metallib":@"native_producer.metallib"]]error:&error];else library=[d newLibraryWithFile:[assets stringByAppendingPathComponent:tagged?@"reusable_producer.metallib":@"native_producer.metallib"]error:&error];
  if(!library)return 6;[liveLibraries addObject:library];
  id<MTLFunction>unlisted=[library newFunctionWithName:selected[1]];id<MTLArgumentEncoder>native=[unlisted newArgumentEncoderWithBufferIndex:0];if(!check([NSString stringWithFormat:@"unlisted_passthrough_%lu",l],[NSStringFromClass(object_getClass(unlisted))isEqual:@"_MTLFunctionInternal"]&&[NSStringFromClass(object_getClass(native))isEqual:@"NVMTLIndirectArgumentEncoder"]))return 6;
  for(NSUInteger f=0;f<9;f++){
   error=nil;NSUInteger callbacks=0;id<MTLFunction>fn=nativeSourceFunctionFromLibrary(library,selected[0],f,&error,&callbacks);if(!fn)return 6;[liveFunctions addObject:fn];id<MTLArgumentEncoder>adapted=[fn newArgumentEncoderWithBufferIndex:0];if(!check([NSString stringWithFormat:@"function_%lu_%lu",l,f],callbacks==(f>=7)&&[NSStringFromClass(object_getClass(adapted))isEqual:@"KPCommandIRArgumentEncoder"]&&adapted.encodedLength==48))return 6;
   for(NSUInteger p=0;p<6;p++){error=nil;nativeLibraryReception=@{@"pipeline_factory":@(p)};id<MTLComputePipelineState>pipeline=nativeLibraryPipeline(d,fn,tagged,&error);BOOL ok=pipeline&&!error;
    [factories addObject:@{@"library":@(l),@"function":@(f),@"pipeline":@(p),@"PASS":@(ok),@"receipt":nativeLibraryReception?:@{}}];if(!ok){emit(@{@"failure":@"native_factory",@"library":@(l),@"function":@(f),@"pipeline":@(p),@"error":error.description?:@""});return 7;}}
  }
 }
 [s restore];BOOL restored=object_getClass(d)==deviceBefore&&object_getClass(q)==queueBefore;for(id<MTLLibrary>l in liveLibraries)restored&=[NSStringFromClass(object_getClass(l))isEqual:@"_MTLLibrary"];for(id<MTLFunction>fn in liveFunctions)restored&=[NSStringFromClass(object_getClass(fn))isEqual:@"_MTLFunctionInternal"]&&[NSStringFromClass(object_getClass([fn newArgumentEncoderWithBufferIndex:0]))isEqual:@"NVMTLIndirectArgumentEncoder"];
 if(!check(@"native_objects_restored",restored))return 8;error=nil;if(!check(@"inactive_registration",![s registerNativeSourceCommandIRLibraryData:source expectedSHA256:digest functionNames:selected reusableContexts:tagged error:&error]&&error))return 8;
 emit(@{@"status":@"PASS",@"device":d.name,@"device_identity":KPKepler880MIdentity(d),@"registry_id":@(d.registryID),@"generation_tagged_root":@(tagged),@"source_SHA256":digest,@"cases":cases,@"factories":factories,@"events":s.events,@"GPU_dispatches":@0,@"GPU_submissions":@0,@"system_modified":@NO});return 0;
}}
