// SPDX-License-Identifier: MIT
// Public VideoToolbox decode, including a recorded failed hardware create.
#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreVideo/CoreVideo.h>
#import <Metal/Metal.h>
#import <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <map>
#include <mutex>
#include <vector>

static void need(bool v,NSString* why) { if(!v) @throw [NSException exceptionWithName:@"VideoProbe" reason:why userInfo:nil]; }
static uint32_t property(io_registry_entry_t e,CFStringRef k) {
    CFTypeRef x=IORegistryEntryCreateCFProperty(e,k,kCFAllocatorDefault,0); uint32_t n=0;
    if(x&&CFGetTypeID(x)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)x)==4) {
        const UInt8*p=CFDataGetBytePtr((CFDataRef)x); n=p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;
    }
    if(x)CFRelease(x); return n;
}
static bool ancestor(io_registry_entry_t e,uint64_t* id) {
    if(!e||IOObjectRetain(e)!=KERN_SUCCESS)return false; io_registry_entry_t cur=e; bool found=false;
    for(unsigned k=0;k<32&&cur;k++) {
        if(IOObjectConformsTo(cur,"IOPCIDevice")) { uint64_t rid=0;
            found=property(cur,CFSTR("vendor-id"))==0x10de&&property(cur,CFSTR("device-id"))==0x1198&&
                IORegistryEntryGetRegistryEntryID(cur,&rid)==KERN_SUCCESS&&rid; if(found)*id=rid; break; }
        io_registry_entry_t p=0; kern_return_t st=IORegistryEntryGetParentEntry(cur,kIOServicePlane,&p);
        IOObjectRelease(cur); cur=0; if(st!=KERN_SUCCESS)break; cur=p;
    }
    if(cur)IOObjectRelease(cur); return found;
}
static void target(uint64_t* rid,uint64_t* pci) {
    io_iterator_t it=0; need(IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("nvAccelerator"),&it)==KERN_SUCCESS&&it,@"inventory");
    unsigned matches=0; io_service_t s=0;
    while((s=IOIteratorNext(it))) { uint64_t id=0,p=0;
        if(ancestor(s,&p)&&IORegistryEntryGetRegistryEntryID(s,&id)==KERN_SUCCESS&&id) { *rid=id; *pci=p; matches++; }
        IOObjectRelease(s);
    }
    IOObjectRelease(it); need(matches==1,@"ambiguous NVIDIA target");
}
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
    need(argc==4,@"fixture output hardware|software|metal"); NSString* mode=@(argv[3]);
    need([@[@"hardware",@"software",@"metal"] containsObject:mode],@"mode"); uint64_t rid=0,pci=0; target(&rid,&pci);
    using Begin=void(*)(uint64_t,bool); using End=void(*)(); using Results=NSDictionary*(*)();
    auto begin=reinterpret_cast<Begin>(dlsym(RTLD_DEFAULT,"KMObserveBegin"));
    auto end=reinterpret_cast<End>(dlsym(RTLD_DEFAULT,"KMObserveEnd"));
    auto results=reinterpret_cast<Results>(dlsym(RTLD_DEFAULT,"KMObserveResults"));
    need((!begin&&!end&&!results)||(begin&&end&&results),@"observer exports"); if(begin) begin(rid,false);
    NSString* dir=@(argv[1]); NSError* error=nil; NSUInteger controlCount=0,controlMatches=0,allCount=0,allMatches=0;
    auto report=[&](NSString* status,OSStatus createStatus,id hwStatus,id hwValue,NSArray* statuses,NSUInteger count,NSUInteger bytes) {
        if(end) end(); id observation=results?results():(id)[NSNull null];
        NSDictionary* result=@{@"status":status,@"mode":mode,@"create_status":@(createStatus),
            @"hardware_property_status":hwStatus,@"hardware_property":hwValue,@"decode_statuses":statuses,
            @"frames":@(count),@"bytes":@(bytes),@"observer_loaded":@(begin!=nullptr),@"observation":observation,
            @"unique_nvidia_pci_target":@YES,@"explicit_gpu_dispatches":@0,@"control_enum_count":@(controlCount),@"control_enum_pci_matches":@(controlMatches),@"control_all_count":@(allCount),@"control_all_pci_matches":@(allMatches)};
        NSData* j=[NSJSONSerialization dataWithJSONObject:result options:0 error:&error]; need(j!=nil,@"JSON");
        fwrite(j.bytes,1,j.length,stdout); putchar('\n');
    };
    if([mode isEqual:@"metal"]) {
        id<NSObject> observer=nil; NSArray<id<MTLDevice>>* devices=MTLCopyAllDevicesWithObserver(&observer,^(id<MTLDevice>,MTLDeviceNotificationName){});
        need(devices&&observer, @"Metal enumeration"); controlCount=devices.count;
        for(id<MTLDevice> d in devices) { io_service_t service=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(d.registryID));
            uint64_t candidate=0; if(service&&ancestor(service,&candidate)&&candidate==pci)controlMatches++; if(service)IOObjectRelease(service); }
        MTLRemoveDeviceObserver(observer); need(controlCount==1&&controlMatches==1,@"Metal enumeration target");
        NSArray<id<MTLDevice>>* all=MTLCopyAllDevices(); need(all, @"Metal all devices"); allCount=all.count;
        for(id<MTLDevice> d in all) { io_service_t service=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(d.registryID));
            uint64_t candidate=0; if(service&&ancestor(service,&candidate)&&candidate==pci)allMatches++; if(service)IOObjectRelease(service); }
        need(allCount==1&&allMatches==1,@"Metal all devices target");
        id<MTLDevice> device=MTLCreateSystemDefaultDevice(); need(device!=nil,@"Metal device");
        io_service_t s=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(device.registryID));
        uint64_t targetPCI=0; bool same=s&&ancestor(s,&targetPCI)&&targetPCI==pci; if(s)IOObjectRelease(s); need(same,@"Metal PCI mismatch");
        id<MTLBuffer> buffer=[device newBufferWithLength:4096 options:MTLResourceStorageModeShared];
        need(buffer&&buffer.contents&&buffer.length==4096,@"Metal buffer"); auto* p=static_cast<uint8_t*>(buffer.contents); bool ok=true;
        for(unsigned i=0;i<4096;i++)p[i]=uint8_t(i*13+7); for(unsigned i=0;i<4096;i++)if(p[i]!=uint8_t(i*13+7))ok=false;
        need(ok,@"Metal buffer contents"); report(@"METAL_PASS",0,[NSNull null],[NSNull null],@[],0,0); return 0;
    }
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
    const OSStatus createStatus=st;
    if(st!=0 || !session) {
        if(session) { VTDecompressionSessionInvalidate(session); CFRelease(session); }
        CFRelease(format);
        report(@"CREATE_FAILED",createStatus,[NSNull null],[NSNull null],@[],0,0); return 0;
    }
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
    report(@"PASS",createStatus,@(hwStatus),hwValue,statuses,decoded.images.size(),image.length); return 0;
 } @catch(NSException* e) { fprintf(stderr,"%s: %s\n",e.name.UTF8String,e.reason.UTF8String); return 1; } } }
