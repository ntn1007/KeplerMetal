// SPDX-License-Identifier: MIT
// Process-local laboratory adapter; not part of the public CAS SDK.
#include "KeplerNativeCAS.mm"
extern "C" id<MTLComputePipelineState> KPConditionalCB0WitnessPipeline(
 id<MTLDevice>d,NSData*library,NSData*metadata,NSData*original,NSData*replacement,
 NSError**error,NSDictionary**proof){
 if(activeContext||nativeAllocationScopeActive||expectedNativeOriginal||keepNativeMetadata||
    certifiedLibraryData||certifiedNativeMetadata||certifiedConditionalAux)return nil;
 id<MTLComputePipelineState> pipeline=nil;
 certifiedLibraryData=library;certifiedNativeMetadata=metadata;certifiedConditionalAux=true;
 @try{pipeline=KPInternalCASCreatePreservingNativeCASPipeline(d,nil,@"divergence_case",original,replacement,error,proof);}
 @finally{certifiedLibraryData=nil;certifiedNativeMetadata=nil;certifiedConditionalAux=false;}
 return pipeline;
}
