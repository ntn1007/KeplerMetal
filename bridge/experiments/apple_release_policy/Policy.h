// SPDX-License-Identifier: MIT
// Explicit launcher-selected policy. It is not an independent trust boundary.
#pragma once
#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>

static NSString *KPPolicyDigest(NSData *data){
    if(!data || !data.length || data.length>65536)return nil;
    unsigned char digest[32];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
    NSMutableString *result=[NSMutableString new];for(unsigned char c:digest)[result appendFormat:@"%02x",c];return result;
}
static BOOL KPPolicyHex(id value){
    return [value isKindOfClass:NSString.class]&&[value length]==64&&[value rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"] invertedSet]].location==NSNotFound;
}
static NSString *KPApprovedPolicy(NSData *data,NSString *expected,NSString *client){
    if(!KPPolicyHex(expected)||!KPPolicyHex(client)||![KPPolicyDigest(data)isEqual:expected])return nil;
    id value=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];if(![value isKindOfClass:NSDictionary.class])return nil;
    NSDictionary *policy=value;id version=policy[@"version"],allowed=policy[@"allowed_clients"];
    if(policy.count!=2||![version isKindOfClass:NSNumber.class]||CFGetTypeID((__bridge CFTypeRef)version)==CFBooleanGetTypeID()||![version isEqual:@1]||![allowed isKindOfClass:NSArray.class]||![allowed count]||[allowed count]>16)return nil;
    NSMutableSet *seen=[NSMutableSet new];for(id item in allowed){if(!KPPolicyHex(item)||[seen containsObject:item])return nil;[seen addObject:item];}
    return [seen containsObject:client]?expected:nil;
}
