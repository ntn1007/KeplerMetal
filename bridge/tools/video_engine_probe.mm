// Public VideoToolbox qualification only. No driver or machine configuration writes.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <VideoToolbox/VideoToolbox.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <mutex>
#include <vector>
#include <chrono>
#include <dlfcn.h>
#include <mach-o/dyld.h>

static id jsonSafe(id value) {
 if(!value)return [NSNull null];
 if([value isKindOfClass:[NSString class]]||[value isKindOfClass:[NSNumber class]]||[value isKindOfClass:[NSNull class]])return value;
 if([value isKindOfClass:[NSData class]])return [value base64EncodedStringWithOptions:0];
 if([value isKindOfClass:[NSArray class]]){NSMutableArray *r=[NSMutableArray array];for(id v in value)[r addObject:jsonSafe(v)];return r;}
 if([value isKindOfClass:[NSDictionary class]]){NSMutableDictionary *r=[NSMutableDictionary dictionary];for(id k in value)r[[k description]]=jsonSafe(value[k]);return r;}
 return [value description];
}
static NSDictionary *property(VTSessionRef session,CFStringRef key) {
 CFTypeRef value=nullptr;OSStatus status=VTSessionCopyProperty(session,key,kCFAllocatorDefault,&value);
 id safe=jsonSafe((id)value);NSDictionary *result=@{@"status":@(status),@"value":safe};if(value)CFRelease(value);return result;
}
static void emit(id value){NSData *data=[NSJSONSerialization dataWithJSONObject:jsonSafe(value) options:NSJSONWritingPrettyPrinted error:nil];if(data)fwrite(data.bytes,1,data.length,stdout);puts("");}
static double ms(std::chrono::steady_clock::time_point start){return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();}

