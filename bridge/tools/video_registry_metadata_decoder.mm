// SPDX-License-Identifier: MIT
// Reuse the qualified host/private-entry library; add a public CF metadata view.
#define KPRegistryPublicDecode KPRegistryUnobservedDecode
#include "video_registry_decoder.mm"
#undef KPRegistryPublicDecode
#include "video_registry_observer.h"
#include "video_registry_metadata.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
static NSString *metadataHash(NSData *data){
    if(!data)return @"";unsigned char bytes[32];CC_SHA256(data.bytes,(CC_LONG)data.length,bytes);
    NSMutableString *s=[NSMutableString string];for(auto b:bytes)[s appendFormat:@"%02x",b];return s;
}
extern "C" NSDictionary *KPRegistryPublicDecode(NSString *folder,NSString *mode,NSString *out){
    NSString *assets=folder.stringByDeletingLastPathComponent.stringByDeletingLastPathComponent;
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"registry-config.json"]]options:0 error:nil];
    Dl_info library{};if(!config||!dladdr((void*)KPRegistryMetadataBegin,&library)||!library.dli_fname||
        ![metadataHash([NSData dataWithContentsOfFile:@(library.dli_fname)])isEqual:config[@"metadata_library_SHA256"]])return nil;
    // The unchanged host has already checked the original six resident functions.
    // Both field-copy functions are 45 bytes; their CFRetain returns are at +27.
    if(!KPRegistryMetadataBegin((uintptr_t)KPRegistryOriginal(1)+27,(uintptr_t)KPRegistryOriginal(3)+27))return nil;
    CFMutableDictionaryRef object=CFDictionaryCreateMutable(kCFAllocatorDefault,0,
        &kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    if(!object)return nil;CFDictionarySetValue(object,CFSTR("KeplerMetal retain control"),kCFBooleanTrue);
    KPRegistryMetadataControl(true);CFTypeRef held=CFRetain(object);KPRegistryMetadataControl(false);
    bool control=held==object;CFRelease(object);
    control=control&&CFDictionaryGetValue((CFDictionaryRef)held,CFSTR("KeplerMetal retain control"))==kCFBooleanTrue;
    CFRelease(held);
    NSDictionary *decoded=control?KPRegistryUnobservedDecode(folder,mode,out):nil;
    NSMutableDictionary *metadata=[NSMutableDictionary dictionaryWithDictionary:KPRegistryMetadataSnapshot()];
    metadata[@"public_retain_control_valid"]=@(control);
    NSData *data=[NSJSONSerialization dataWithJSONObject:metadata options:NSJSONWritingPrettyPrinted error:nil];
    if(![data writeToFile:[out stringByAppendingPathComponent:@"metadata.json"]options:0 error:nil])return nil;
    if(![metadata[@"status"]isEqual:@"COMPLETE"])return nil;
    return decoded;
}
