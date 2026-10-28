// Included by the application-local transport, compiled without ARC.
#import "KeplerNativeCAS.h"

static NSString *kpCASDigest(NSData *data) {
 if(!data||data.length>UINT32_MAX)return nil;
 unsigned char digest[CC_SHA256_DIGEST_LENGTH];
 CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *text=[NSMutableString string];
 for(unsigned char byte:digest)[text appendFormat:@"%02x",byte];
 return text;
}
static bool kpCASHash(NSData *data,id expected) {
 return [expected isKindOfClass:NSString.class]&&[expected length]==64&&
        [kpCASDigest(data) isEqual:expected];
}
static NSData *kpCASDecode(id value) {
 return [value isKindOfClass:NSString.class]?
        [[[NSData alloc]initWithBase64EncodedString:value options:0]autorelease]:nil;
}
// Bind the named entry to its own indexed AIR range and HASH. The certificate
// may not relabel another entry even when two entries have identical SASS.
static bool kpCASModuleMatches(NSData *library,NSString *function,NSDictionary *module) {
 const unsigned char *b=(const unsigned char*)library.bytes;size_t n=library.length;
 if(n<88||memcmp(b,"MTLB",4)||u64(b,16)!=n)return false;
 uint64_t start=u64(b,24),extent=u64(b,32),bc=u64(b,72),bcSize=u64(b,80);
 if(start<88||start>n||extent>n-start||n-start-extent<8||bc<88||bc>n||bcSize>n-bc)return false;
 if(extent<4)return false;
 unsigned count=u32(b,start);if(!count||count>1024)return false;
 uint64_t pos=start+4,limit=start+extent;unsigned matches=0;
 for(unsigned i=0;i<count;i++) {
  if(pos>limit||limit-pos<4)return false;
  uint64_t entrySize=u32(b,pos),end=pos+entrySize;
  if(entrySize<8||end<pos||end>limit+4||end>n)return false;
  uint64_t cursor=pos+4;NSString *name=nil;NSData *hash=nil;
  uint64_t moduleSize=0,relative=UINT64_MAX;int type=-1;bool terminated=false;
  while(cursor+4<=end) {
   if(!memcmp(b+cursor,"ENDT",4)){terminated=cursor+4==end;break;}
   if(end-cursor<6)return false;
   uint16_t length;memcpy(&length,b+cursor+4,2);uint64_t payload=cursor+6;
   if(length>end-payload)return false;
   if(!memcmp(b+cursor,"NAME",4)) {
    if(name||length<2||length>256||b[payload+length-1]||memchr(b+payload,0,length-1))return false;
    name=[[[NSString alloc]initWithBytes:b+payload length:length-1 encoding:NSUTF8StringEncoding]autorelease];if(!name)return false;
   }else if(!memcmp(b+cursor,"TYPE",4)) {
    if(type!=-1||length!=1)return false;type=b[payload];
   }else if(!memcmp(b+cursor,"HASH",4)) {
    if(hash||length!=32)return false;hash=[NSData dataWithBytes:b+payload length:32];
   }else if(!memcmp(b+cursor,"MDSZ",4)) {
    if(moduleSize||length!=8)return false;moduleSize=u64(b,payload);
   }else if(!memcmp(b+cursor,"OFFT",4)) {
    if(relative!=UINT64_MAX||length!=24)return false;relative=u64(b,payload+16);
   }
   cursor=payload+length;
  }
  if(!terminated||!name||!hash||!moduleSize||relative>bcSize||moduleSize>bcSize-relative)return false;
  if([name isEqual:function]) {
   if(type!=2||bc+relative!=[module[@"offset"]unsignedLongLongValue]||moduleSize!=[module[@"bytes"]unsignedLongLongValue])return false;
   NSMutableString *digest=[NSMutableString string];for(NSUInteger j=0;j<hash.length;j++)[digest appendFormat:@"%02x",((const unsigned char*)hash.bytes)[j]];
   if(![digest isEqual:module[@"sha256"]])return false;
   matches++;
  }
  pos=end;
 }
 return matches==1&&pos==limit+4&&pos<=n-4&&!memcmp(b+pos,"ENDT",4);
}

