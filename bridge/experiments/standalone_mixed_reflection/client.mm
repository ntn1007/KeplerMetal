// SPDX-License-Identifier: MIT
// Public Metal executable: no KeplerMetal headers, symbols or API calls.
#include "workload.inc"
static void require(BOOL b,NSString*message){if(!b)@throw [NSException exceptionWithName:@"PublicClientFailure" reason:message userInfo:nil];}
int main(int argc,char**argv){@autoreleasepool{@try{
 require(argc==6,@"compute render output mode factory");NSString*mode=@(argv[4]);NSString*factory=@(argv[5]);
 require([@[@"plain",@"reflection",@"reflection-null",@"options-none"] containsObject:factory],@"factory");
 require([@[@"direct",@"icb",@"no-producer",@"no-render",@"bad-descriptor"]containsObject:mode],@"mode");
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d){fprintf(stderr,"no device\n");return 3;}
 id<MTLCommandQueue>q=[d newCommandQueue];require(q!=nil,@"queue");NSError*error=nil;
 id<MTLLibrary>compute=[d newLibraryWithFile:@(argv[1]) error:&error];require(compute!=nil,error.description?:@"compute library");
 id<MTLFunction>cf=[compute newFunctionWithName:@"gpu_indices"];require(cf!=nil,@"compute function");
 MTLComputePipelineReflection*reflection=nil;id<MTLComputePipelineState>cp=nil;
 if([factory isEqual:@"plain"])cp=[d newComputePipelineStateWithFunction:cf error:&error];
 else {MTLPipelineOption options=[factory isEqual:@"options-none"]?MTLPipelineOptionNone:(MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo);cp=[d newComputePipelineStateWithFunction:cf options:options reflection:[factory isEqual:@"reflection-null"]?nil:&reflection error:&error];}
 require(cp!=nil,error.description?:@"compute pipeline");NSMutableArray*arguments=[NSMutableArray new];
 if([factory isEqual:@"reflection"]){require(reflection!=nil,@"missing native reflection");for(MTLArgument*a in reflection.arguments){[arguments addObject:@{@"name":a.name,@"index":@(a.index),@"type":@(a.type),@"active":@(a.active),@"access":@(a.access),@"size":@(a.bufferDataSize),@"alignment":@(a.bufferAlignment),@"data_type":@(a.bufferDataType)}];}}

 id<MTLLibrary>render=[d newLibraryWithFile:@(argv[2]) error:&error];require(render!=nil,error.description?:@"render library");
 MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.vertexFunction=[render newFunctionWithName:@"vs_state"];desc.fragmentFunction=[render newFunctionWithName:@"fs_state"];require(desc.vertexFunction&&desc.fragmentFunction,@"render functions");desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;if([mode isEqual:@"bad-descriptor"])desc.colorAttachments[0].writeMask=MTLColorWriteMaskRed;desc.supportIndirectCommandBuffers=![mode isEqual:@"direct"];
 id<MTLRenderPipelineState>rp=[d newRenderPipelineStateWithDescriptor:desc error:&error];require(rp!=nil,error.description?:@"render pipeline");
 NSDictionary*result=run_public_mixed(d,q,cp,rp,@(argv[3]),[mode isEqual:@"bad-descriptor"]?@"icb":mode);require([result[@"status"]isEqual:@"PASS"],result[@"error"]?:@"workload");
 NSDictionary*o=@{@"status":@"PASS",@"client":result,@"device":d.name,@"registry_id":@(d.registryID),@"created_pipelines_by_public_API":@YES,@"factory":factory,@"reflection_arguments":arguments};NSData*j=[NSJSONSerialization dataWithJSONObject:o options:NSJSONWritingPrettyPrinted error:&error];require(j!=nil,@"json");fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
 }@catch(NSException*x){fprintf(stderr,"client: %s\n",x.reason.UTF8String?:"");return 1;}}}
