#import "KeplerProgramImport.h"
extern "C" id<MTLComputePipelineState> KPInternalCASCreatePipeline(id<MTLDevice>,NSURL*,NSString*,NSData*,KeplerImportConfig,NSError**,NSDictionary**);
extern "C" id<MTLComputePipelineState> KPInternalCASCreatePreservingNativeCASPipeline(id<MTLDevice>,NSURL*,NSString*,NSData*,NSData*,NSError**,NSDictionary**);
extern "C" id<MTLComputePipelineState> KPCreatePipeline(id<MTLDevice> d,NSURL* l,NSString* f,NSData* c,KeplerImportConfig q,NSError** e,NSDictionary** p) { return KPInternalCASCreatePipeline(d,l,f,c,q,e,p); }
extern "C" id<MTLComputePipelineState> KPCreatePreservingNativeCASPipeline(id<MTLDevice> d,NSURL* l,NSString* f,NSData* a,NSData* b,NSError** e,NSDictionary** p) { return KPInternalCASCreatePreservingNativeCASPipeline(d,l,f,a,b,e,p); }
