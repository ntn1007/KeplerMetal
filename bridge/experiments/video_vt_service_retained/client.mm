// SPDX-License-Identifier: MIT
// Public VideoToolbox decode, including a recorded failed hardware create.
#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreVideo/CoreVideo.h>
#import <Metal/Metal.h>
#import <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <map>
#include <mutex>
#include <vector>

extern "C" __attribute__((noinline,used)) void KMTraceReady(unsigned long x,unsigned long registry,unsigned long held) { __asm__ volatile("" : : "r"(x),"r"(registry),"r"(held) : "memory"); }
static void need(bool v,NSString* why) { if(!v) @throw [NSException exceptionWithName:@"VideoProbe" reason:why userInfo:nil]; }
static bool readSelf(uintptr_t address,void* out,size_t n) { mach_vm_size_t got=0; return mach_vm_read_overwrite(mach_task_self(),address,n,(mach_vm_address_t)out,&got)==KERN_SUCCESS&&got==n; }
static bool digestEquals(const void* data,size_t n,const char* expected) { unsigned char hash[32];CC_SHA256(data,(CC_LONG)n,hash);char text[65]{};const char* digits="0123456789abcdef";for(unsigned j=0;j<32;j++){text[2*j]=digits[hash[j]>>4];text[2*j+1]=digits[hash[j]&15];}return !strcmp(text,expected); }
static NSDictionary* binding() {
 void* symbol=dlsym(RTLD_DEFAULT,"VTDecompressionSessionCreate"); Dl_info i{},resolved{}; uint8_t call[5]{},stub[6]{}; uintptr_t target=0; bool valid=false;
 if(symbol&&dladdr(symbol,&i)&&i.dli_fname&&i.dli_fbase&&!strcmp(i.dli_fname,"/System/Library/Frameworks/VideoToolbox.framework/Versions/A/VideoToolbox")) {
  uintptr_t base=(uintptr_t)i.dli_fbase,site=base+0x5fd9f6;
  if(readSelf(site,call,sizeof call)&&digestEquals(call,sizeof call,"e1de6abe986d7f5ca399bde2ec59409682315cb37625f26f61d69b611cf62a69")) {
   int32_t displacement=0;memcpy(&displacement,call+1,4);uintptr_t stubAddress=site+5+(intptr_t)displacement;
   if(stubAddress==base+0x6477f6 && readSelf(stubAddress,stub,sizeof stub)&&digestEquals(stub,sizeof stub,"211bdecea0e069e89a2565ce2149522c4f4ced1ed3ffddf1ccc52d1a8f5a339e")) {
    memcpy(&displacement,stub+2,4);uintptr_t slot=stubAddress+6+(intptr_t)displacement;
    valid=slot==base+0x2a69ba30 && readSelf(slot,&target,sizeof target) && target && dladdr((void*)target,&resolved) && resolved.dli_fbase && resolved.dli_fname;
   }
  }
 }
 if(!valid)return @{@"valid":@NO}; const char*name=strrchr(resolved.dli_fname,'/');name=name?name+1:resolved.dli_fname;
 return @{@"valid":@YES,@"target_image":@(name),@"target_offset":@(target-(uintptr_t)resolved.dli_fbase),@"target_symbol":@(resolved.dli_sname?:"")};
}
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
struct HeldService { io_service_t value=0; ~HeldService(){if(value)IOObjectRelease(value);} };
static void target(uint64_t* rid,uint64_t* pci,io_service_t* held) {
    io_iterator_t it=0; need(IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("nvAccelerator"),&it)==KERN_SUCCESS&&it,@"inventory");
    unsigned matches=0; io_service_t s=0;
    while((s=IOIteratorNext(it))) { uint64_t id=0,p=0;
        if(ancestor(s,&p)&&IORegistryEntryGetRegistryEntryID(s,&id)==KERN_SUCCESS&&id) { if(*held){IOObjectRelease(*held);*held=0;} need(IOObjectRetain(s)==KERN_SUCCESS,@"service retain"); *held=s; *rid=id; *pci=p; matches++; }
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
    need([@[@"hardware",@"software",@"metal"] containsObject:mode],@"mode"); uint64_t rid=0,pci=0; HeldService service; target(&rid,&pci,&service.value); uint64_t heldId=0; need(service.value&&IORegistryEntryGetRegistryEntryID(service.value,&heldId)==KERN_SUCCESS&&heldId==rid,@"retained service identity");
    using Begin=void(*)(uint64_t,bool); using End=void(*)(); using Results=NSDictionary*(*)();
    auto begin=reinterpret_cast<Begin>(dlsym(RTLD_DEFAULT,"KMObserveBegin"));
    auto end=reinterpret_cast<End>(dlsym(RTLD_DEFAULT,"KMObserveEnd"));
    auto results=reinterpret_cast<Results>(dlsym(RTLD_DEFAULT,"KMObserveResults"));
    NSDictionary* before=binding();
    need((!begin&&!end&&!results)||(begin&&end&&results),@"observer exports"); if(begin) begin(rid,false);
    NSString* dir=@(argv[1]); NSError* error=nil; NSUInteger controlCount=0,controlMatches=0,allCount=0,allMatches=0;
    auto report=[&](NSString* status,OSStatus createStatus,id hwStatus,id hwValue,NSArray* statuses,NSUInteger count,NSUInteger bytes) {
        if(end) end(); id observation=results?results():(id)[NSNull null];
        NSDictionary* result=@{@"status":status,@"mode":mode,@"create_status":@(createStatus),
            @"hardware_property_status":hwStatus,@"hardware_property":hwValue,@"decode_statuses":statuses,
            @"frames":@(count),@"bytes":@(bytes),@"observer_loaded":@(begin!=nullptr),@"observation":observation,
            @"binding_before":before,@"binding_after":binding(),@"unique_nvidia_pci_target":@YES,@"retained_target_service_verified":@YES,@"explicit_gpu_dispatches":@0,@"control_enum_count":@(controlCount),@"control_enum_pci_matches":@(controlMatches),@"control_all_count":@(allCount),@"control_all_pci_matches":@(allMatches)};
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
    VTDecompressionSessionRef session=nullptr; KMTraceReady(0xabc0,rid,service.value); st=VTDecompressionSessionCreate(kCFAllocatorDefault,format,(__bridge CFDictionaryRef)spec,(__bridge CFDictionaryRef)attrs,&cb,&session);
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
