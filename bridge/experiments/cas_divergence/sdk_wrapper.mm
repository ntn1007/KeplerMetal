// SPDX-License-Identifier: MIT
// Laboratory bridge from the existing numerical host to the public CAS API.
#import "KeplerNativeCAS.h"
#include <CommonCrypto/CommonDigest.h>
#include <cstdlib>

static NSString *sha256(NSData *data) {
 if(!data||data.length>UINT32_MAX)return nil;
 unsigned char digest[32];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *text=[NSMutableString string];
 for(unsigned char byte:digest)[text appendFormat:@"%02x",byte];
 return text;
}

extern "C" id<MTLComputePipelineState> KPCertifiedConditionalCASPipeline(
 id<MTLDevice> device,NSURL *path,NSString *function,NSData *original,NSData *replacement,
 NSError **error,NSDictionary **evidence) {
 const char *certPath=getenv("KM_CAS_CONDITIONAL_CERT");
 NSData *library=[NSData dataWithContentsOfURL:path];
 NSData *templateData=certPath?[NSData dataWithContentsOfFile:@(certPath)]:nil;
 id parsed=templateData?[NSJSONSerialization JSONObjectWithData:templateData options:NSJSONReadingMutableContainers error:error]:nil;
 if(![parsed isKindOfClass:NSMutableDictionary.class]||!library||!original||!replacement||
    ![function isEqual:@"divergence_case"])return nil;
 NSMutableDictionary *certificate=parsed;
 certificate[@"original_code_base64"]=[original base64EncodedStringWithOptions:0];
 certificate[@"original_code_SHA256"]=sha256(original);
 certificate[@"repaired_code_base64"]=[replacement base64EncodedStringWithOptions:0];
 certificate[@"repaired_code_SHA256"]=sha256(replacement);
 NSData *encoded=[NSJSONSerialization dataWithJSONObject:certificate options:0 error:error];
 if(!encoded)return nil;
 return KPCreateCertifiedNativeCASPipeline(device,library,sha256(library),encoded,sha256(encoded),error,evidence);
}
