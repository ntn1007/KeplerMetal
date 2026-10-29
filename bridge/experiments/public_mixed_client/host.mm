// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#include <dlfcn.h>
static void need(BOOL ok,const char*m){if(!ok)@throw [NSException exceptionWithName:@"TestFailure" reason:@(m) userInfo:nil];}
int main(int argc,char**argv){@autoreleasepool{@try{
 need(argc==7,"compute manifest render plugin output mode");NSString*mode=@(argv[6]);
 id<MTLDevice>d=nil;NSDictionary*identity=nil;for(id<MTLDevice>x in MTLCopyAllDevices()){NSDictionary*i=KPKepler880MIdentity(x);if(i){need(!d,"ambiguous GPU");d=x;identity=i;}}need(d!=nil,"GPU identity");
 id<MTLCommandQueue>q=[d newCommandQueue];need(q!=nil,"queue");Class deviceClass=object_getClass(d),queueClass=object_getClass(q);
 Class nativeCB=objc_getClass("NVMTLCommandBuffer"),nativeRender=objc_getClass("NVMTLRenderCommandEncoder_KEPLER_A"),nativeCompute=objc_getClass("NVMTLComputeCommandEncoder_KEPLER_COMPUTE_A");
 SEL selectors[]={@selector(commandBuffer),@selector(computeCommandEncoder),@selector(renderCommandEncoderWithDescriptor:),@selector(executeCommandsInBuffer:withRange:),@selector(executeCommandsInBuffer:withRange:)};
 Class owners[]={queueClass,nativeCB,nativeCB,nativeRender,nativeCompute};IMP before[5];for(int i=0;i<5;i++){Method m=class_getInstanceMethod(owners[i],selectors[i]);need(m!=nullptr,"native method");before[i]=method_getImplementation(m);}
 NSData*compute=[NSData dataWithContentsOfFile:@(argv[1])],*manifest=[NSData dataWithContentsOfFile:@(argv[2])],*render=[NSData dataWithContentsOfFile:@(argv[3])];NSError*e=nil;
 KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:compute expectedSHA256:@"7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911" manifestData:manifest expectedManifestSHA256:@"225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be" error:&e];need(s!=nil,e.description.UTF8String?:"scope");
 need([s registerRenderingLibraryData:render expectedSHA256:@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7" error:&e],e.description.UTF8String?:"render domain");
 need([s enableAutomaticComputeEncoderFactoriesWithError:&e]&&[s enableAutomaticRenderEncoderFactoriesWithError:&e],e.description.UTF8String?:"factories");
 void*h=dlopen(argv[4],RTLD_NOW|RTLD_LOCAL);need(h!=nullptr,dlerror()?:"plugin");using Client=NSDictionary*(*)(id<MTLDevice>,id<MTLCommandQueue>,id<MTLComputePipelineState>,id<MTLRenderPipelineState>,NSString*,NSString*);Client run=(Client)dlsym(h,"run_public_mixed");need(run!=nullptr,"symbol");
 NSDictionary*result=run(d,q,[s pipelineForFunction:@"gpu_indices"],s.renderPipeline,@(argv[5]),mode);need([result[@"status"]isEqual:@"PASS"],[result[@"error"]description].UTF8String?:"client");
 [s restore];BOOL restored=object_getClass(d)==deviceClass&&object_getClass(q)==queueClass;BOOL methods=YES;for(int i=0;i<5;i++){Method m=class_getInstanceMethod(owners[i],selectors[i]);methods=methods&&m&&method_getImplementation(m)==before[i];}need(restored&&methods,"restore");
 NSDictionary*out=@{@"status":@"PASS",@"mode":mode,@"device_identity":identity,@"client":result,@"scope_events":s.events,@"device_queue_restored":@(restored),@"shared_method_imps_unchanged":@(methods),@"shared_methods_checked":@5,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:nil];need(j!=nil,"json");fwrite(j.bytes,1,j.length,stdout);puts("");dlclose(h);return 0;
 }@catch(NSException*x){fprintf(stderr,"test failure: %s\n",x.reason.UTF8String?:"");return 1;}}}
