#import "KeplerProgramImport.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
static void emit(NSDictionary*d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3&&argc!=5)return 1;bool nak=argc==5;unsigned factor=(unsigned)strtoul(argv[2],nullptr,10);if(factor>64)return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];id<MTLFunction>vertex=[library newFunctionWithName:@"tess_triangle"];
 NSMutableDictionary*result=[NSMutableDictionary dictionaryWithDictionary:@{@"device":device.name,@"registry_id":@(device.registryID),@"factor":@(factor),@"family1v2":@([device supportsFeatureSet:MTLFeatureSet_macOS_GPUFamily1_v2]),@"family1v3":@([device supportsFeatureSet:MTLFeatureSet_macOS_GPUFamily1_v3]),@"function_patch_type":@(vertex.patchType),@"function_control_points":@(vertex.patchControlPointCount)}];
 MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.vertexFunction=vertex;desc.fragmentFunction=[library newFunctionWithName:@"tess_fragment"];desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;desc.maxTessellationFactor=64;desc.tessellationPartitionMode=MTLTessellationPartitionModeInteger;desc.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionConstant;desc.tessellationOutputWindingOrder=MTLWindingCounterClockwise;
 id<MTLRenderPipelineState>pipeline=nil;NSDictionary*importEvidence=nil;@try{if(nak){NSDictionary*info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[4])] options:0 error:nil];pipeline=KPCreateTessellationPipeline(device,desc,[NSData dataWithContentsOfFile:@(argv[3])],{[info[@"registers"]unsignedIntValue],0,0},&error,&importEvidence);}else pipeline=[device newRenderPipelineStateWithDescriptor:desc error:&error];}@catch(NSException*e){result[@"exception"]=e.reason?:e.name;}
 result[@"NAK_imported"]=@(nak);result[@"import"]=importEvidence?:@{};
 result[@"pipeline_created"]=@(pipeline!=nil);if(!pipeline){result[@"error"]=error.description?:@"no pipeline";emit(result);return 3;}
 const unsigned W=64,H=48;MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[device newTextureWithDescriptor:td];id<MTLBuffer>readback=KPCreateHostBuffer(device,nullptr,W*H*16,true);if(!target||!readback)return 4;
 // Integer factors are exact half values; construct their binary representation.
 uint16_t bits=0;if(factor){unsigned e=0;while((1u<<(e+1))<=factor)e++;bits=(uint16_t)(((e+15)<<10)|((factor-(1u<<e))<<(10-e)));}
 MTLTriangleTessellationFactorsHalf values={{bits,bits,bits},bits};id<MTLBuffer>factors=KPCreateHostBuffer(device,&values,sizeof values,true);
 MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);pass.colorAttachments[0].storeAction=MTLStoreActionStore;
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLRenderCommandEncoder>encoder=[command renderCommandEncoderWithDescriptor:pass];[encoder setRenderPipelineState:pipeline];[encoder setViewport:(MTLViewport){0,0,W,H,0,1}];[encoder setCullMode:MTLCullModeNone];[encoder setTessellationFactorBuffer:factors offset:0 instanceStride:0];[encoder drawPatches:3 patchStart:0 patchCount:1 patchIndexBuffer:nil patchIndexBufferOffset:0 instanceCount:1 baseInstance:0];[encoder endEncoding];
 id<MTLBlitCommandEncoder>copy=[command blitCommandEncoder];[copy copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:W*16 destinationBytesPerImage:W*H*16];[copy endEncoding];[command commit];[command waitUntilCompleted];result[@"command_status"]=@(command.status);if(command.status!=MTLCommandBufferStatusCompleted){result[@"error"]=command.error.description?:@"command failed";emit(result);return 5;}
 const char*pixelPath=getenv("KEPLER_TESS_PIXELS_FILE");if(pixelPath)[[NSData dataWithBytes:readback.contents length:W*H*16]writeToFile:@(pixelPath) atomically:YES];
 const float*out=(const float*)readback.contents;unsigned bad=0;double maxAnalyticError=0,maxFactor1Error=0;NSMutableArray*first=[NSMutableArray array];
 for(unsigned y=0;y<H;y++)for(unsigned x=0;x<W;x++){
  double v=(x+.5)/(2*W),w=(H-y-.5)/(2*H),u=1-v-w;double bary[]={u,v,w};
  for(unsigned c=0;c<4;c++){double actual=out[(y*W+x)*4+c],linear=c==3?1:bary[c],analytic=c==3?1:bary[c]*bary[c];if(nak&&c<3){linear=linear*.5+.125;analytic=analytic*.5+.125;}
   if(!factor){if(actual!=0)bad++;}else if(factor==1){if(std::abs(actual-linear)>2e-6)bad++;}else if(!std::isfinite(actual)||actual<analytic-2e-6||actual>linear+2e-6)bad++;
   if(factor){maxAnalyticError=std::max(maxAnalyticError,std::abs(actual-analytic));maxFactor1Error=std::max(maxFactor1Error,std::abs(actual-linear));}
   if(!x&&!y)[first addObject:@(actual)];
  }
 }
 result[@"mismatches"]=@(bad);result[@"max_error_vs_analytic"]=@(maxAnalyticError);result[@"max_difference_vs_factor1"]=@(maxFactor1Error);result[@"first_pixel"]=first;result[@"oracle"]=factor==0?@"discarded patch -> clear":(factor==1?@"exact linear triangle CPU oracle":@"convex interpolation bounds; not exact generated topology");emit(result);return bad?10:0;
}}
