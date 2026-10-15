#import "KeplerProgramImport.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
int main(int argc,char**argv){@autoreleasepool{
 if(argc<2||argc>5)return 1;bool imported=argc>=4,floatTarget=(argc==3||argc==5)&&!strcmp(argv[argc-1],"float");
 NSDictionary*shaderInfo=imported?[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[3])] options:0 error:nil]:nil;
 bool halfGeometry=imported&&[shaderInfo[@"kind"] isEqualToString:@"vertex_half"],nakVertex=imported&&([shaderInfo[@"kind"] isEqualToString:@"vertex"]||halfGeometry),nakRead=imported&&[shaderInfo[@"kind"] isEqualToString:@"read"],nakNearest=imported&&[shaderInfo[@"kind"] isEqualToString:@"nearest"],nakLinear=imported&&[shaderInfo[@"kind"] isEqualToString:@"linear"];
 const char*vertexPath=getenv("KEPLER_VERTEX_CODE"),*vertexInfoPath=getenv("KEPLER_VERTEX_INFO");bool both=imported&&vertexPath&&vertexInfoPath;
 NSDictionary*vertexInfo=both?[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(vertexInfoPath)] options:0 error:nil]:nil;
 if(both)halfGeometry=[vertexInfo[@"kind"] isEqualToString:@"vertex_half"];
 const unsigned width=64,height=48;const size_t inputRow=width*4,bytesPerRow=width*(floatTarget?16:4),bytes=bytesPerRow*height;
 MTLPixelFormat targetFormat=floatTarget?MTLPixelFormatRGBA32Float:MTLPixelFormatRGBA8Unorm;
 std::vector<uint8_t>pixels(inputRow*height);for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++){
  size_t i=(y*width+x)*4;pixels[i]=(x*3+y*5)&255;pixels[i+1]=(x*7+y*11)&255;pixels[i+2]=(x^y)&255;pixels[i+3]=255;
 }
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 MTLTextureDescriptor*inputDesc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:width height:height mipmapped:NO];inputDesc.storageMode=MTLStorageModeManaged;inputDesc.usage=MTLTextureUsageShaderRead;
 id<MTLTexture>input=[device newTextureWithDescriptor:inputDesc];if(!input)return 4;[input replaceRegion:MTLRegionMake2D(0,0,width,height) mipmapLevel:0 withBytes:pixels.data() bytesPerRow:inputRow];
 MTLTextureDescriptor*targetDesc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:targetFormat width:width height:height mipmapped:NO];targetDesc.storageMode=MTLStorageModePrivate;targetDesc.usage=MTLTextureUsageRenderTarget;
 id<MTLTexture>target=[device newTextureWithDescriptor:targetDesc];id<MTLBuffer>readback=KPCreateHostBuffer(device,nullptr,bytes,true);id<MTLCommandQueue>queue=[device newCommandQueue];if(!target||!readback||!queue)return 4;
 NSMutableArray*tests=[NSMutableArray array];unsigned totalBad=0;
 for(NSString*name in (imported?@[nakRead?@"fs_read":(nakNearest?@"fs_nearest":(nakLinear?@"fs_linear":@"fs_const"))]:@[@"fs_const",@"fs_match",@"fs_read",@"fs_nearest",@"fs_linear"])){@autoreleasepool{
  MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.vertexFunction=[library newFunctionWithName:@"vs_ref"];desc.fragmentFunction=[library newFunctionWithName:name];desc.colorAttachments[0].pixelFormat=targetFormat;
  NSDictionary*importEvidence=nil;id<MTLRenderPipelineState>pipeline=nil;
  if(imported){@autoreleasepool{KeplerImportConfig config={[shaderInfo[@"registers"] unsignedIntValue],0,0};if(both)pipeline=KPCreateGraphicsPipeline(device,desc,[NSData dataWithContentsOfFile:@(vertexPath)],{[vertexInfo[@"registers"] unsignedIntValue],0,0},[NSData dataWithContentsOfFile:@(argv[2])],config,&error,&importEvidence);else pipeline=nakVertex?KPCreateVertexPipeline(device,desc,[NSData dataWithContentsOfFile:@(argv[2])],config,&error,&importEvidence):KPCreateRenderPipeline(device,desc,[NSData dataWithContentsOfFile:@(argv[2])],config,&error,&importEvidence);[error retain];[importEvidence retain];}}
  else pipeline=[device newRenderPipelineStateWithDescriptor:desc error:&error];if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 5;}
  MTLSamplerDescriptor*samplerDesc=[MTLSamplerDescriptor new];bool linear=[name isEqualToString:@"fs_linear"];samplerDesc.minFilter=linear?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;samplerDesc.magFilter=samplerDesc.minFilter;samplerDesc.sAddressMode=MTLSamplerAddressModeClampToEdge;samplerDesc.tAddressMode=MTLSamplerAddressModeClampToEdge;
  id<MTLSamplerState>sampler=[device newSamplerStateWithDescriptor:samplerDesc];
  MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);pass.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLRenderCommandEncoder>encoder=[command renderCommandEncoderWithDescriptor:pass];[encoder setRenderPipelineState:pipeline];[encoder setViewport:(MTLViewport){0,0,width,height,0,1}];[encoder setCullMode:MTLCullModeNone];[encoder setFragmentTexture:input atIndex:0];[encoder setFragmentSamplerState:sampler atIndex:0];[encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[encoder endEncoding];
  id<MTLBlitCommandEncoder>blit=[command blitCommandEncoder];[blit copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(width,height,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:bytesPerRow destinationBytesPerImage:bytes];[blit endEncoding];[command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"%s\n",command.error.description.UTF8String);return 6;}
  const uint8_t*out=(const uint8_t*)readback.contents;unsigned bad=0,maxError=0;double maxFloatError=0,maxIdealError=0;
  const char*pixelDirectory=getenv("KEPLER_RENDER_OUTPUT_DIR");if(pixelDirectory){NSString*directory=@(pixelDirectory);[[NSFileManager defaultManager]createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:nil error:nil];NSString*file=[NSString stringWithFormat:@"%@-%@-%@.bin",name,floatTarget?@"float":@"unorm",imported?@"nak":@"native"];[[NSData dataWithBytes:out length:bytes]writeToFile:[directory stringByAppendingPathComponent:file] atomically:YES];}
  bool sameColor=(imported&&!nakVertex&&!nakRead&&!nakNearest&&!nakLinear)||[name isEqualToString:@"fs_match"],constant=[name isEqualToString:@"fs_const"]||[name isEqualToString:@"fs_match"];
  for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++)for(unsigned c=0;c<4;c++){
   unsigned expected=0;if(constant){const uint8_t nativeColor[4]={191,32,64,255},nakColor[4]={64,128,191,255};expected=sameColor?nakColor[c]:nativeColor[c];}
   else if(linear){unsigned x1=std::min(x+1,width-1),y1=std::min(y+1,height-1);double value=pixels[(y*width+x)*4+c]*.75*.875+pixels[(y*width+x1)*4+c]*.25*.875+pixels[(y1*width+x)*4+c]*.75*.125+pixels[(y1*width+x1)*4+c]*.25*.125;expected=(unsigned)std::lround(value);}
   else expected=pixels[(y*width+x)*4+c];
   bool covered=!halfGeometry||2.*height*(x+.5)<width*(y+.5+height);if(!covered)expected=0;
   if(floatTarget){double reference=double(expected)/255.;if(constant){const float nativeColor[4]={.75f,.125f,.25f,1.f},nakColor[4]={.25f,.5f,.75f,1.f};reference=sameColor?nakColor[c]:nativeColor[c];}
    else if(linear){unsigned x1=std::min(x+1,width-1),y1=std::min(y+1,height-1);reference=(pixels[(y*width+x)*4+c]*.75*.875+pixels[(y*width+x1)*4+c]*.25*.875+pixels[(y1*width+x)*4+c]*.75*.125+pixels[(y1*width+x1)*4+c]*.25*.125)/255.;}
    if(!covered)reference=0;
    float actual;memcpy(&actual,out+((y*width+x)*4+c)*4,4);maxIdealError=std::max(maxIdealError,std::abs(double(actual)-reference));
    if(linear)reference=std::nearbyint(reference*65535.)/65535.;
    double error=std::abs(double(actual)-reference);maxFloatError=std::max(maxFloatError,error);if(!std::isfinite(actual)||error>(constant?0:(linear?1e-7:1e-6)))bad++;
   }else{unsigned delta=(unsigned)std::abs(int(out[(y*width+x)*4+c])-int(expected));maxError=std::max(maxError,delta);if(delta>((linear||sameColor)?1:0))bad++;}
  }
  NSMutableArray*first=[NSMutableArray array];for(unsigned c=0;c<4;c++){if(floatTarget){float value;memcpy(&value,out+c*4,4);[first addObject:@(value)];}else[first addObject:@(out[c])];}
  unsigned coveredPixels=0;for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++)if(!halfGeometry||2.*height*(x+.5)<width*(y+.5+height))coveredPixels++;
  totalBad+=bad;[tests addObject:@{@"fragment":name,@"pixels":@(width*height),@"cpu_expected_covered_pixels":@(coveredPixels),@"cpu_expected_clear_pixels":@(width*height-coveredPixels),@"mismatched_channels":@(bad),@"maximum_channel_error":@(maxError),@"maximum_float_error":@(maxFloatError),@"maximum_error_vs_ideal_float":@(maxIdealError),@"linear_oracle":linear?@"UNorm16 nearest-even model established separately on this fixture":@"not applicable",@"tolerance_lsb":@((linear||sameColor)?1:0),@"tolerance_float":@(constant?0:(linear?1e-7:1e-6)),@"gpu_seconds":@(command.GPUEndTime-command.GPUStartTime),@"command_status":@(command.status),@"import":importEvidence?:@{},@"first_pixel":first}];
 }}
 NSDictionary*result=@{@"device":device.name,@"registry_id":@(device.registryID),@"tests":tests,@"mismatched_channels":@(totalBad),@"NAK_fragment_imported":@(imported&&!nakVertex),@"NAK_vertex_imported":@(nakVertex||both),@"half_geometry":@(halfGeometry),@"target_format":floatTarget?@"RGBA32Float":@"RGBA8Unorm",@"scope":imported?@"NAK SM30 graphics stage executed with installed render driver":@"offscreen raster and texture reference through installed driver; GPU timing diagnostic only"};NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(json)fwrite(json.bytes,1,json.length,stdout);putchar('\n');return totalBad?10:0;
}}
