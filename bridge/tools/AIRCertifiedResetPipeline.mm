// SPDX-License-Identifier: MIT
#import "AIRCertifiedResetPipeline.h"
#import "KeplerGPUIdentity.h"
#include "NativeCommandBoundaryCapture.inc"
#if __has_feature(objc_arc)
#error This constructor observer requires MRC ownership semantics
#endif
static void resetNeed(bool ok,const char *reason){if(!ok)@throw [NSException exceptionWithName:@"AIRResetProfile" reason:@(reason) userInfo:nil];}
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
