// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
extern "C" bool KPVideoFactoryBegin(NSString *);
extern "C" NSDictionary *KPVideoFactorySnapshot();
int KPOwnedQualifiedMain(int,char **);
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=4||!KPVideoFactoryBegin(@(argv[1])))return 2;
    int status=KPOwnedQualifiedMain(argc,argv);
    NSDictionary *record=KPVideoFactorySnapshot();
    NSData *data=[NSJSONSerialization dataWithJSONObject:record options:NSJSONWritingPrettyPrinted error:nil];
    if(![data writeToFile:[@(argv[2])stringByAppendingPathComponent:@"factory-resolver.json"]options:0 error:nil])return 3;
    return status?status:([record[@"status"]isEqual:@"COMPLETE"]?0:4);
}}
