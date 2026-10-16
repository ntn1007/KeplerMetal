// SPDX-License-Identifier: MIT
// Real native constructor refusals; no command buffer or GPU dispatch.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>

extern "C" id<MTLComputePipelineState> KPExperimentalCreateNativeReservePipeline(
 id<MTLDevice>, NSURL*, NSString*, NSData*, NSString*, uint32_t, NSError**,
 NSDictionary**) NS_RETURNS_RETAINED;

static NSString *sha(NSData *data) {
 unsigned char h[32]; CC_SHA256(data.bytes, (CC_LONG)data.length, h);
 NSMutableString *s=[NSMutableString string];
 for(unsigned char b:h)[s appendFormat:@"%02x", b];
 return s;
}

int main(int argc, char **argv) { @autoreleasepool {
 if(argc!=4)return 1;
 NSString *assets=@(argv[1]), *mode=@(argv[3]);
 NSArray *early=@[@"unaligned",@"oversize",@"short-metadata",@"nil-device"];
 NSArray *late=@[@"wrong-code",@"wrong-gpr",@"wrong-control",@"wrong-frame",@"downward",@"wrong-function"];
 if(![early containsObject:mode]&&![late containsObject:mode])return 1;
 id<MTLDevice>device=nil;
 for(id<MTLDevice>d in MTLCopyAllDevices())
  if(d.registryID==4294968458&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"])device=d;
 NSString *driver=sha([NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"]);
 if(!device||![driver isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"control_flow_config.json"]] options:0 error:nil];
 NSDictionary *cert=config[@"certificates"][@"depth96"];
 NSArray *words=cert[@"metadata_words"]; if(words.count!=58)return 2;
 NSMutableData *metadata=[NSMutableData dataWithLength:232];
 for(unsigned i=0;i<58;i++){uint32_t v=[words[i]unsignedIntValue];memcpy((char*)metadata.mutableBytes+4*i,&v,4);}
 NSString *codeHash=cert[@"code_SHA256"], *function=@"depth96";
 uint32_t reserve=4096;
 if([mode isEqual:@"wrong-code"])codeHash=[@"0" stringByPaddingToLength:64 withString:@"0" startingAtIndex:0];
 unsigned field=[mode isEqual:@"wrong-gpr"]?7:([mode isEqual:@"wrong-control"]?11:12);
 if([@[@"wrong-gpr",@"wrong-control",@"wrong-frame"]containsObject:mode]){
  uint32_t v;memcpy(&v,(char*)metadata.bytes+4*field,4);v^=1;memcpy((char*)metadata.mutableBytes+4*field,&v,4);
 }
 if([mode isEqual:@"downward"])reserve=1024;
 if([mode isEqual:@"unaligned"])reserve=4095;
 if([mode isEqual:@"oversize"])reserve=8192;
 if([mode isEqual:@"short-metadata"])metadata.length=228;
 if([mode isEqual:@"wrong-function"])function=@"depth64";
 Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));
 if(!method)return 2; IMP before=method_getImplementation(method);
 NSURL *url=[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"control_flow.metallib"]];
 NSError *error=nil; NSDictionary *proof=nil;
 id<MTLComputePipelineState>pso=KPExperimentalCreateNativeReservePipeline(
  [mode isEqual:@"nil-device"]?nil:device,url,function,metadata,codeHash,reserve,&error,&proof);
 BOOL restored=method_getImplementation(method)==before;
 BOOL earlyCase=[early containsObject:mode];
 BOOL rejection=!pso&&error&&restored;
 if(earlyCase)rejection=rejection&&!proof;
 else rejection=rejection&&[proof[@"constructor_restored"]boolValue]
  &&![proof[@"contract_verified"]boolValue]&&[proof[@"calls"]unsignedIntValue]==1;
 // The recovery uses a different original native function, outside interception.
 // It creates a PSO only. No command queue or command buffer is created here.
 NSError *recoveryError=nil;
 id<MTLLibrary>lib=[device newLibraryWithURL:url error:&recoveryError];
 id<MTLFunction>f=[lib newFunctionWithName:@"depth0"];
 id<MTLComputePipelineState>recovery=f?[device newComputePipelineStateWithFunction:f error:&recoveryError]:nil;
 BOOL recoveryOK=recovery&&method_getImplementation(method)==before;
 NSDictionary *result=@{@"device":device.name,@"registry_id":@(device.registryID),@"driver_SHA256":driver,
  @"mode":mode,@"status":rejection&&recoveryOK?@"PASS":@"FAIL",@"early_contract":@(earlyCase),
  @"pipeline_created":@(pso!=nil),@"rejection_verified":@(rejection),@"constructor_restored":@(restored),
  @"native_recovery_pipeline_created":@(recoveryOK),@"error":error.description?:@"",@"import":proof?:@{},
  @"GPU_command_buffers":@0,@"kernel_dispatches":@0,@"runs":@[],@"system_modified":@NO,@"performance_benchmark":@NO};
 NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
 fwrite(json.bytes,1,json.length,stdout);puts("");
 return rejection&&recoveryOK?0:3;
}}
