// SPDX-License-Identifier: MIT
// Public VideoToolbox decode with optional process-local IOKit observation.
#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreVideo/CoreVideo.h>
#import <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <map>
#include <mutex>
#include <vector>
#include "observer.h"

static void need(bool v,NSString* why) { if(!v) @throw [NSException exceptionWithName:@"VideoProbe" reason:why userInfo:nil]; }
struct Frames {
    std::mutex mu; std::map<int64_t,CVPixelBufferRef> images; std::vector<int> errors;
    ~Frames() { for(auto& p:images) CFRelease(p.second); }
};
static void on_frame(void* ref,void*,OSStatus status,VTDecodeInfoFlags flags,CVImageBufferRef image,CMTime pts,CMTime) {
    auto* f=static_cast<Frames*>(ref); std::lock_guard<std::mutex> l(f->mu);
    const int64_t n=CMTimeConvertScale(pts,30,kCMTimeRoundingMethod_RoundHalfAwayFromZero).value;
    if(status||!image||(flags&kVTDecodeInfo_FrameDropped)||n<0||n>=6||f->images.count(n)) { f->errors.push_back(status?:-1); return; }
    CFRetain(image); f->images[n]=image;
}
static NSData* packed(CVPixelBufferRef p) {
    need(CVPixelBufferGetWidth(p)==320 && CVPixelBufferGetHeight(p)==240 &&
         CVPixelBufferGetPixelFormatType(p)==kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange &&
         CVPixelBufferGetPlaneCount(p)==2,@"pixel format");
    need(CVPixelBufferLockBaseAddress(p,kCVPixelBufferLock_ReadOnly)==kCVReturnSuccess,@"lock");
    NSMutableData* result=[NSMutableData dataWithCapacity:115200];
    for(size_t n=0;n<2;n++) {
        auto* b=static_cast<const uint8_t*>(CVPixelBufferGetBaseAddressOfPlane(p,n));
        size_t stride=CVPixelBufferGetBytesPerRowOfPlane(p,n), rows=CVPixelBufferGetHeightOfPlane(p,n);
        need(b && stride>=320 && rows==(n?120:240),@"plane");
        for(size_t y=0;y<rows;y++) [result appendBytes:b+y*stride length:320];
    }
    need(CVPixelBufferUnlockBaseAddress(p,kCVPixelBufferLock_ReadOnly)==kCVReturnSuccess && result.length==115200,@"unlock");
    return result;
}
int main(int argc,char** argv) { @autoreleasepool { @try {
    need(argc==4,@"fixture output hardware|software"); NSString* mode=@(argv[3]);
    need([mode isEqual:@"hardware"]||[mode isEqual:@"software"],@"mode");
    using Snapshot=void(*)(uint64_t*); auto snapshot=reinterpret_cast<Snapshot>(dlsym(RTLD_DEFAULT,"km_observer_snapshot"));
    using Detail=void(*)(KMDetails*); auto detail=reinterpret_cast<Detail>(dlsym(RTLD_DEFAULT,"km_observer_details"));
    KMDetails detailStart{},detailEnd{};
    uint64_t pre[772]={},start[772]={},end[772]={}; bool calibrated=false;
    if(snapshot) {
        snapshot(pre); size_t size=0;
        (void)IOConnectCallStructMethod(MACH_PORT_NULL,254,nullptr,0,nullptr,&size);
        snapshot(start); calibrated=start[2]==pre[2]+1 && start[4+256+254]==pre[4+256+254]+1;
        need(calibrated && detail,@"observer calibration"); detail(&detailStart);
    }
    NSString* dir=@(argv[1]); NSError* error=nil;
    NSDictionary* fixture=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[dir stringByAppendingPathComponent:@"fixture.json"]] options:0 error:&error];
    NSArray* sets=fixture[@"H264_parameter_sets_base64"],*frames=fixture[@"frames"];
    need(sets.count==2 && frames.count==6 && [fixture[@"NAL_length_bytes"] intValue]==4,@"fixture");
    NSData* sps=[[NSData alloc] initWithBase64EncodedString:sets[0] options:0];
    NSData* pps=[[NSData alloc] initWithBase64EncodedString:sets[1] options:0]; need(sps&&pps,@"parameter sets");
    const uint8_t* parts[]={static_cast<const uint8_t*>(sps.bytes),static_cast<const uint8_t*>(pps.bytes)};
    size_t sizes[]={sps.length,pps.length}; CMVideoFormatDescriptionRef format=nullptr;
    OSStatus st=CMVideoFormatDescriptionCreateFromH264ParameterSets(kCFAllocatorDefault,2,parts,sizes,4,&format);
    need(st==0 && format,@"format"); Frames decoded; VTDecompressionOutputCallbackRecord cb={on_frame,&decoded};
    NSDictionary* spec=[mode isEqual:@"hardware"] ? @{(__bridge id)kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder:@YES} : @{(__bridge id)kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder:@NO};
    NSDictionary* attrs=@{(__bridge id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),(__bridge id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
    VTDecompressionSessionRef session=nullptr; st=VTDecompressionSessionCreate(kCFAllocatorDefault,format,(__bridge CFDictionaryRef)spec,(__bridge CFDictionaryRef)attrs,&cb,&session);
    need(st==0 && session,[NSString stringWithFormat:@"session %d",st]);
    CFTypeRef hw=nullptr; OSStatus hwStatus=VTSessionCopyProperty(session,kVTDecompressionPropertyKey_UsingHardwareAcceleratedVideoDecoder,kCFAllocatorDefault,&hw);
    id hwValue=[NSNull null]; if(hw) { need(CFGetTypeID(hw)==CFBooleanGetTypeID(),@"hardware property type"); hwValue=@(CFBooleanGetValue((CFBooleanRef)hw)); CFRelease(hw); }
    NSMutableArray* statuses=[NSMutableArray new];
    for(NSDictionary* frame in frames) {
        NSString* name=frame[@"file"]; need([name isEqual:name.lastPathComponent],@"frame path");
        NSData* data=[NSData dataWithContentsOfFile:[dir stringByAppendingPathComponent:name]]; need(data && data.length==[frame[@"bytes"] unsignedLongLongValue],@"frame data");
        CMBlockBufferRef block=nullptr; CMSampleBufferRef sample=nullptr;
        st=CMBlockBufferCreateWithMemoryBlock(kCFAllocatorDefault,nullptr,data.length,kCFAllocatorDefault,nullptr,0,data.length,0,&block);
        if(!st) st=CMBlockBufferReplaceDataBytes(data.bytes,block,0,data.length);
        CMSampleTimingInfo timing={CMTimeMake(1,30),CMTimeMake([frame[@"pts_value"] longLongValue],[frame[@"pts_scale"] intValue]),kCMTimeInvalid};
        size_t n=data.length; if(!st) st=CMSampleBufferCreateReady(kCFAllocatorDefault,block,format,1,1,&timing,1,&n,&sample);
        if(block) CFRelease(block); need(st==0 && sample,@"sample");
        st=VTDecompressionSessionDecodeFrame(session,sample,0,nullptr,nullptr); CFRelease(sample); [statuses addObject:@(st)]; need(st==0,@"decode");
    }
    OSStatus finish=VTDecompressionSessionFinishDelayedFrames(session),wait=VTDecompressionSessionWaitForAsynchronousFrames(session);
    need(finish==0 && wait==0 && decoded.images.size()==6 && decoded.errors.empty(),@"completion");
    VTDecompressionSessionInvalidate(session); CFRelease(session); CFRelease(format);
    NSMutableData* image=[NSMutableData dataWithCapacity:691200];
    for(int i=0;i<6;i++) { auto it=decoded.images.find(i); need(it!=decoded.images.end(),@"frame missing"); [image appendData:packed(it->second)]; }
    need([image writeToURL:[NSURL fileURLWithPath:@(argv[2])] options:NSDataWritingWithoutOverwriting error:&error],@"output");
    if(snapshot) { snapshot(end); detail(&detailEnd); }
    NSMutableArray* kinds=[NSMutableArray new],*events=[NSMutableArray new];
    for(unsigned i=0;i<4;i++) [kinds addObject:@(end[i]-start[i])];
    for(unsigned kind=0;kind<3;kind++) for(unsigned n=0;n<256;n++) {
        unsigned i=4+kind*256+n; if(end[i]!=start[i]) [events addObject:@{ @"kind":@(kind+1),@"selector":@(n),@"count":@(end[i]-start[i]) }];
    }
    NSMutableArray* services=[NSMutableArray new],*detailEvents=[NSMutableArray new];
    for(uint32_t i=0;i<detailEnd.service_count;i++) {
        const auto& s=detailEnd.services[i];
        NSString* cls=[NSString stringWithUTF8String:s.class_name]?:@"";
        NSString* name=[NSString stringWithUTF8String:s.registry_name]?:@"";
        [services addObject:@{ @"class":cls,@"name":name,@"type":@(s.type) }];
    }
    for(uint32_t i=detailStart.event_count;i<detailEnd.event_count;i++) {
        const auto& e=detailEnd.events[i];
        [detailEvents addObject:@{ @"kind":@(e.kind),@"selector":@(e.selector),@"service":
            e.service==KM_UNKNOWN_SERVICE ? (id)[NSNull null] : (id)@(e.service) }];
    }
    NSDictionary* result=@{@"status":@"PASS",@"mode":mode,@"hardware_property_status":@(hwStatus),
        @"hardware_property":hwValue,@"decode_statuses":statuses,@"frames":@(decoded.images.size()),
        @"bytes":@(image.length),@"observer_loaded":@(snapshot!=nullptr),@"observer_calibrated":@(calibrated),
        @"observed_counts":kinds,@"observed_selectors":events,@"services":services,
        @"detail_events":detailEvents,@"dropped_events":@(detailEnd.dropped-detailStart.dropped)};
    NSData* j=[NSJSONSerialization dataWithJSONObject:result options:0 error:&error]; need(j!=nil,@"JSON");
    fwrite(j.bytes,1,j.length,stdout); putchar('\n'); return 0;
 } @catch(NSException* e) { fprintf(stderr,"%s: %s\n",e.name.UTF8String,e.reason.UTF8String); return 1; } } }
