// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
extern "C" bool KPVideoFactoryBegin(NSString*);
extern "C" NSDictionary*KPVideoFactorySnapshot();
extern "C" bool KPAliasNativeBegin(NSString*);
extern "C" NSDictionary*KPAliasNativeSnapshot();
extern "C" bool KPGateBegin(NSString*);
extern "C" NSDictionary*KPGateSnapshot();
int KPOwnedQualifiedMain(int,char**);
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4||!KPVideoFactoryBegin(@(argv[1]))||!KPAliasNativeBegin(@(argv[1]))||!KPGateBegin(@(argv[1])))return 2;
 int status=KPOwnedQualifiedMain(argc,argv);NSDictionary*alias=KPAliasNativeSnapshot(),*factory=KPVideoFactorySnapshot(),*gate=KPGateSnapshot();
 for(NSArray*pair in @[@[@"factory-resolver.json",factory],@[@"alias-native.json",alias],@[@"provider-gate.json",gate]]){
  NSData*d=[NSJSONSerialization dataWithJSONObject:pair[1] options:NSJSONWritingPrettyPrinted error:nil];
  if(!d||![d writeToFile:[@(argv[2])stringByAppendingPathComponent:pair[0]] options:0 error:nil])return 3;
 }
 return status?status:([alias[@"status"]isEqual:@"COMPLETE"]&&[factory[@"status"]isEqual:@"COMPLETE"]&&[gate[@"status"]isEqual:@"COMPLETE"]?0:4);
}}
