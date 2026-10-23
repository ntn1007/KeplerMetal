#import "KeplerProgramImport.h"
#import "KeplerGPUIdentity.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
static void emit(NSDictionary *d){NSData *j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=3&&argc!=5)return 1;bool nak=argc==5;unsigned factor=(unsigned)strtoul(argv[2],nullptr,10);if(factor>64)return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();NSDictionary*identity=KPKepler880MIdentity(device);if(!identity)return 2;
 NSError *error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
 MTLRenderPipelineDescriptor *desc=[MTLRenderPipelineDescriptor new];desc.vertexFunction=[library newFunctionWithName:@"tess_capture"];desc.rasterizationEnabled=NO;desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;desc.maxTessellationFactor=64;desc.tessellationPartitionMode=MTLTessellationPartitionModeInteger;desc.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionConstant;desc.tessellationOutputWindingOrder=MTLWindingCounterClockwise;
 NSMutableDictionary *result=[NSMutableDictionary dictionaryWithDictionary:@{@"device":device.name,@"registry_id":@(device.registryID),@"device_identity":identity,@"factor":@(factor),@"NAK_imported":@(nak),@"rasterization_enabled":@NO,@"capacity":@32768}];
 id<MTLRenderPipelineState>pipeline=nil;NSDictionary *evidence=nil;
 @try{if(nak){NSDictionary *info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[4])] options:0 error:nil];pipeline=KPCreateTessellationPipeline(device,desc,[NSData dataWithContentsOfFile:@(argv[3])],{[info[@"registers"]unsignedIntValue],0,0},&error,&evidence);}else pipeline=[device newRenderPipelineStateWithDescriptor:desc error:&error];}@catch(NSException *e){result[@"exception"]=e.reason?:e.name;}
 result[@"pipeline_created"]=@(pipeline!=nil);result[@"import"]=evidence?:@{};if(!pipeline){result[@"error"]=error.description?:@"no pipeline";emit(result);return 3;}
 const size_t guard=64,capacity=32768;size_t dataBytes[]={4,capacity*16,capacity*16};
 id<MTLBuffer>gpu[3],upload[3],readback[3];
 for(unsigned b=0;b<3;b++){
  size_t bytes=dataBytes[b]+2*guard;std::vector<unsigned char>initial(bytes,0xa5);if(!b)memset(initial.data()+guard,0,4);
  gpu[b]=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate];upload[b]=KPCreateHostBuffer(device,initial.data(),bytes,true);readback[b]=KPCreateHostBuffer(device,nullptr,bytes,true);if(!gpu[b]||!upload[b]||!readback[b])return 4;
 }
 uint16_t bits=0;if(factor){unsigned e=0;while((1u<<(e+1))<=factor)e++;bits=(uint16_t)(((e+15)<<10)|((factor-(1u<<e))<<(10-e)));}
 MTLTriangleTessellationFactorsHalf fv={{bits,bits,bits},bits};id<MTLBuffer>factors=KPCreateHostBuffer(device,&fv,sizeof fv,true);
 MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:1 height:1 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[device newTextureWithDescriptor:td];if(!target||!factors)return 4;
 MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionDontCare;pass.colorAttachments[0].storeAction=MTLStoreActionDontCare;
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLBlitCommandEncoder>copy=[command blitCommandEncoder];
 for(unsigned b=0;b<3;b++)[copy copyFromBuffer:upload[b] sourceOffset:0 toBuffer:gpu[b] destinationOffset:0 size:dataBytes[b]+2*guard];[copy endEncoding];
 id<MTLRenderCommandEncoder>encoder=[command renderCommandEncoderWithDescriptor:pass];[encoder setRenderPipelineState:pipeline];for(unsigned b=0;b<3;b++)[encoder setVertexBuffer:gpu[b] offset:guard atIndex:b];[encoder setTessellationFactorBuffer:factors offset:0 instanceStride:0];[encoder drawPatches:3 patchStart:0 patchCount:1 patchIndexBuffer:nil patchIndexBufferOffset:0 instanceCount:1 baseInstance:0];[encoder endEncoding];
 copy=[command blitCommandEncoder];for(unsigned b=0;b<3;b++)[copy copyFromBuffer:gpu[b] sourceOffset:0 toBuffer:readback[b] destinationOffset:0 size:dataBytes[b]+2*guard];[copy endEncoding];[command commit];[command waitUntilCompleted];result[@"command_status"]=@(command.status);
 if(command.status!=MTLCommandBufferStatusCompleted){result[@"error"]=command.error.description?:@"command failed";emit(result);return 5;}
 uint32_t count=0;memcpy(&count,(unsigned char*)readback[0].contents+guard,4);result[@"invocations"]=@(count);if(count>capacity){result[@"overflow"]=@YES;emit(result);return 10;}
 unsigned guardBad=0,tailBad=0,bad=0;double maxError=0,maxSumError=0;
 for(unsigned b=0;b<3;b++){
  const unsigned char *p=(const unsigned char*)readback[b].contents;
  for(size_t i=0;i<guard;i++)if(p[i]!=0xa5||p[guard+dataBytes[b]+i]!=0xa5)guardBad++;
  if(b)for(size_t i=count*16;i<dataBytes[b];i++)if(p[guard+i]!=0xa5)tailBad++;
 }
 const float *coords=(const float*)((unsigned char*)readback[1].contents+guard),*values=(const float*)((unsigned char*)readback[2].contents+guard);
 NSMutableArray *examples=[NSMutableArray array];
 for(unsigned i=0;i<count;i++){
  double sum=0;for(unsigned c=0;c<3;c++)sum+=coords[i*4+c];maxSumError=std::max(maxSumError,std::abs(sum-1));if(std::abs(sum-1)>2e-7)bad++;
  for(unsigned c=0;c<4;c++){
   double v=coords[i*4+c],expected=c==3?1:v*v;if(nak&&c<3)expected=expected*.5+.125;
   double error=std::abs(values[i*4+c]-expected);maxError=std::max(maxError,error);
   if(!std::isfinite(v)||v<0||v>1||!std::isfinite(values[i*4+c])||error>1e-7||(c==3&&v!=1))bad++;
  }
  if(i<3)[examples addObject:@{@"coord":@[@(coords[i*4]),@(coords[i*4+1]),@(coords[i*4+2])],@"value":@[@(values[i*4]),@(values[i*4+1]),@(values[i*4+2])]}];
 }
 if((factor==0&&count!=0)||(factor>0&&count<3))bad++;
 const char *prefix=getenv("KEPLER_TESS_CAPTURE_PREFIX");if(prefix){for(unsigned b=1;b<3;b++)[[NSData dataWithBytes:(unsigned char*)readback[b].contents+guard length:count*16]writeToFile:[@(prefix) stringByAppendingString:b==1?@".coords.bin":@".values.bin"] atomically:YES];}
 if(prefix)for(unsigned b=0;b<3;b++)[[NSData dataWithBytes:readback[b].contents length:dataBytes[b]+2*guard]writeToFile:[NSString stringWithFormat:@"%s.buffer-%u.bin",prefix,b] atomically:YES];
 result[@"mismatches"]=@(bad);result[@"guard_mismatches"]=@(guardBad);result[@"tail_mismatches"]=@(tailBad);result[@"max_error_vs_cpu_double"]=@(maxError);result[@"max_coordinate_sum_error"]=@(maxSumError);result[@"examples"]=examples;result[@"oracle"]=@"Independent CPU double square per captured coordinate; native tessellator coordinates, no topology oracle";emit(result);return bad||guardBad||tailBad?10:0;
}}
