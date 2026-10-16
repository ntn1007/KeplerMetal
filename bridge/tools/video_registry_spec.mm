// SPDX-License-Identifier: MIT
// One-process public-API experiment: preserve RequireHardware and optionally
// also set EnableHardware, as requested by an observed legacy registration.
#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#include <crt_externs.h>
#include <cstring>
#ifndef KPREG_SPEC_BOTH
#define KPREG_SPEC_BOTH 0
#endif
namespace {
OSStatus observedCreate(CFAllocatorRef allocator,CMVideoFormatDescriptionRef format,CFDictionaryRef specification,
    CFDictionaryRef attributes,const VTDecompressionOutputCallbackRecord *callback,VTDecompressionSessionRef *session){
    int argc=*_NSGetArgc();char **argv=*_NSGetArgv();
    bool controlled=argc==4&&(!strcmp(argv[3],"hardware")||!strcmp(argv[3],"cpu"));
    bool required=specification&&CFDictionaryGetValue(specification,
        kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder)==kCFBooleanTrue;
    bool apply=controlled&&required&&KPREG_SPEC_BOTH;
    CFMutableDictionaryRef modified=nullptr;
    if(apply){
        modified=CFDictionaryCreateMutableCopy(kCFAllocatorDefault,0,specification);
        if(!modified)return -108;
        CFDictionarySetValue(modified,kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder,kCFBooleanTrue);
    }
    CFDictionaryRef forwarded=modified?modified:specification;
    OSStatus status=VTDecompressionSessionCreate(allocator,format,forwarded,attributes,callback,session);
    if(controlled){
        NSDictionary *record=@{@"status":@"PUBLIC_API_RETURNED",@"compiled_both":@(KPREG_SPEC_BOTH),
            @"mode":@(argv[3]),@"codec_fourcc":@(CMFormatDescriptionGetMediaSubType(format)),
            @"original_specification":specification?(id)specification:@{},
            @"forwarded_specification":forwarded?(id)forwarded:@{},@"applied":@(apply),
            @"hardware_requirement_preserved":@(!required||(CFDictionaryGetValue(forwarded,
                kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder)==kCFBooleanTrue)),
            @"create_status":@(status),@"system_modified":@NO,@"performance_benchmark":@NO};
        NSData *data=[NSJSONSerialization dataWithJSONObject:record options:NSJSONWritingPrettyPrinted error:nil];
        [data writeToFile:[@(argv[2])stringByAppendingPathComponent:@"specification.json"]options:0 error:nil];
    }
    if(modified)CFRelease(modified);return status;
}
__attribute__((used)) static const struct{const void *replacement,*original;} interpose
__attribute__((section("__DATA,__interpose")))={(void*)&observedCreate,(void*)&VTDecompressionSessionCreate};
}
