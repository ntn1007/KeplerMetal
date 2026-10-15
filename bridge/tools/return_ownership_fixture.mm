// CPU-only +1 C factory implementation matching the documented import contract.
#import "KeplerProgramImport.h"
static unsigned created=0,destroyed=0;
@interface KPReturnToken:NSObject @end
@implementation KPReturnToken
- (instancetype)init{if((self=[super init]))created++;return self;}
- (void)dealloc{destroyed++;[super dealloc];}
@end
extern "C" unsigned KPReturnCreated(){return created;}
extern "C" unsigned KPReturnDestroyed(){return destroyed;}
extern "C" id<MTLComputePipelineState> KPCreatePipeline(id<MTLDevice>,NSURL*,NSString*,NSData*,KeplerImportConfig,NSError**,NSDictionary**){return(id<MTLComputePipelineState>)[KPReturnToken new];}
extern "C" id<MTLRenderPipelineState> KPCreateRenderPipeline(id<MTLDevice>,MTLRenderPipelineDescriptor*,NSData*,KeplerImportConfig,NSError**,NSDictionary**){return(id<MTLRenderPipelineState>)[KPReturnToken new];}
extern "C" id<MTLRenderPipelineState> KPCreateVertexPipeline(id<MTLDevice>,MTLRenderPipelineDescriptor*,NSData*,KeplerImportConfig,NSError**,NSDictionary**){return(id<MTLRenderPipelineState>)[KPReturnToken new];}
extern "C" id<MTLRenderPipelineState> KPCreateTessellationPipeline(id<MTLDevice>,MTLRenderPipelineDescriptor*,NSData*,KeplerImportConfig,NSError**,NSDictionary**){return(id<MTLRenderPipelineState>)[KPReturnToken new];}
extern "C" id<MTLRenderPipelineState> KPCreateGraphicsPipeline(id<MTLDevice>,MTLRenderPipelineDescriptor*,NSData*,KeplerImportConfig,NSData*,KeplerImportConfig,NSError**,NSDictionary**){return(id<MTLRenderPipelineState>)[KPReturnToken new];}
extern "C" id<MTLBuffer> KPCreateHostBuffer(id<MTLDevice>,const void*,NSUInteger,bool){return(id<MTLBuffer>)[KPReturnToken new];}