extern "C" id<MTLComputePipelineState> KPCreateCertifiedNativeCASPipeline(
 id<MTLDevice> device,NSData *libraryData,NSString *expectedLibrarySHA256,
 NSData *certificateData,NSString *expectedCertificateSHA256,
 NSError **error,NSDictionary **evidence) {
 if(error)*error=nil;if(evidence)*evidence=nil;
 // Refuse before parsing: a malformed nested certificate must not reach
 // exception cleanup that belongs to the active outer import.
 if(activeContext||nativeAllocationScopeActive||expectedNativeOriginal||keepNativeMetadata||certifiedLibraryData||certifiedNativeMetadata){fail(error,@"Nested CAS context refused");return nil;}
 if(![libraryData isKindOfClass:NSData.class]||!libraryData.length||libraryData.length>64*1024*1024||
    ![certificateData isKindOfClass:NSData.class]||!certificateData.length||certificateData.length>1024*1024||
    !KPKepler880MIdentity(device)){fail(error,@"Unqualified CAS input/device");return nil;}
 NSData *library=[[libraryData copy]autorelease],*certificate=[[certificateData copy]autorelease];
 bool identities=kpCASHash(library,expectedLibrarySHA256)&&kpCASHash(certificate,expectedCertificateSHA256);
 if(!identities){fail(error,@"CAS library/certificate fingerprint differs");if(evidence)*evidence=@{@"gate_accepted":@NO,@"constructor_entered":@NO};return nil;}
 id parsed=[NSJSONSerialization JSONObjectWithData:certificate options:0 error:error];
 if(![parsed isKindOfClass:NSDictionary.class]){fail(error,@"CAS certificate object required");return nil;}
 NSDictionary *cert=parsed;
 id<MTLComputePipelineState> pipeline=nil;NSDictionary *proof=nil;
 @try {
  NSDictionary *air=cert[@"AIR"],*sass=cert[@"SASS"],*module=cert[@"embedded_AIR"];
  if(![air isKindOfClass:NSDictionary.class]||![sass isKindOfClass:NSDictionary.class]||
     ![module isKindOfClass:NSDictionary.class]){fail(error,@"Missing CAS diagnosis");return nil;}
  NSString *function=cert[@"function"];
  id repairProfile=cert[@"repair_profile"];
  bool conditionalProfile=[repairProfile isKindOfClass:NSString.class]&&
      [repairProfile isEqual:@"gk104-conditional-pinned-v1"];
  NSData *original=kpCASDecode(cert[@"original_code_base64"]),*replacement=kpCASDecode(cert[@"repaired_code_base64"]),
         *metadata=kpCASDecode(cert[@"native_metadata_base64"]);
  NSUInteger component=[air[@"expected_output_component"]unsignedIntegerValue];
  uint64_t offset=[module[@"offset"]unsignedLongLongValue],length=[module[@"bytes"]unsignedLongLongValue];
  bool bounded=length>=20&&offset<=library.length&&length<=library.length-offset;
  NSData *embedded=bounded?[library subdataWithRange:NSMakeRange(offset,length)]:nil;
  bool semantic=[cert[@"schema"]unsignedIntValue]==1&&[cert[@"candidate"]boolValue]&&
      [cert[@"SASS_only_repair_forbidden"]boolValue]&&[cert[@"intent"]isEqual:@"post_CAS_expected"]&&
      [function isKindOfClass:NSString.class]&&function.length&&function.length<=255&&
      (!certifiedSuppliedFunction||(certifiedSuppliedFunction.device==device&&[certifiedSuppliedFunction.name isEqual:function]))&&
      [module[@"name"]isEqual:function]&&[module[@"type"]unsignedIntValue]==2&&
      ((!conditionalProfile&&[air[@"qualified"]boolValue]&&[sass[@"qualified"]boolValue])||
       (conditionalProfile&&![air[@"qualified"]boolValue]&&![sass[@"qualified"]boolValue]&&
        [air[@"reason"]isEqual:@"Expected is not directly inserted into one output vector"]&&
        [sass[@"reason"]isEqual:@"indirect or unsupported branch"]&&
        [cert[@"qualification"]isEqual:@"manual-exact-profile-gpu-tested"]))&&component<=3&&
      component==[sass[@"expected_output_component"]unsignedIntegerValue]&&
      kpCASModuleMatches(library,function,module)&&
      kpCASHash(library,cert[@"library_SHA256"])&&kpCASHash(embedded,module[@"sha256"])&&
      kpCASHash(original,cert[@"original_code_SHA256"])&&kpCASHash(replacement,cert[@"repaired_code_SHA256"])&&
      kpCASHash(metadata,cert[@"native_metadata_SHA256"]);
  if(!semantic){fail(error,@"CAS semantic/identity gate refused");if(evidence)*evidence=@{@"gate_accepted":@NO,@"constructor_entered":@NO};return nil;}
  NSUInteger redirect=[sass[@"redirect_offset"]unsignedIntegerValue],size=original.length;
  bool structure=size>=64&&size<=65536-64&&size%64==0&&metadata.length==232&&
      replacement.length==size+64&&redirect<size&&redirect%8==0&&redirect%64!=0&&
      [sass[@"return_offset"]unsignedIntegerValue]==redirect+8;
  NSUInteger oldRegister=[sass[@"old_register"]unsignedIntegerValue],expectedRegister=[sass[@"expected_register"]unsignedIntegerValue];
  structure=structure&&oldRegister<24&&expectedRegister<24&&oldRegister!=expectedRegister;
  const unsigned char *a=(const unsigned char*)original.bytes,*b=(const unsigned char*)replacement.bytes;
  bool copiedLockProfile=[repairProfile isKindOfClass:NSString.class]&&
      [repairProfile isEqual:@"gk104-livecopy-pinned-v1"];
  structure=structure&&(!repairProfile||copiedLockProfile||conditionalProfile);
  if(structure){
   structure=u32((const unsigned char*)metadata.bytes,0)==size/8-1&&
      memcmp(a+redirect,b+size+8,8)==0&&
      u64(b,size+16)==(0x2800000000001de4ULL|(uint64_t(oldRegister)<<26)|(uint64_t(expectedRegister)<<14));
   if(copiedLockProfile){
    // Separately GPU-qualified exact program. This does not authorize another
    // register flow or a generic displaced constant-bank instruction.
    structure=structure&&[function isEqual:@"test"]&&component==0&&size==0x5c0&&
      redirect==0x530&&oldRegister==5&&expectedRegister==0&&
      kpCASHash(library,@"17cd653eb49ab7749f6013145e71292d51ce467f2a094451e6f1fc9192a31632")&&
      kpCASHash(original,@"f16bf16da56d5dc060429f6886d2e1d80eafa0a960f48b7d776a3234fb6bcb41")&&
      kpCASHash(replacement,@"a193a1c62851ff483bcb3ab7fda86e9646108e36f1552f80a879616e7017e58f")&&
      kpCASHash(metadata,@"b688a341c68920bb8e8c383f5a2a87d37ac5a1c93a962a531ff8f4a289ecbf12");
   }else if(conditionalProfile){
    // The AIR and flow recognizers explicitly refuse this profile. Only the
    // separately tested exact bytes are admitted; no arbitrary branch or
    // conditional shader is inferred safe.
    structure=structure&&[function isEqual:@"divergence_case"]&&component==0&&size==0x540&&
      redirect==0x428&&oldRegister==0&&expectedRegister==4&&
      kpCASHash(library,@"811e53236f858247d59ae1540efb1a74160c0e566522faadd9fa82ad60de8640")&&
      kpCASHash(original,@"83fedb1873bf54ae9975d3f44bd8e8512a9639903afee18d2decef4fbcdd2eb2")&&
      kpCASHash(replacement,@"d0dfcbe6cbcdbba8df91289d7eb56f122ba48eeeb91d7c6b294ceaf7c291e1e8")&&
      kpCASHash(metadata,@"f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe");
   }else structure=structure&&u64(a,redirect)==0xe000000000001c05ULL;
   for(NSUInteger i=0;i<size&&structure;i+=8)
    if(i!=redirect&&memcmp(a+i,b+i,8))structure=false;
  }
  if(!structure){fail(error,@"CAS trampoline/metadata structure refused");if(evidence)*evidence=@{@"gate_accepted":@NO,@"constructor_entered":@NO};return nil;}
  if(activeContext||nativeAllocationScopeActive||expectedNativeOriginal||keepNativeMetadata||certifiedLibraryData||certifiedNativeMetadata){fail(error,@"Nested CAS context refused");return nil;}
  certifiedLibraryData=library;certifiedNativeMetadata=metadata;
  @try {
   pipeline=KPInternalCASCreatePreservingNativeCASPipeline(device,nil,function,original,replacement,error,&proof);
  } @finally {certifiedLibraryData=nil;certifiedNativeMetadata=nil;}
  // The core captures restoration while holding importMutex. Sampling an IMP
  // before acquiring that mutex can observe another legitimate caller's hook;
  // sampling after release can observe the next caller. Neither is our baseline.
  bool restored=[proof[@"constructor_restored"]boolValue];
  if(pipeline&&!restored){[pipeline release];pipeline=nil;fail(error,@"CAS constructor was not restored");}
  if(pipeline)objc_setAssociatedObject(pipeline,&certifiedInputsKey,@[library,certificate],OBJC_ASSOCIATION_RETAIN_NONATOMIC);
  if(evidence)*evidence=@{@"gate_accepted":@YES,@"function":function,@"library_SHA256":kpCASDigest(library),
      @"certificate_SHA256":kpCASDigest(certificate),@"immutable_library_data":@YES,
      @"constructor_restored":@(restored),@"native_import":proof?:@{},
      @"scope":@"Explicit adapted-client pipeline; approved bounded AIR/SASS certificate, not general compiler repair"};
 } @catch(NSException *exception) {
  certifiedLibraryData=nil;certifiedNativeMetadata=nil;
  if(pipeline){[pipeline release];pipeline=nil;}
  fail(error,exception.reason?:@"Invalid CAS certificate");
 }
 return pipeline;
}

