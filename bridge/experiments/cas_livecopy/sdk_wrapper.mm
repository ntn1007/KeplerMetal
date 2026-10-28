// SPDX-License-Identifier: MIT
// Laboratory probe adapter: exercise the public certificate API using the
// existing native-CAS numerical host. This is not an application bootstrap.
#import "KeplerProgramImport.h"
#import "KeplerNativeCAS.h"
#include <CommonCrypto/CommonDigest.h>
#include <cstdlib>

extern "C" id<MTLComputePipelineState> KPInternalCASCreatePipeline(id<MTLDevice>,NSURL*,NSString*,NSData*,KeplerImportConfig,NSError**,NSDictionary**);

static NSString *sha256(NSData *data) {
 if(!data||data.length>UINT32_MAX)return nil;
 unsigned char digest[32];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *text=[NSMutableString string];
 for(unsigned char byte:digest)[text appendFormat:@"%02x",byte];
 return text;
}

extern "C" id<MTLComputePipelineState> KPCreatePipeline(id<MTLDevice> d,NSURL* l,NSString* f,NSData* c,KeplerImportConfig q,NSError** e,NSDictionary** p) {
 return KPInternalCASCreatePipeline(d,l,f,c,q,e,p);
}

extern "C" id<MTLComputePipelineState> KPCreatePreservingNativeCASPipeline(id<MTLDevice> d,NSURL* l,NSString* f,NSData* original,NSData* replacement,NSError** e,NSDictionary** p) {
 const char *path=getenv("KM_CAS_CERT");
 NSData *library=[NSData dataWithContentsOfURL:l],*templateData=path?[NSData dataWithContentsOfFile:@(path)]:nil;
 id parsed=templateData?[NSJSONSerialization JSONObjectWithData:templateData options:NSJSONReadingMutableContainers error:e]:nil;
 if(![parsed isKindOfClass:NSMutableDictionary.class]||!library||!original||!replacement)return nil;
 NSMutableDictionary *certificate=parsed;
 certificate[@"original_code_base64"]=[original base64EncodedStringWithOptions:0];
 certificate[@"original_code_SHA256"]=sha256(original);
 certificate[@"repaired_code_base64"]=[replacement base64EncodedStringWithOptions:0];
 certificate[@"repaired_code_SHA256"]=sha256(replacement);
 NSData *encoded=[NSJSONSerialization dataWithJSONObject:certificate options:0 error:e];
 if(!encoded)return nil;
 return KPCreateCertifiedNativeCASPipeline(d,library,sha256(library),encoded,sha256(encoded),e,p);
}