struct Encoded {
 std::mutex lock;std::vector<CMSampleBufferRef> samples;std::vector<OSStatus> errors;
 ~Encoded(){for(auto s:samples)CFRelease(s);}
};
static void encodedCallback(void *context,void *,OSStatus status,VTEncodeInfoFlags flags,CMSampleBufferRef sample){
 auto *c=(Encoded*)context;std::lock_guard<std::mutex>guard(c->lock);
 if(status||!sample||!CMSampleBufferDataIsReady(sample)){c->errors.push_back(status?status:-1);return;}
 if(flags&kVTEncodeInfo_FrameDropped){c->errors.push_back(-2);return;}
 CFRetain(sample);c->samples.push_back(sample);
}
static CVPixelBufferRef input(unsigned width,unsigned height,unsigned frame){
 CVPixelBufferRef pixel=nullptr;NSDictionary *attributes=@{(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
 if(CVPixelBufferCreate(kCFAllocatorDefault,width,height,kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,(CFDictionaryRef)attributes,&pixel))return nullptr;
 if(CVPixelBufferLockBaseAddress(pixel,0)){CFRelease(pixel);return nullptr;}
 for(size_t plane=0;plane<2;plane++){
  auto *p=(uint8_t*)CVPixelBufferGetBaseAddressOfPlane(pixel,plane);size_t pitch=CVPixelBufferGetBytesPerRowOfPlane(pixel,plane);
  size_t rows=CVPixelBufferGetHeightOfPlane(pixel,plane);memset(p,0,pitch*rows);
  for(unsigned y=0;y<rows;y++)for(unsigned x=0;x<width;x++)p[y*pitch+x]=plane?(uint8_t)(80+(x*3+y*5+frame*7)%96):(uint8_t)(16+(x+y*2+frame*11)%220);
 }
 CVPixelBufferUnlockBaseAddress(pixel,0);return pixel;
}
static NSDictionary *encode(unsigned width,unsigned height,unsigned count,NSString *mode,uint64_t registry,Encoded &output){
 bool cpu=[mode isEqualToString:@"cpu"],gpu=[mode isEqualToString:@"hardware-gpu"];
 NSMutableDictionary *spec=[NSMutableDictionary dictionary];
 spec[(id)(cpu?kVTVideoEncoderSpecification_EnableHardwareAcceleratedVideoEncoder:kVTVideoEncoderSpecification_RequireHardwareAcceleratedVideoEncoder)]=@(!cpu);
 if(gpu)spec[(id)kVTVideoEncoderSpecification_RequiredEncoderGPURegistryID]=@(registry);
 NSDictionary *attributes=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
 VTCompressionSessionRef session=nullptr;OSStatus status=VTCompressionSessionCreate(kCFAllocatorDefault,width,height,kCMVideoCodecType_H264,(CFDictionaryRef)spec,(CFDictionaryRef)attributes,nullptr,encodedCallback,&output,&session);
 NSMutableDictionary *result=[NSMutableDictionary dictionaryWithDictionary:@{@"mode":mode,@"create_status":@(status),@"specification":spec,@"width":@(width),@"height":@(height),@"requested_frames":@(count)}];
 if(status||!session)return result;
 NSMutableDictionary *sets=[NSMutableDictionary dictionary];
 NSDictionary *settings=@{(id)kVTCompressionPropertyKey_RealTime:@NO,(id)kVTCompressionPropertyKey_AllowFrameReordering:@NO,(id)kVTCompressionPropertyKey_ProfileLevel:(id)kVTProfileLevel_H264_Baseline_AutoLevel,(id)kVTCompressionPropertyKey_AverageBitRate:@(width*height*4),(id)kVTCompressionPropertyKey_ExpectedFrameRate:@30,(id)kVTCompressionPropertyKey_MaxKeyFrameInterval:@30};
 for(id key in settings)sets[key]=@(VTSessionSetProperty(session,(CFStringRef)key,(CFTypeRef)settings[key]));result[@"set_status"]=sets;
 result[@"prepare_status"]=@(VTCompressionSessionPrepareToEncodeFrames(session));
 auto start=std::chrono::steady_clock::now();NSMutableArray *statuses=[NSMutableArray array];
 for(unsigned frame=0;frame<count;frame++){
  CVPixelBufferRef image=input(width,height,frame);if(!image){[statuses addObject:@(-3)];break;}
  OSStatus s=VTCompressionSessionEncodeFrame(session,image,CMTimeMake(frame,30),CMTimeMake(1,30),nullptr,nullptr,nullptr);[statuses addObject:@(s)];CFRelease(image);if(s)break;
 }
 result[@"encode_status"]=statuses;result[@"complete_status"]=@(VTCompressionSessionCompleteFrames(session,kCMTimeInvalid));result[@"diagnostic_wall_ms"]=@(ms(start));
 result[@"using_hardware"]=property(session,kVTCompressionPropertyKey_UsingHardwareAcceleratedVideoEncoder);result[@"using_gpu_registry"]=property(session,kVTCompressionPropertyKey_UsingGPURegistryID);result[@"encoder_id"]=property(session,kVTCompressionPropertyKey_EncoderID);
 NSMutableArray *errors=[NSMutableArray array];for(auto e:output.errors)[errors addObject:@(e)];result[@"callback_errors"]=errors;result[@"output_frames"]=@(output.samples.size());
 VTCompressionSessionInvalidate(session);CFRelease(session);return result;
}
struct Decoded {
 std::mutex lock;std::map<int64_t,std::vector<uint8_t>> frames;std::vector<OSStatus> errors;unsigned width,height;
};
static void decodedCallback(void *context,void *,OSStatus status,VTDecodeInfoFlags flags,CVImageBufferRef image,CMTime pts,CMTime){
 auto *c=(Decoded*)context;std::lock_guard<std::mutex>guard(c->lock);
 if(status||!image||(flags&kVTDecodeInfo_FrameDropped)){c->errors.push_back(status?status:-1);return;}
 if(CVPixelBufferGetPixelFormatType(image)!=kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange||CVPixelBufferGetWidth(image)!=c->width||CVPixelBufferGetHeight(image)!=c->height||CVPixelBufferGetPlaneCount(image)!=2){c->errors.push_back(-2);return;}
 if(CVPixelBufferLockBaseAddress(image,kCVPixelBufferLock_ReadOnly)){c->errors.push_back(-3);return;}
 std::vector<uint8_t>data;data.reserve(c->width*c->height*3/2);
 for(size_t plane=0;plane<2;plane++){
  const uint8_t *p=(const uint8_t*)CVPixelBufferGetBaseAddressOfPlane(image,plane);size_t pitch=CVPixelBufferGetBytesPerRowOfPlane(image,plane);
  for(size_t y=0;y<CVPixelBufferGetHeightOfPlane(image,plane);y++)data.insert(data.end(),p+y*pitch,p+y*pitch+c->width);
 }
 CVPixelBufferUnlockBaseAddress(image,kCVPixelBufferLock_ReadOnly);int64_t frame=CMTimeConvertScale(pts,30,kCMTimeRoundingMethod_RoundHalfAwayFromZero).value;
 if(c->frames.count(frame))c->errors.push_back(-4);else c->frames[frame]=std::move(data);
}
static NSDictionary *decode(const Encoded &input,NSString *mode,Decoded &output){
 bool cpu=[mode isEqualToString:@"cpu"],hardware=[mode isEqualToString:@"hardware"];
 NSDictionary *spec=cpu?@{(id)kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder:@NO}:(hardware?@{(id)kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder:@YES}:@{(id)kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder:@YES});
 NSDictionary *attributes=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
 VTDecompressionOutputCallbackRecord callback={decodedCallback,&output};VTDecompressionSessionRef session=nullptr;
 OSStatus status=VTDecompressionSessionCreate(kCFAllocatorDefault,CMSampleBufferGetFormatDescription(input.samples.front()),(CFDictionaryRef)spec,(CFDictionaryRef)attributes,&callback,&session);
 NSMutableDictionary *result=[NSMutableDictionary dictionaryWithDictionary:@{@"mode":mode,@"create_status":@(status),@"specification":spec}];if(status||!session)return result;
 auto start=std::chrono::steady_clock::now();NSMutableArray *statuses=[NSMutableArray array];
 for(auto sample:input.samples){OSStatus s=VTDecompressionSessionDecodeFrame(session,sample,0,nullptr,nullptr);[statuses addObject:@(s)];if(s)break;}
 result[@"decode_status"]=statuses;result[@"finish_status"]=@(VTDecompressionSessionFinishDelayedFrames(session));result[@"wait_status"]=@(VTDecompressionSessionWaitForAsynchronousFrames(session));result[@"diagnostic_wall_ms"]=@(ms(start));
 result[@"using_hardware"]=property(session,kVTDecompressionPropertyKey_UsingHardwareAcceleratedVideoDecoder);result[@"using_gpu_registry"]=property(session,kVTDecompressionPropertyKey_UsingGPURegistryID);
 NSMutableArray *errors=[NSMutableArray array];for(auto e:output.errors)[errors addObject:@(e)];result[@"callback_errors"]=errors;result[@"output_frames"]=@(output.frames.size());
 VTDecompressionSessionInvalidate(session);CFRelease(session);return result;
}
static NSDictionary *comparison(const Decoded &cpu,const Decoded &other){
 unsigned missing=0;uint64_t changed=0,checked=0;unsigned maxError=0;
 for(const auto &frame:cpu.frames){auto found=other.frames.find(frame.first);if(found==other.frames.end()||found->second.size()!=frame.second.size()){missing++;continue;}
  for(size_t i=0;i<frame.second.size();i++){unsigned delta=(unsigned)std::abs(int(frame.second[i])-int(found->second[i]));changed+=delta!=0;maxError=std::max(maxError,delta);checked++;}}
 return @{@"missing_frames":@(missing),@"values_checked":@(checked),@"different_bytes":@(changed),@"maximum_byte_error":@(maxError),@"scope":@"same H264 bitstream, active NV12 plane bytes; no lossy comparison against unencoded source"};
}
static void saveFixture(const Encoded &input,NSString *folder){
 [[NSFileManager defaultManager]createDirectoryAtPath:folder withIntermediateDirectories:YES attributes:nil error:nil];NSMutableArray *frames=[NSMutableArray array];
 for(size_t i=0;i<input.samples.size();i++){
  auto sample=input.samples[i];auto block=CMSampleBufferGetDataBuffer(sample);size_t size=CMBlockBufferGetDataLength(block);NSMutableData *data=[NSMutableData dataWithLength:size];OSStatus s=CMBlockBufferCopyDataBytes(block,0,size,data.mutableBytes);
  NSString *name=[NSString stringWithFormat:@"frame-%03zu.avcc",i];if(!s)[data writeToFile:[folder stringByAppendingPathComponent:name] atomically:YES];
  CMTime time=CMSampleBufferGetPresentationTimeStamp(sample);[frames addObject:@{@"file":name,@"bytes":@(size),@"copy_status":@(s),@"pts_value":@(time.value),@"pts_scale":@(time.timescale)}];
 }
 auto format=CMSampleBufferGetFormatDescription(input.samples.front());NSMutableArray *parameters=[NSMutableArray array];size_t count=0;int length=0;
 const uint8_t *p=nullptr;size_t size=0;CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format,0,&p,&size,&count,&length);
 for(size_t i=0;i<count;i++){OSStatus s=CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format,i,&p,&size,nullptr,nullptr);if(!s)[parameters addObject:[[NSData dataWithBytes:p length:size]base64EncodedStringWithOptions:0]];}
 NSDictionary *result=@{@"frames":frames,@"H264_parameter_sets_base64":parameters,@"NAL_length_bytes":@(length),@"format_extensions":jsonSafe((id)CMFormatDescriptionGetExtensions(format))};
 NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];[json writeToFile:[folder stringByAppendingPathComponent:@"fixture.json"] atomically:YES];
}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=5)return 1;unsigned width=(unsigned)strtoul(argv[1],nullptr,10),height=(unsigned)strtoul(argv[2],nullptr,10),count=(unsigned)strtoul(argv[3],nullptr,10);if(!width||!height||width%2||height%2||width>1920||height>1080||!count||count>120)return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSMutableDictionary *result=[NSMutableDictionary dictionaryWithDictionary:@{@"device":device.name,@"registry_id":@(device.registryID),@"system_configuration_changed":@NO,@"benchmark":@NO}];
 void *preloaded=nullptr;bool preload=getenv("KEPLER_PRELOAD_VIDEO_DRIVER")!=nullptr,supplement=getenv("KEPLER_REGISTER_H264")!=nullptr;
 result[@"preload_requested"]=@(preload);result[@"supplemental_registration_requested"]=@(supplement);
 if(preload){dlerror();preloaded=dlopen("/System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver",RTLD_NOW|RTLD_LOCAL);const char *e=dlerror();result[@"preload_loaded"]=@(preloaded!=nullptr);result[@"preload_error"]=e?@(e):@"";}
 if(supplement)VTRegisterSupplementalVideoDecoderIfAvailable(kCMVideoCodecType_H264);
 result[@"hardware_decode_supported_h264"]=@(VTIsHardwareDecodeSupported(kCMVideoCodecType_H264));result[@"hardware_decode_supported_hevc"]=@(VTIsHardwareDecodeSupported(kCMVideoCodecType_HEVC));
 CFArrayRef list=nullptr;result[@"encoder_list_status"]=@(VTCopyVideoEncoderList(nullptr,&list));result[@"registered_encoders"]=jsonSafe((id)list);if(list)CFRelease(list);
 Encoded software,hw,gpu;result[@"encode_cpu"]=encode(width,height,count,@"cpu",device.registryID,software);result[@"encode_hardware"]=encode(width,height,count,@"hardware",device.registryID,hw);result[@"encode_hardware_gpu"]=encode(width,height,count,@"hardware-gpu",device.registryID,gpu);
 if(software.samples.empty()){result[@"error"]=@"CPU fixture unavailable";emit(result);return 3;}saveFixture(software,@(argv[4]));
 Decoded cpu{},hardware{},automatic{};cpu.width=hardware.width=automatic.width=width;cpu.height=hardware.height=automatic.height=height;
 result[@"decode_cpu"]=decode(software,@"cpu",cpu);result[@"decode_hardware"]=decode(software,@"hardware",hardware);result[@"decode_auto"]=decode(software,@"auto",automatic);
 result[@"hardware_decode_comparison"]=comparison(cpu,hardware);result[@"auto_decode_comparison"]=comparison(cpu,automatic);
 for(const auto &frame:cpu.frames){NSString *name=[NSString stringWithFormat:@"cpu-frame-%03lld.nv12",(long long)frame.first];[[NSData dataWithBytes:frame.second.data() length:frame.second.size()]writeToFile:[@(argv[4]) stringByAppendingPathComponent:name] atomically:YES];}
 bool cpuValid=software.samples.size()==count&&software.errors.empty()&&cpu.frames.size()==count&&cpu.errors.empty();result[@"CPU_control_valid"]=@(cpuValid);
 result[@"hardware_decode_frames_produced"]=@(hardware.frames.size()==count&&hardware.errors.empty());result[@"scope"]=@"Public hardware-only H264 sessions; using_hardware flag checked separately from session creation; internal decoder GPU identity requires further evidence if registry property is null";
 NSMutableArray *images=[NSMutableArray array];for(uint32_t i=0;i<_dyld_image_count();i++){const char *name=_dyld_get_image_name(i);if(strstr(name,"GVA")||strstr(name,"GeForceVA")||strstr(name,"AppleH264")||strstr(name,"VideoToolbox"))[images addObject:@(name)];}
 result[@"loaded_video_images_not_execution_proof"]=images;
 emit(result);if(preloaded)dlclose(preloaded);return cpuValid?0:10;
}}
