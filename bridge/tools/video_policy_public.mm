// SPDX-License-Identifier: MIT
// Public decoding with a pinned, process-local policy-data experiment.
#import <VideoToolbox/VideoToolbox.h>
#include "video_policy_profile.h"

extern "C" NSDictionary *KPVideoVTFixtureDecode(NSString *,NSString *,NSString *);
__attribute__((used)) static auto volatile dependency=&VTIsHardwareDecodeSupported;

int main(int argc,char **argv){@autoreleasepool {
    if(argc!=4||!dependency)return 1;
    NSString *assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
    if(![@[@"inspect",@"cpu",@"native",@"wrong-model",@"model-entry"]containsObject:mode])return 1;
    bool inspect=[mode isEqual:@"inspect"],cpu=[mode isEqual:@"cpu"];
    bool replace=[mode isEqual:@"wrong-model"]||[mode isEqual:@"model-entry"];
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"config.json"]]options:0 error:nil];
    if(!config||![@[@"H264",@"MPEG2Video"]containsObject:config[@"codec"]])return 2;
    KPVideoImagesStart();NSDictionary *before=KPVideoImagesSnapshot();
    NSArray *pins=KPVideoProfilePins(before,config);if(pins.count!=3)return 3;
    NSString *originalHash=KPVideoHash([NSData dataWithContentsOfFile:KPVideoPolicyPath()]);
    NSData *overlay=nil;if(replace){NSString *name=[mode stringByAppendingString:@".plist"];
        overlay=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:name]];
        if(!overlay||![KPVideoHash(overlay)isEqual:config[@"overlay_SHA256"][name]])return 4;}
    if(!KPVideoPolicyBegin((CFDataRef)overlay,!inspect))return 4;
    bool modelPresent=false;NSDictionary *decoded=nil;
    if(!inspect){
        KPVideoPolicyCalibration(true);CFURLRef url=CFURLCreateWithFileSystemPath(kCFAllocatorDefault,
            (CFStringRef)KPVideoPolicyPath(),kCFURLPOSIXPathStyle,false);CFDataRef bytes=nullptr;SInt32 error=0;
        Boolean success=CFURLCreateDataAndPropertiesFromResource(kCFAllocatorDefault,url,&bytes,nullptr,nullptr,&error);
        KPVideoPolicyCalibration(false);CFRelease(url);if(!success||error||!bytes)return 5;
        NSDictionary *plist=[NSPropertyListSerialization propertyListWithData:(NSData*)bytes options:0 format:nil error:nil];
        modelPresent=plist[@"System Support"][@"iMac11,1"]!=nil;CFRelease(bytes);
        if(modelPresent!=[mode isEqual:@"model-entry"])return 5;
        // No private availability call precedes this public API request.
        decoded=KPVideoVTFixtureDecode([assets stringByAppendingPathComponent:@"fixture"],cpu?@"cpu":@"hardware",out);
        if(!decoded)return 6;
    }
    NSDictionary *trace=KPVideoPolicySnapshot();NSDictionary *after=KPVideoImagesSnapshot();
    NSString *afterHash=KPVideoHash([NSData dataWithContentsOfFile:KPVideoPolicyPath()]);
    if(![afterHash isEqual:originalHash])return 7;
    NSDictionary *result=@{@"status":@"OBSERVATION_COMPLETED",@"mode":mode,@"codec":config[@"codec"],
        @"resident_code_pins":pins,@"private_query_invoked_by_host":@NO,
        @"unknown_private_factory_or_decoder_invoked_by_host":@NO,
        @"public_decode":decoded?:(id)[NSNull null],@"calibration_model_entry_present":@(modelPresent),
        @"policy":trace,@"policy_SHA256_before":originalHash,@"policy_SHA256_after":afterHash,
        @"hardware_video_execution_proved":@NO,@"system_modified":@NO,@"performance_benchmark":@NO};
    NSData *json=[NSJSONSerialization dataWithJSONObject:@{@"before":before,@"after":after}
        options:NSJSONWritingPrettyPrinted error:nil];
    if(![json writeToFile:[out stringByAppendingPathComponent:@"images.json"]options:0 error:nil])return 8;
    json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(json.bytes,1,json.length,stdout);puts("");return 0;
}}
