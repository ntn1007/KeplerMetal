// SPDX-License-Identifier: MIT
// Call the unchanged public VDA client; keep observer evidence separate.
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <cstdint>
#include <cstring>

extern "C" void KPVideoTraceConfigure(bool, bool);
extern "C" NSDictionary *KPVideoTraceSnapshot();
extern "C" NSDictionary *KPVideoVTFixtureDecode(NSString *, NSString *, NSString *);
int KPVDAMain(int, char **);

extern "C" __attribute__((used,visibility("default"))) uint64_t KPVideoSelfCreate(
    uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f,
    uint64_t g,uint64_t h,uint64_t i,uint64_t j,uint64_t k,uint64_t l) {
    return a ^ (3*b) ^ (5*c) ^ (7*d) ^ (11*e) ^ (13*f) ^ (17*g) ^ (19*h) ^ (23*i) ^ (29*j) ^ (31*k) ^ (37*l);
}
extern "C" __attribute__((used,visibility("default"))) double KPVideoSelfDestroy(
    double a,double b,double c,double d,double e,double f,double g,double h,double i,double j) {
    return a+2*b+3*c+4*d+5*e+6*f+7*g+8*h+9*i+10*j;
}
static NSString *hash(NSData *d) {
    if (!d) return @""; unsigned char bytes[32]; CC_SHA256(d.bytes, (CC_LONG)d.length, bytes);
    NSMutableString *s=[NSMutableString string]; for (auto b:bytes) [s appendFormat:@"%02x",b]; return s;
}
int main(int argc,char **argv) {@autoreleasepool {
    if (argc!=4) return 1;
    NSString *assets=@(argv[1]), *out=@(argv[2]), *mode=@(argv[3]);
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"observer-config.json"]] options:0 error:nil];
    if (!config) return 2;
    Dl_info info{}; if (!dladdr((void *)KPVideoTraceConfigure,&info) || !info.dli_fname) return 2;
    NSString *library=@(info.dli_fname);
    if (![hash([NSData dataWithContentsOfFile:library]) isEqual:config[@"observer_library_SHA256"]]) return 2;
    bool selftest=[mode isEqual:@"selftest"], vt=[mode hasPrefix:@"vt-"];
    bool active=[mode isEqual:@"observe"]||[mode isEqual:@"vt-observe"];
    if (![@[@"selftest",@"observe",@"plain",@"vt-cpu",@"vt-plain",@"vt-observe"]containsObject:mode]) return 1;
    NSString *va=@"/System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver";
    if (!selftest && ![hash([NSData dataWithContentsOfFile:va]) isEqual:
        @"2d3894048f5d61f6735955211bba28cb1e1a0ff9a7f556ebb6c144018388a865"]) return 2;
    KPVideoTraceConfigure(active||selftest,selftest);
    int code=0; unsigned integerCases=0, floatingCases=0;
    if (selftest) {
        auto a=(decltype(&KPVideoSelfCreate))dlsym(RTLD_DEFAULT,"KPVideoSelfCreate");
        auto b=(decltype(&KPVideoSelfDestroy))dlsym(RTLD_DEFAULT,"KPVideoSelfDestroy");
        if (!a||!b) return 3;
        CFBundleRef mainBundle=CFBundleGetMainBundle(); if (!mainBundle) return 3;
        CFBundleGetFunctionPointerForName(mainBundle,CFSTR("KPVideoSelfCreate"));
        for (uint64_t n=0;n<128;n++) {
            uint64_t expected=KPVideoSelfCreate(n,n+1,n+2,n+3,n+4,n+5,n+6,n+7,n+8,n+9,n+10,n+11);
            if (a(n,n+1,n+2,n+3,n+4,n+5,n+6,n+7,n+8,n+9,n+10,n+11)!=expected) return 4; integerCases++;
            double want=KPVideoSelfDestroy(n/2.,1,2,3,4,5,6,7,8,9);
            if (b(n/2.,1,2,3,4,5,6,7,8,9)!=want) return 4; floatingCases++;
        }
    } else if(vt) {
        NSDictionary *result=KPVideoVTFixtureDecode([assets stringByAppendingPathComponent:@"fixture"],
            [mode isEqual:@"vt-cpu"]?@"cpu":@"hardware",out);
        if(!result)return 7;
        NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
        fwrite(json.bytes,1,json.length,stdout);puts("");
    } else {
        NSString *fixture=[assets stringByAppendingPathComponent:@"fixture"];
        char *nativeArgs[]={argv[0],(char *)fixture.fileSystemRepresentation,(char *)"320",(char *)"240",(char *)"nv12",nullptr};
        code=KPVDAMain(5,nativeArgs);
    }
    NSDictionary *snapshot=KPVideoTraceSnapshot();
    NSDictionary *proof=@{@"mode":mode,@"VDA_exit_code":vt?(id)[NSNull null]:@(code),@"observer":snapshot,
        @"public_API":selftest?@"CPU":(vt?@"VideoToolbox":@"VDA"),
        @"integer_ABI_cases":@(integerCases),@"floating_ABI_cases":@(floatingCases),
        @"observer_library_SHA256":hash([NSData dataWithContentsOfFile:library]),
        @"system_modified":@NO,@"performance_benchmark":@NO,@"GPU_work_in_selftest":@NO};
    NSData *data=[NSJSONSerialization dataWithJSONObject:proof options:NSJSONWritingPrettyPrinted error:nil];
    if (![data writeToFile:[out stringByAppendingPathComponent:@"observer.json"] options:0 error:nil]) return 5;
    if (selftest) {
        if ([snapshot[@"create_calls"]unsignedLongLongValue]!=128 ||
            [snapshot[@"destroy_calls"]unsignedLongLongValue]!=128 || [snapshot[@"dropped"]unsignedIntValue]) return 6;
        if (![snapshot[@"bundle_calls_observed"]unsignedIntValue] ||
            [snapshot[@"dlsym_calls_observed"]unsignedIntValue]<2) return 6;
        fwrite(data.bytes,1,data.length,stdout);puts("");
    }
    return code;
}}