// Internal interoperability contract: the ICB loader creates this exact function
// from its verified immutable library. An arbitrary caller-supplied MTLFunction
// is not a semantic origin proof. Keep the standalone public API data-based.
@interface KPCertifiedNativeCASFactory : NSObject
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
      function:(id<MTLFunction>)function libraryData:(NSData*)library
      expectedSHA256:(NSString*)librarySHA certificateData:(NSData*)certificate
      expectedCertificateSHA256:(NSString*)certificateSHA options:(MTLPipelineOption)options
      reflection:(MTLComputePipelineReflection**)reflection error:(NSError**)error
      evidence:(NSDictionary**)evidence NS_RETURNS_RETAINED;
@end
@implementation KPCertifiedNativeCASFactory
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
      function:(id<MTLFunction>)function libraryData:(NSData*)library
      expectedSHA256:(NSString*)librarySHA certificateData:(NSData*)certificate
      expectedCertificateSHA256:(NSString*)certificateSHA options:(MTLPipelineOption)options
      reflection:(MTLComputePipelineReflection**)reflection error:(NSError**)error
      evidence:(NSDictionary**)evidence {
 if(reflection)*reflection=nil;
 if(activeContext||nativeAllocationScopeActive||certifiedSuppliedFunction||!function||function.device!=device||
    options!=(MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo)){
  fail(error,@"Unqualified native CAS reflection interoperability context");return nil;
 }
 certifiedSuppliedFunction=function;certifiedPipelineOptions=options;certifiedReflection=reflection;
 @try{return KPCreateCertifiedNativeCASPipeline(device,library,librarySHA,certificate,certificateSHA,error,evidence);}
 @finally{certifiedSuppliedFunction=nil;certifiedPipelineOptions=MTLPipelineOptionNone;certifiedReflection=nullptr;}
}
@end
