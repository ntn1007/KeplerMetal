// SPDX-License-Identifier: MIT
#include "video_dependency.h"
#include <cstring>
extern "C" void KPVideoImagesStart();
extern "C" NSDictionary *KPVideoImagesSnapshot();
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=4||strcmp(argv[3],"inspect"))return 1;KPVideoImagesStart();NSDictionary *before=KPVideoImagesSnapshot();
    NSDictionary *result=KPVideoDependencyInspect(@(argv[1]));NSDictionary *after=KPVideoImagesSnapshot();
    NSData *images=[NSJSONSerialization dataWithJSONObject:@{@"before":before,@"after":after}
        options:NSJSONWritingPrettyPrinted error:nil];
    [images writeToFile:[@(argv[2])stringByAppendingPathComponent:@"images.json"]options:0 error:nil];
    NSData *data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    [data writeToFile:[@(argv[2])stringByAppendingPathComponent:@"dependency.json"]options:0 error:nil];
    fwrite(data.bytes,1,data.length,stdout);puts("");
    return [result[@"public_query_controls_valid"]boolValue]&&[result[@"status"]isEqual:@"COMPLETE"]?0:2;
}}
