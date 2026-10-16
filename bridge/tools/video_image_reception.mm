// SPDX-License-Identifier: MIT
#define main KPVideoBaseMain
#include "video_va_reception.mm"
#undef main

extern "C" void KPVideoImagesStart();
extern "C" NSDictionary *KPVideoImagesSnapshot();
extern "C" NSArray *KPVideoExistingGVASymbols();

int main(int argc,char **argv) {@autoreleasepool {
    if(argc!=4)return 1;
    NSString *assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
    KPVideoImagesStart();NSDictionary *before=KPVideoImagesSnapshot();
    NSDictionary *loaded=nil,*unloaded=nil;NSArray *lookupsBefore=KPVideoExistingGVASymbols();
    int code=0;bool calibration=[mode isEqual:@"catalog"];
    uint32_t value=0;int closeStatus=0;
    if(calibration) {
        NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
            [assets stringByAppendingPathComponent:@"image-config.json"]]options:0 error:nil];
        NSString *path=config[@"calibration_library"];
        if(!path||![hash([NSData dataWithContentsOfFile:path])isEqual:config[@"calibration_SHA256"]])return 20;
        void *library=dlopen(path.fileSystemRepresentation,RTLD_NOW|RTLD_LOCAL);if(!library)return 21;
        auto function=(uint32_t(*)())dlsym(library,"KPVideoImageFixtureValue");
        if(!function){dlclose(library);return 22;}value=function();loaded=KPVideoImagesSnapshot();
        closeStatus=dlclose(library);unloaded=KPVideoImagesSnapshot();
        if(value!=37||closeStatus)code=23;
    } else code=KPVideoBaseMain(argc,argv);
    NSDictionary *after=KPVideoImagesSnapshot();NSArray *lookupsAfter=KPVideoExistingGVASymbols();
    NSDictionary *final=KPVideoImagesSnapshot();
    NSDictionary *result=@{@"mode":mode,@"base_exit_code":@(code),@"before":before,@"after":after,@"final":final,
        @"calibration":@{@"enabled":@(calibration),@"value":@(value),@"dlclose_status":@(closeStatus),
            @"loaded":loaded?:@{},@"unloaded":unloaded?:@{}},
        @"existing_GVA_symbols_before":lookupsBefore,@"existing_GVA_symbols_after":lookupsAfter,
        @"private_vendor_function_invoked":@NO,@"system_modified":@NO,@"performance_benchmark":@NO};
    NSData *data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    if(![data writeToFile:[out stringByAppendingPathComponent:@"images.json"]options:0 error:nil])return 24;
    if(calibration){fwrite(data.bytes,1,data.length,stdout);puts("");}
    return code;
}}
