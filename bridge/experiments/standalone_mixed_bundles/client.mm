// SPDX-License-Identifier: MIT
// Public Metal executable: no KeplerMetal headers, symbols or API calls.
#include "workload.inc"
static void require(BOOL b,NSString*message){if(!b)@throw [NSException exceptionWithName:@"PublicClientFailure" reason:message userInfo:nil];}
static id<MTLLibrary> loadLibrary(id<MTLDevice>d,NSString*path,NSString*route,NSUInteger*segments,NSError**error){
 *segments=0;if([route isEqual:@"main"])return [d newDefaultLibrary];
 if([route isEqual:@"bundle"]){NSBundle*b=[NSBundle bundleWithPath:path];require(b!=nil,@"bundle unavailable");return [d newDefaultLibraryWithBundle:b error:error];}
 if([route isEqual:@"file"])return [d newLibraryWithFile:path error:error];
 if([route isEqual:@"url"])return [d newLibraryWithURL:[NSURL fileURLWithPath:path] error:error];
 require([@[@"data",@"segmented"]containsObject:route],@"invalid loader");NSData*bytes=[NSData dataWithContentsOfFile:path];require(bytes.length>1,@"library bytes missing");dispatch_queue_t q=dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0);dispatch_data_t payload=nil;
 if([route isEqual:@"data"])payload=dispatch_data_create(bytes.bytes,bytes.length,q,^{(void)bytes.length;});else{NSUInteger half=bytes.length/2;dispatch_data_t left=dispatch_data_create(bytes.bytes,half,q,^{(void)bytes.length;});dispatch_data_t right=dispatch_data_create((const uint8_t*)bytes.bytes+half,bytes.length-half,q,^{(void)bytes.length;});payload=dispatch_data_create_concat(left,right);}
 __block NSUInteger count=0;dispatch_data_apply(payload,^bool(dispatch_data_t region,size_t offset,const void*data,size_t length){(void)region;(void)offset;(void)data;(void)length;count++;return true;});*segments=count;return [d newLibraryWithData:payload error:error];
}
int main(int argc,char**argv){@autoreleasepool{@try{
 require(argc==6,@"compute render output mode routes");NSString*mode=@(argv[4]);NSArray*routes=[@(argv[5]) componentsSeparatedByString:@","];require(routes.count==2,@"two loader routes");NSUInteger computeSegments=0,renderSegments=0;
 require([@[@"direct",@"icb",@"no-producer",@"no-render",@"bad-descriptor"]containsObject:mode],@"mode");
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d){fprintf(stderr,"no device\n");return 3;}
 id<MTLCommandQueue>q=[d newCommandQueue];require(q!=nil,@"queue");NSError*error=nil;
 id<MTLLibrary>compute=loadLibrary(d,@(argv[1]),routes[0],&computeSegments,&error);require(compute!=nil,error.description?:@"compute library");
 id<MTLFunction>cf=[compute newFunctionWithName:@"gpu_indices"];require(cf!=nil,@"compute function");
 id<MTLComputePipelineState>cp=[d newComputePipelineStateWithFunction:cf error:&error];require(cp!=nil,error.description?:@"compute pipeline");
 id<MTLLibrary>render=loadLibrary(d,@(argv[2]),routes[1],&renderSegments,&error);require(render!=nil,error.description?:@"render library");
 MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.vertexFunction=[render newFunctionWithName:@"vs_state"];desc.fragmentFunction=[render newFunctionWithName:@"fs_state"];require(desc.vertexFunction&&desc.fragmentFunction,@"render functions");desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;if([mode isEqual:@"bad-descriptor"])desc.colorAttachments[0].writeMask=MTLColorWriteMaskRed;desc.supportIndirectCommandBuffers=![mode isEqual:@"direct"];
 id<MTLRenderPipelineState>rp=[d newRenderPipelineStateWithDescriptor:desc error:&error];require(rp!=nil,error.description?:@"render pipeline");
 NSDictionary*result=run_public_mixed(d,q,cp,rp,@(argv[3]),[mode isEqual:@"bad-descriptor"]?@"icb":mode);require([result[@"status"]isEqual:@"PASS"],result[@"error"]?:@"workload");
 NSDictionary*o=@{@"status":@"PASS",@"client":result,@"device":d.name,@"registry_id":@(d.registryID),@"created_pipelines_by_public_API":@YES,@"loader_routes":routes,@"compute_segments":@(computeSegments),@"render_segments":@(renderSegments)};NSData*j=[NSJSONSerialization dataWithJSONObject:o options:NSJSONWritingPrettyPrinted error:&error];require(j!=nil,@"json");fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
 }@catch(NSException*x){fprintf(stderr,"client: %s\n",x.reason.UTF8String?:"");return 1;}}}
