// SPDX-License-Identifier: MIT
// Original public MPEG2 sample adapter, sharing the unchanged callback/oracle.
#define main KPUnusedOriginalVTMain
#include "video_engine_probe.mm"
#undef main
#include <CommonCrypto/CommonDigest.h>

static NSString *mpeg2Hash(NSData *data){
    unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);NSMutableString *s=[NSMutableString string];
    for(auto b:h)[s appendFormat:@"%02x",b];return s;
}
extern "C" NSDictionary *KPVideoMPEG2FixtureDecode(NSString *folder,NSString *mode,NSString *out){
    NSDictionary *fixture=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [folder stringByAppendingPathComponent:@"fixture.json"]]options:0 error:nil];
    if(![fixture[@"codec"]isEqual:@"MPEG2Video"]||[fixture[@"width"]intValue]!=320||
        [fixture[@"height"]intValue]!=240||[fixture[@"frames"]count]!=6||
        ![@[@"cpu",@"hardware"]containsObject:mode])return nil;
    CMVideoFormatDescriptionRef format=nullptr;
    OSStatus formatStatus=CMVideoFormatDescriptionCreate(kCFAllocatorDefault,kCMVideoCodecType_MPEG2Video,
        320,240,nullptr,&format);if(formatStatus||!format)return nil;
    Encoded samples;
    for(NSDictionary *frame in fixture[@"frames"]){
        NSString *name=frame[@"file"];if(![name isEqual:name.lastPathComponent]){CFRelease(format);return nil;}
        NSData *data=[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:name]];
        if(!data.length||data.length!=[frame[@"bytes"]unsignedLongLongValue]||
            ![mpeg2Hash(data)isEqual:frame[@"SHA256"]]){CFRelease(format);return nil;}
        CMBlockBufferRef block=nullptr;CMSampleBufferRef sample=nullptr;
        OSStatus status=CMBlockBufferCreateWithMemoryBlock(kCFAllocatorDefault,nullptr,data.length,
            kCFAllocatorDefault,nullptr,0,data.length,0,&block);
        if(!status)status=CMBlockBufferReplaceDataBytes(data.bytes,block,0,data.length);
        CMSampleTimingInfo timing={CMTimeMake(1,30),CMTimeMake([frame[@"pts_value"]longLongValue],
            [frame[@"pts_scale"]intValue]),kCMTimeInvalid};size_t bytes=data.length;
        if(!status)status=CMSampleBufferCreateReady(kCFAllocatorDefault,block,format,1,1,&timing,1,&bytes,&sample);
        if(block)CFRelease(block);if(status||!sample){CFRelease(format);return nil;}samples.samples.push_back(sample);
    }
    CFRelease(format);Decoded decoded{};decoded.width=320;decoded.height=240;
    NSDictionary *attempt=decode(samples,mode,decoded);
    uint64_t checked=0,different=0;unsigned missing=0,maximumError=0;NSMutableArray *files=[NSMutableArray array];
    for(const auto &frame:decoded.frames){
        NSString *reference=[NSString stringWithFormat:@"cpu-frame-%03lld.nv12",(long long)frame.first];
        NSData *expected=[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:reference]];
        if(expected.length!=frame.second.size()){missing++;continue;}
        const uint8_t *bytes=(const uint8_t*)expected.bytes;
        for(size_t i=0;i<frame.second.size();i++){
            unsigned delta=(unsigned)std::abs(int(bytes[i])-int(frame.second[i]));
            checked++;different+=delta!=0;maximumError=std::max(maximumError,delta);
        }
        NSString *name=[NSString stringWithFormat:@"vt-frame-%03lld.nv12",(long long)frame.first];
        if(![[NSData dataWithBytes:frame.second.data()length:frame.second.size()]writeToFile:
            [out stringByAppendingPathComponent:name]options:0 error:nil])return nil;[files addObject:name];
    }
    return @{@"api":@"VideoToolbox",@"codec":@"MPEG2Video",@"mode":mode,@"format_create_status":@(formatStatus),
        @"fixture_samples":@(samples.samples.size()),@"decode":attempt,@"output_frames":@(decoded.frames.size()),
        @"CPU_reference_bytes_compared":@(checked),@"different_bytes":@(different),@"maximum_byte_error":@(maximumError),
        @"missing_CPU_references":@(missing),@"frame_files":files,@"system_modified":@NO,
        @"performance_benchmark":@NO,@"hardware_video_execution_proved":@NO};
}
