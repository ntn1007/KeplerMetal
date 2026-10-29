// SPDX-License-Identifier: MIT
// CPU-only tests for exactly the policy parser compiled into the bootstrap.
#import <Foundation/Foundation.h>
#import "Policy.h"
static void need(BOOL v,NSString *message){if(!v)@throw [NSException exceptionWithName:@"PolicyTest" reason:message userInfo:nil];}
static NSData *json(id value){return [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingSortedKeys error:nil];}
int main(void){@autoreleasepool{@try{
 NSString *a=[@"a" stringByPaddingToLength:64 withString:@"a" startingAtIndex:0],*b=[@"b" stringByPaddingToLength:64 withString:@"b" startingAtIndex:0],*c=[@"c" stringByPaddingToLength:64 withString:@"c" startingAtIndex:0];
 NSData *ab=json(@{@"version":@1,@"allowed_clients":@[a,b]}),*onlyA=json(@{@"version":@1,@"allowed_clients":@[a]});
 need(KPApprovedPolicy(ab,KPPolicyDigest(ab),a)&&KPApprovedPolicy(ab,KPPolicyDigest(ab),b)&&KPApprovedPolicy(onlyA,KPPolicyDigest(onlyA),a),@"valid policy");
 NSMutableArray *checks=[NSMutableArray new];void(^reject)(NSString*,NSData*,NSString*,NSString*)=^(NSString *label,NSData *data,NSString *expected,NSString *client){need(!KPApprovedPolicy(data,expected,client),label);[checks addObject:label];};
 reject(@"unlisted",onlyA,KPPolicyDigest(onlyA),b);reject(@"wrong_digest",ab,KPPolicyDigest(onlyA),a);reject(@"unknown_client",ab,KPPolicyDigest(ab),c);
 NSData *dup=json(@{@"version":@1,@"allowed_clients":@[a,a]}),*extra=json(@{@"version":@1,@"allowed_clients":@[a],@"extra":@1}),*empty=json(@{@"version":@1,@"allowed_clients":@[]}),*badversion=json(@{@"version":@YES,@"allowed_clients":@[a]}),*upper=json(@{@"version":@1,@"allowed_clients":@[a.uppercaseString]});
 for(NSArray *row in @[@[@"duplicate",dup],@[@"extra_key",extra],@[@"empty",empty],@[@"boolean_version",badversion],@[@"uppercase",upper]])reject(row[0],row[1],KPPolicyDigest(row[1]),a);
 NSMutableArray *many=[NSMutableArray new];for(int i=0;i<17;i++)[many addObject:[NSString stringWithFormat:@"%064x",i]];NSData *oversized=json(@{@"version":@1,@"allowed_clients":many});reject(@"too_many",oversized,KPPolicyDigest(oversized),a);
 NSData *bad=[@"{" dataUsingEncoding:NSUTF8StringEncoding];reject(@"invalid_json",bad,KPPolicyDigest(bad),a);reject(@"bad_expected",ab,@"bad",a);reject(@"bad_client",ab,KPPolicyDigest(ab),@"bad");
 NSDictionary *result=@{@"status":@"PASS",@"valid_selections":@3,@"refusals":checks,@"GPU_calls":@0};NSData *out=json(result);fwrite(out.bytes,1,out.length,stdout);putchar('\n');return 0;
 }@catch(NSException *e){fprintf(stderr,"%s: %s\n",e.name.UTF8String,e.reason.UTF8String);return 1;}}}
