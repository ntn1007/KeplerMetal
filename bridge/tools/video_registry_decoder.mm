// SPDX-License-Identifier: MIT
#if KPREG_MPEG2
#include "video_mpeg2_vt_client.mm"
extern "C" const char *KPRegistryCodecName(){return "MPEG2Video";}
extern "C" NSDictionary *KPRegistryPublicDecode(NSString *f,NSString *m,NSString *o){
    return KPVideoMPEG2FixtureDecode(f,m,o);
}
#else
#include "video_va_vt_client.mm"
extern "C" const char *KPRegistryCodecName(){return "H264";}
extern "C" NSDictionary *KPRegistryPublicDecode(NSString *f,NSString *m,NSString *o){
    return KPVideoVTFixtureDecode(f,m,o);
}
#endif
