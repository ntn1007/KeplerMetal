// SPDX-License-Identifier: MIT
// Reuse the original decoder helper, without invoking its encoder/main workflow.
#define main KPUnusedOriginalVTMain
#include "video_engine_probe.mm"
#undef main

extern "C" NSDictionary *KPVideoVTFixtureDecode(NSString *folder, NSString *mode, NSString *out) {
    NSDictionary *fixture=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [folder stringByAppendingPathComponent:@"fixture.json"]]options:0 error:nil];
    NSArray *sets=fixture[@"H264_parameter_sets_base64"];
    if (!fixture || sets.count!=2 || ![@[@"cpu",@"hardware"]containsObject:mode]) return nil;
    NSData *sps=[[NSData alloc]initWithBase64EncodedString:sets[0]options:0];
    NSData *pps=[[NSData alloc]initWithBase64EncodedString:sets[1]options:0];
    const uint8_t *pointers[]={(const uint8_t *)sps.bytes,(const uint8_t *)pps.bytes};
    size_t lengths[]={sps.length,pps.length};CMVideoFormatDescriptionRef format=nullptr;
    OSStatus formatStatus=CMVideoFormatDescriptionCreateFromH264ParameterSets(kCFAllocatorDefault,2,pointers,lengths,
        [fixture[@"NAL_length_bytes"]intValue],&format);
    [sps release];[pps release];if(formatStatus||!format)return nil;
    Encoded samples;
    for(NSDictionary *frame in fixture[@"frames"]) {
        NSString *name=frame[@"file"];if(![name isEqual:name.lastPathComponent]){CFRelease(format);return nil;}
        NSData *data=[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:name]];
        if(data.length!=[frame[@"bytes"]unsignedLongLongValue]){CFRelease(format);return nil;}
        CMBlockBufferRef block=nullptr;CMSampleBufferRef sample=nullptr;
        OSStatus status=CMBlockBufferCreateWithMemoryBlock(kCFAllocatorDefault,nullptr,data.length,
            kCFAllocatorDefault,nullptr,0,data.length,0,&block);
        if(!status)status=CMBlockBufferReplaceDataBytes(data.bytes,block,0,data.length);
        CMSampleTimingInfo timing={CMTimeMake(1,30),CMTimeMake([frame[@"pts_value"]longLongValue],
            [frame[@"pts_scale"]intValue]),kCMTimeInvalid};size_t size=data.length;
        if(!status)status=CMSampleBufferCreateReady(kCFAllocatorDefault,block,format,1,1,&timing,1,&size,&sample);
        if(block)CFRelease(block);
        if(status||!sample){CFRelease(format);return nil;}
        samples.samples.push_back(sample);
    }
    CFRelease(format);if(samples.samples.size()!=6)return nil;
    Decoded decoded{};decoded.width=320;decoded.height=240;
    NSDictionary *attempt=decode(samples,mode,decoded);
    uint64_t checked=0,different=0;unsigned missing=0;NSMutableArray *files=[NSMutableArray array];
    for(const auto &frame:decoded.frames) {
        NSString *reference=[NSString stringWithFormat:@"cpu-frame-%03lld.nv12",(long long)frame.first];
        NSData *expected=[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:reference]];
        if(expected.length!=frame.second.size()){missing++;continue;}
        const uint8_t *bytes=(const uint8_t *)expected.bytes;
        for(size_t i=0;i<frame.second.size();i++){checked++;different+=bytes[i]!=frame.second[i];}
        NSString *name=[NSString stringWithFormat:@"vt-frame-%03lld.nv12",(long long)frame.first];
        if(![[NSData dataWithBytes:frame.second.data()length:frame.second.size()]writeToFile:
             [out stringByAppendingPathComponent:name]options:0 error:nil])return nil;
        [files addObject:name];
    }
    return @{@"api":@"VideoToolbox",@"mode":mode,@"format_create_status":@(formatStatus),
        @"fixture_samples":@(samples.samples.size()),@"decode":attempt,@"output_frames":@(decoded.frames.size()),
        @"CPU_reference_bytes_compared":@(checked),@"different_bytes":@(different),@"missing_CPU_references":@(missing),
        @"frame_files":files,@"system_modified":@NO,@"performance_benchmark":@NO,
        @"hardware_video_execution_proved":@NO};
}
