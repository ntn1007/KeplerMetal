// SPDX-License-Identifier: MIT
// Bounded lab-only factory. Preserve the existing signed QMD/numerical client.
// The shared runtime is linked unchanged; this factory explicitly uses the
// previously qualified standalone experiment for2048/2560, not the common API.
#define KPCreateCertifiedNativeAllocationPipeline KPCreateSegmentedReservePipeline
#include "native_allocation_qmd_execute.mm"
#undef KPCreateCertifiedNativeAllocationPipeline

extern "C" id<MTLComputePipelineState> KPExperimentalCreateNativeReservePipeline(
 id<MTLDevice>,NSURL*,NSString*,NSData*,NSString*,uint32_t,NSError**,NSDictionary**) NS_RETURNS_RETAINED;

extern "C" id<MTLComputePipelineState> KPCreateSegmentedReservePipeline(
 id<MTLDevice>device,NSData*libraryData,NSString*libraryHash,NSData*certificateData,
 NSString*certificateHash,NSError**error,NSDictionary**evidence) {
 if(error)*error=nil;
 if(evidence)*evidence=@{};
 NSDictionary*certificate=json(certificateData);
 NSArray*words=certificate[@"metadata_words"];
 NSNumber*reserve=certificate[@"control_reserve"];
 NSArray*arguments=NSProcessInfo.processInfo.arguments;
 if(![sha(libraryData)isEqual:libraryHash]||![sha(certificateData)isEqual:certificateHash]
    ||![certificate[@"intent"]isEqual:@"native_control_reservation_experiment"]
    ||![words isKindOfClass:NSArray.class]||words.count!=58
    ||![reserve isKindOfClass:NSNumber.class]
    ||![@[@2048,@2560]containsObject:reserve]||arguments.count!=4)return nil;
 uint32_t metadata[58];
 for(unsigned i=0;i<58;i++) {
  if(![words[i]isKindOfClass:NSNumber.class])return nil;
  metadata[i]=[words[i]unsignedIntValue];
 }
 NSString*path=[arguments[1]stringByAppendingPathComponent:@"control_flow.metallib"];
 NSData*disk=[NSData dataWithContentsOfFile:path];
 if(![disk isEqual:libraryData])return nil;
 NSDictionary*proof=nil;
 id<MTLComputePipelineState>pipeline=KPExperimentalCreateNativeReservePipeline(
   device,[NSURL fileURLWithPath:path],certificate[@"function"],
   [NSData dataWithBytes:metadata length:sizeof(metadata)],certificate[@"native_code_sha256"],
   reserve.unsignedIntValue,error,&proof);
 if(evidence)*evidence=@{@"backend":@"standalone_experiment",@"requested_reserve":reserve,
                         @"library_SHA256":sha(disk),@"certificate_SHA256":sha(certificateData),
                         @"standalone":proof?:@{}};
 return pipeline;
}
