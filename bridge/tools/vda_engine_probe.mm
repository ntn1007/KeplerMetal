// Legacy public VDA path, with the same valid AVCC and software reference frames.
#import <Foundation/Foundation.h>
#import <VideoDecodeAcceleration/VDADecoder.h>
#include <cstdio>
#include <map>
#include <mutex>
#include <vector>
#include <algorithm>
#include <cstring>
struct Output {
 std::mutex lock;std::map<unsigned,CVPixelBufferRef> frames;std::vector<OSStatus> errors;
 ~Output(){for(auto &frame:frames)CFRelease(frame.second);}
};
static void callback(void *context,CFDictionaryRef info,OSStatus status,uint32_t flags,CVImageBufferRef image){
 Output *output=(Output*)context;std::lock_guard<std::mutex>guard(output->lock);
 if(status||!image||(flags&2)){output->errors.push_back(status?status:-1);return;}
 NSNumber *index=((NSDictionary*)info)[@"frame"];
 if(!index||output->frames.count(index.unsignedIntValue)){output->errors.push_back(-2);return;}
 CFRetain(image);output->frames[index.unsignedIntValue]=image;
}
static void emit(NSDictionary *value){NSData *json=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=5)return 1;NSString *folder=@(argv[1]);unsigned width=(unsigned)strtoul(argv[2],nullptr,10),height=(unsigned)strtoul(argv[3],nullptr,10);bool native=!strcmp(argv[4],"default");if(!native&&strcmp(argv[4],"nv12"))return 1;
 NSDictionary *fixture=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:@"fixture.json"]] options:0 error:nil];
 NSData *avcc=[[NSData alloc]initWithBase64EncodedString:fixture[@"format_extensions"][@"SampleDescriptionExtensionAtoms"][@"avcC"] options:0];if(!avcc.length||!width||!height)return 2;
 NSDictionary *config=@{(id)kVDADecoderConfiguration_Width:@(width),(id)kVDADecoderConfiguration_Height:@(height),(id)kVDADecoderConfiguration_SourceFormat:@((int32_t)0x61766331),(id)kVDADecoderConfiguration_avcCData:avcc};
 NSDictionary *attributes=native?nil:@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
 Output output;VDADecoder decoder=nullptr;
 // TN2267 Listing1 passes the callback address with this SDK's historical cast.
 OSStatus status=VDADecoderCreate((CFDictionaryRef)config,(CFDictionaryRef)attributes,(VDADecoderOutputCallback*)callback,&output,&decoder);
 NSMutableDictionary *result=[NSMutableDictionary dictionaryWithDictionary:@{@"api":@"VDA",@"destination":@(argv[4]),@"width":@(width),@"height":@(height),@"create_status":@(status),@"avcc_bytes":@(avcc.length),@"system_configuration_changed":@NO,@"benchmark":@NO}];
 if(status||!decoder){result[@"hardware_frames_produced"]=@NO;emit(result);return 0;}
 NSMutableArray *statuses=[NSMutableArray array];unsigned i=0;
 for(NSDictionary *frame in fixture[@"frames"]){NSData *data=[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:frame[@"file"]]];if(data.length!=[frame[@"bytes"]unsignedLongLongValue])return 3;
  OSStatus s=VDADecoderDecode(decoder,0,(CFDataRef)data,(CFDictionaryRef)@{@"frame":@(i++)});[statuses addObject:@(s)];if(s)break;
 }
 result[@"decode_status"]=statuses;result[@"flush_status"]=@(VDADecoderFlush(decoder,kVDADecoderFlush_EmitFrames));
 NSMutableArray *errors=[NSMutableArray array],*formats=[NSMutableArray array];for(auto s:output.errors)[errors addObject:@(s)];
 uint64_t checked=0,changed=0;unsigned maxError=0,formatBad=0,missing=0;
 for(auto &frame:output.frames){CVPixelBufferRef image=frame.second;OSType format=CVPixelBufferGetPixelFormatType(image);[formats addObject:@(format)];
  if(format!=kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange||CVPixelBufferGetWidth(image)!=width||CVPixelBufferGetHeight(image)!=height||CVPixelBufferGetPlaneCount(image)!=2){formatBad++;continue;}
  if(CVPixelBufferLockBaseAddress(image,kCVPixelBufferLock_ReadOnly)){formatBad++;continue;}
  std::vector<uint8_t>actual;for(size_t plane=0;plane<2;plane++){const uint8_t *p=(const uint8_t*)CVPixelBufferGetBaseAddressOfPlane(image,plane);size_t pitch=CVPixelBufferGetBytesPerRowOfPlane(image,plane);for(size_t y=0;y<CVPixelBufferGetHeightOfPlane(image,plane);y++)actual.insert(actual.end(),p+y*pitch,p+y*pitch+width);}
  CVPixelBufferUnlockBaseAddress(image,kCVPixelBufferLock_ReadOnly);
  NSString *name=[NSString stringWithFormat:@"cpu-frame-%03u.nv12",frame.first];NSData *reference=[NSData dataWithContentsOfFile:[folder stringByAppendingPathComponent:name]];
  if(reference.length!=actual.size()){missing++;continue;}const uint8_t *cpu=(const uint8_t*)reference.bytes;
  for(size_t n=0;n<actual.size();n++){unsigned delta=(unsigned)std::abs(int(actual[n])-int(cpu[n]));maxError=std::max(maxError,delta);changed+=delta!=0;checked++;}
 }
 result[@"output_frames"]=@(output.frames.size());result[@"callback_errors"]=errors;result[@"pixel_formats"]=formats;result[@"unsupported_output_formats"]=@(formatBad);result[@"missing_CPU_references"]=@(missing);result[@"CPU_values_checked"]=@(checked);result[@"different_bytes"]=@(changed);result[@"maximum_byte_error"]=@(maxError);result[@"hardware_frames_produced"]=@(output.frames.size()==[fixture[@"frames"]count]&&output.errors.empty());result[@"destroy_status"]=@(VDADecoderDestroy(decoder));
 emit(result);return 0;
}}
