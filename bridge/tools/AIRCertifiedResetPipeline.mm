// SPDX-License-Identifier: MIT
#import "AIRCertifiedResetPipeline.h"
#import "KeplerGPUIdentity.h"
#include "NativeCommandBoundaryCapture.inc"
#if __has_feature(objc_arc)
#error This constructor observer requires MRC ownership semantics
#endif
static void resetNeed(bool ok,const char *reason){if(!ok)@throw [NSException exceptionWithName:@"AIRResetProfile" reason:@(reason) userInfo:nil];}
#include "OwnedKeplerComputeCode.inc"
BOOL KPCheckCertifiedResetPipeline(id<MTLComputePipelineState>pipeline,NSString*certificatePath,NSString*codePath,NSDictionary**receipt,NSError**error){
    if(receipt)*receipt=nil;if(error)*error=nil;
    @try{
        resetNeed(pipeline&&KPKepler880MIdentity(pipeline.device)!=nil,"Pipeline GPU differs");
        NSDictionary*cert=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:certificatePath]options:0 error:nil];
        NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
        NSString*digest=driver?captureSHA(driver):@"";
        resetNeed([@[@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054",@"e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645"]containsObject:digest]&&[cert[@"driver_SHA256"]isEqual:digest]&&[cert[@"no_native_call"]boolValue],"Pipeline certificate profile differs");
        NSData*code=resetOwnedComputeCode(pipeline);
        resetNeed(code.length==[cert[@"code_bytes"]unsignedIntegerValue]&&[captureSHA(code)isEqual:cert[@"code_SHA256"]],"Ordinary factory program differs");
        resetNeed(![[NSFileManager defaultManager]fileExistsAtPath:codePath]&&[code writeToFile:codePath atomically:YES],"Fresh program snapshot required");
        if(receipt)*receipt=@{@"code_SHA256":captureSHA(code),@"code_bytes":@(code.length),@"file":codePath.lastPathComponent,@"own_CPU_staging_code":@YES,@"code_replaced":@NO,@"constructor_observer_installed":@NO};return YES;
    }@catch(NSException*x){if(error)*error=[NSError errorWithDomain:@"KeplerMetalAIRReset" code:2 userInfo:@{NSLocalizedDescriptionKey:x.reason?:x.name}];return NO;}
}
id<MTLComputePipelineState> KPNewCertifiedResetPipeline(id<MTLDevice>device,
    NSString *libraryPath,NSString *certificatePath,NSString *directory,
    NSDictionary **receipt,NSError **error){
    id<MTLLibrary>library=nil;id<MTLFunction>function=nil;id<MTLComputePipelineState>pipeline=nil;
    if(receipt)*receipt=nil;if(error)*error=nil;
    @try{
        resetNeed(KPKepler880MIdentity(device)!=nil,"PCI profile differs");
        NSData *data=[NSData dataWithContentsOfFile:libraryPath];
        NSDictionary *cert=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:certificatePath]options:0 error:nil];
        resetNeed(data&&[cert[@"library_SHA256"]isEqual:captureSHA(data)]&&[cert[@"no_native_call"]boolValue],"Library certificate differs");
        NSData *driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
        resetNeed(driver&&[cert[@"driver_SHA256"]isEqual:captureSHA(driver)],"Driver certificate differs");
        resetNeed([[NSFileManager defaultManager]createDirectoryAtPath:directory withIntermediateDirectories:NO attributes:nil error:error],"Fresh capture directory required");
        library=[device newLibraryWithURL:[NSURL fileURLWithPath:libraryPath]error:error];
        resetNeed(library!=nil,"Library construction refused");function=[library newFunctionWithName:@"probe_boundary"];resetNeed(function!=nil,"Function absent");
        resetNeed(beginCapture(directory),"Native observer profile refused");NSDictionary *capture=nil;
        @try{pipeline=[device newComputePipelineStateWithFunction:function error:error];}@finally{capture=finishCapture();}
        resetNeed(pipeline&&[capture[@"constructor_restored"]boolValue],"Pipeline/restoration refused");
        NSArray *programs=capture[@"records"];resetNeed(programs.count==1,"One native program required");NSDictionary *program=programs[0];
        resetNeed([program[@"post_constructor_code_saved"]boolValue]&&[program[@"post_constructor_code_SHA256"]isEqual:cert[@"code_SHA256"]],"Native program differs");
        if(receipt)*receipt=@{@"capture":capture,@"library_SHA256":captureSHA(data),@"code_SHA256":cert[@"code_SHA256"],@"driver_SHA256":cert[@"driver_SHA256"],@"ownership":@"NS_RETURNS_RETAINED MRC factory / ARC caller",@"observer_restored_before_scope":@YES};
    }@catch(NSException *exception){
        [pipeline release];pipeline=nil;if(error)*error=[NSError errorWithDomain:@"KeplerMetalAIRReset" code:1 userInfo:@{NSLocalizedDescriptionKey:exception.reason?:exception.name}];
    }@finally{[function release];[library release];}
    return pipeline;
}
