// SPDX-License-Identifier: MIT
#import "KeplerNativeAllocation.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>

static NSString *digest(NSData *data) {
 unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);
 NSMutableString*s=[NSMutableString string];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;
}
static NSData *encode(id object) {
 return [NSJSONSerialization dataWithJSONObject:object options:NSJSONWritingPrettyPrinted error:nil];
}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*mode=@(argv[3]);
 NSArray*modes=@[@"library_hash",@"certificate_hash",@"root_type",@"schema_boolean",@"fractional_word",
  @"reserve",@"code_size",@"driver",@"short_metadata",@"nil_device",@"library_field",@"missing_function",
  @"code_hash",@"gpr",@"static_word",@"function"];
 if(![modes containsObject:mode])return 1;
 id<MTLDevice>device=nil;
 for(id<MTLDevice>d in MTLCopyAllDevices())if(d.registryID==4294968458&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"])device=d;
 if(!device)return 2;
 NSDictionary*manifest=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"native-allocation-manifest.json"]]options:0 error:nil];
 NSData*originalLibrary=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"control_flow.metallib"]];
 NSData*originalCertificate=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:manifest[@"certificates"][@"depth96"][@"file"]]];
 NSString*libraryHash=manifest[@"library_sha256"],*certificateHash=manifest[@"certificates"][@"depth96"][@"SHA256"];
 if(![digest(originalLibrary)isEqual:libraryHash]||![digest(originalCertificate)isEqual:certificateHash])return 2;
 NSData*library=originalLibrary,*certificate=originalCertificate;
 NSMutableDictionary*changed=[NSJSONSerialization JSONObjectWithData:certificate options:NSJSONReadingMutableContainers error:nil];
 BOOL raw=[@[@"library_hash",@"certificate_hash",@"nil_device"]containsObject:mode];
 if([mode isEqual:@"library_hash"]){NSMutableData*b=[library mutableCopy];((uint8_t*)b.mutableBytes)[b.length-1]^=1;library=b;}
 if([mode isEqual:@"certificate_hash"]){NSMutableData*b=[certificate mutableCopy];((uint8_t*)b.mutableBytes)[b.length-1]^=1;certificate=b;}
 if([mode isEqual:@"schema_boolean"])changed[@"schema"]=@YES;
 if([mode isEqual:@"fractional_word"])changed[@"metadata_words"][12]=@1732.5;
 if([mode isEqual:@"reserve"])changed[@"control_reserve"]=@1024;
 if([mode isEqual:@"code_size"])changed[@"code_bytes"]=@104064;
 if([mode isEqual:@"driver"])changed[@"driver_sha256"]=[@"0" stringByPaddingToLength:64 withString:@"0" startingAtIndex:0];
 if([mode isEqual:@"short_metadata"])[changed[@"metadata_words"]removeLastObject];
 if([mode isEqual:@"library_field"])changed[@"library_sha256"]=[@"0" stringByPaddingToLength:64 withString:@"0" startingAtIndex:0];
 if([mode isEqual:@"missing_function"])changed[@"function"]=@"not_a_present_function";
 if([mode isEqual:@"code_hash"])changed[@"native_code_sha256"]=[@"0" stringByPaddingToLength:64 withString:@"0" startingAtIndex:0];
 if([mode isEqual:@"gpr"])changed[@"metadata_words"][7]=@62;
 if([mode isEqual:@"static_word"]){NSUInteger v=[changed[@"metadata_words"][27]unsignedIntegerValue];changed[@"metadata_words"][27]=@(v^1);}
 if([mode isEqual:@"function"])changed[@"function"]=@"depth64";
 if(!raw){certificate=encode([mode isEqual:@"root_type"]?@[]:changed);certificateHash=digest(certificate);}
 Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));
 if(!method)return 2;IMP before=method_getImplementation(method);
 NSError*error=nil;NSDictionary*proof=nil;
 id<MTLComputePipelineState>pipeline=KPCreateCertifiedNativeAllocationPipeline(
  [mode isEqual:@"nil_device"]?nil:device,library,libraryHash,certificate,certificateHash,&error,&proof);
 BOOL late=[@[@"code_hash",@"gpr",@"static_word",@"function"]containsObject:mode];
 BOOL missing=[mode isEqual:@"missing_function"],restored=method_getImplementation(method)==before;
 BOOL rejected=!pipeline&&error&&restored;
 if(late)rejected=rejected&&[proof[@"gate_accepted"]boolValue]&&[proof[@"constructor_entered"]boolValue]
  &&[proof[@"calls"]unsignedIntegerValue]==1&&![proof[@"contract_verified"]boolValue]&&[proof[@"constructor_restored"]boolValue];
 else if(missing)rejected=rejected&&[proof[@"gate_accepted"]boolValue]&&![proof[@"constructor_entered"]boolValue]
  &&[proof[@"calls"]unsignedIntegerValue]==0&&[proof[@"constructor_restored"]boolValue];
 else rejected=rejected&&![proof[@"gate_accepted"]boolValue]&&![proof[@"constructor_entered"]boolValue];
 // Verify native construction after refusal, with the original unmodified data.
 dispatch_data_t bytes=dispatch_data_create(originalLibrary.bytes,originalLibrary.length,
  dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)originalLibrary.length;});
 NSError*recoveryError=nil;id<MTLLibrary>lib=[device newLibraryWithData:bytes error:&recoveryError];
 id<MTLFunction>function=[lib newFunctionWithName:@"depth0"];
 id<MTLComputePipelineState>recovery=function?[device newComputePipelineStateWithFunction:function error:&recoveryError]:nil;
 BOOL recoveryOK=recovery&&method_getImplementation(method)==before;
 NSDictionary*result=@{@"mode":mode,@"status":rejected&&recoveryOK?@"PASS":@"FAIL",
  @"device":device.name,@"registry_id":@(device.registryID),@"phase":late?@"constructor":missing?@"missing_callback":@"gate",
  @"pipeline_returned":@(pipeline!=nil),@"rejection_verified":@(rejected),@"error":error.description?:@"",
  @"constructor_restored":@(restored),@"native_recovery_pipeline_created":@(recoveryOK),@"import":proof?:@{},
  @"GPU_command_buffers":@0,@"kernel_dispatches":@0,@"runs":@[],@"system_modified":@NO,@"performance_benchmark":@NO};
 NSData*output=encode(result);fwrite(output.bytes,1,output.length,stdout);puts("");return rejected&&recoveryOK?0:3;
}}
