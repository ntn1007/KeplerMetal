// SPDX-License-Identifier: MIT
// Use the ordinary numerical client after wiping caller inputs and draining
// the factory pool. The candidate program/metadata implementation is unchanged.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstring>

extern "C" id<MTLComputePipelineState> KPExperimentalCreateNativeReservePipeline(
 id<MTLDevice>,NSURL*,NSString*,NSData*,NSString*,uint32_t,NSError**,NSDictionary**) NS_RETURNS_RETAINED;

extern "C" id<MTLComputePipelineState> KPLifetimeCreateNativeReservePipeline(
 id<MTLDevice>device,NSURL*library,NSString*function,NSData*certificate,
 NSString*codeHash,uint32_t reserve,NSError**error,NSDictionary**proof) NS_RETURNS_RETAINED {
 id<MTLComputePipelineState>kept=nil;
 NSMutableDictionary*ownedProof=nil;
 @autoreleasepool {
  NSMutableData*callerMetadata=[NSMutableData dataWithData:certificate];
  NSMutableString*callerHash=[NSMutableString stringWithString:codeHash];
  NSDictionary*constructionProof=nil;
  kept=KPExperimentalCreateNativeReservePipeline(device,library,function,
      callerMetadata,callerHash,reserve,error,&constructionProof);
  ownedProof=[constructionProof mutableCopy];
  [callerMetadata resetBytesInRange:NSMakeRange(0,callerMetadata.length)];
  [callerHash setString:@"caller-overwritten"];
  ownedProof[@"caller_metadata_overwritten"]=@(memcmp(callerMetadata.bytes,certificate.bytes,certificate.length)!=0);
  ownedProof[@"caller_hash_overwritten"]=@(![callerHash isEqual:codeHash]);
 }
 // The construction pool has ended before the caller creates any GPU command.
 ownedProof[@"factory_autorelease_pool_drained"]=@YES;
 if(proof)*proof=ownedProof;
 return kept;
}

#define KPExperimentalCreateNativeReservePipeline KPLifetimeCreateNativeReservePipeline
#include "control_flow_probe.mm"
