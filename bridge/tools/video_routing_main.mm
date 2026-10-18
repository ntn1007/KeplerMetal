// SPDX-License-Identifier: MIT
#include "video_routing.h"
int KPRegistryQualifiedMain(int,char **);
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=4)return 1;
    if(!KPVideoRoutingBegin(@(argv[1]))){puts("{\"status\":\"ROUTING_PREFLIGHT_FAILED\"}");return 2;}
    int status=KPRegistryQualifiedMain(argc,argv);
    NSDictionary *result=KPVideoRoutingSnapshot();
    NSData *data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    if(![data writeToFile:[@(argv[2])stringByAppendingPathComponent:@"routing.json"]options:0 error:nil])return 3;
    return status?status:([result[@"status"]isEqual:@"COMPLETE"]?0:4);
}}
