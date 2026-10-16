// SPDX-License-Identifier: MIT
// Adapter from the frozen numerical client to the common certified data API.
#import "KeplerNativeAllocation.h"
#include <cstring>
#ifndef KP_ALLOCATION_LIFETIME
#define KP_ALLOCATION_LIFETIME 0
#endif

extern "C" id<MTLComputePipelineState> KPCommonNativeAllocationPipeline(
 id<MTLDevice>device,NSURL*libraryURL,NSString*function,NSData*metadata,
 NSString*codeHash,uint32_t reserve,NSError**error,NSDictionary**proof) NS_RETURNS_RETAINED {
 id<MTLComputePipelineState>kept=nil;NSMutableDictionary*ownedProof=nil;
 @autoreleasepool {
  NSURL*assets=[libraryURL URLByDeletingLastPathComponent];
  NSDictionary*manifest=[NSJSONSerialization JSONObjectWithData:
      [NSData dataWithContentsOfURL:[assets URLByAppendingPathComponent:@"native-allocation-manifest.json"]]
      options:0 error:error];
  NSDictionary*entry=manifest[@"certificates"][function];
  NSMutableData*library=[NSMutableData dataWithContentsOfURL:libraryURL];
  NSMutableData*certificate=[NSMutableData dataWithContentsOfURL:[assets URLByAppendingPathComponent:entry[@"file"]]];
  NSDictionary*profile=certificate?[NSJSONSerialization JSONObjectWithData:certificate options:0 error:error]:nil;
  NSArray*words=profile[@"metadata_words"];NSMutableData*packed=[NSMutableData dataWithLength:232];
  if(words.count!=58||metadata.length!=232||reserve!=4096||![profile[@"function"]isEqual:function]||
     ![profile[@"native_code_sha256"]isEqual:codeHash])return nil;
  for(unsigned i=0;i<58;i++){uint32_t v=[words[i]unsignedIntValue];memcpy((char*)packed.mutableBytes+4*i,&v,4);}
  if(memcmp(packed.bytes,metadata.bytes,232))return nil;
  NSDictionary*construction=nil;
  kept=KPCreateCertifiedNativeAllocationPipeline(device,library,manifest[@"library_sha256"],
      certificate,entry[@"SHA256"],error,&construction);
  ownedProof=[construction mutableCopy];ownedProof[@"legacy_arguments_match_certificate"]=@YES;
#if KP_ALLOCATION_LIFETIME
  memset(library.mutableBytes,0xa5,library.length);memset(certificate.mutableBytes,0x5a,certificate.length);
  ownedProof[@"caller_library_overwritten"]=@YES;ownedProof[@"caller_certificate_overwritten"]=@YES;
#endif
 }
 ownedProof[@"factory_autorelease_pool_drained"]=@YES;
 if(proof)*proof=ownedProof;
 return kept;
}

#define KPExperimentalCreateNativeReservePipeline KPCommonNativeAllocationPipeline
#include "control_flow_probe.mm"
