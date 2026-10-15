#import "KeplerProgramImport.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static const unsigned W=64,H=48;
static NSDictionary* readInfo(NSString*directory,NSString*kind){
 return [NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[directory stringByAppendingPathComponent:[kind stringByAppendingString:@"-info.json"]]] options:0 error:nil];
}
static void emit(NSDictionary*result){NSData*data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];if(data)fwrite(data.bytes,1,data.length,stdout);puts("");}

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=5)return 1;
 NSString*shaderDirectory=@(argv[2]);std::string name=argv[3];bool nak=!strcmp(argv[4],"nak");if(!nak&&strcmp(argv[4],"native"))return 1;
 bool blend=name.rfind("blend-",0)==0,depth=name.rfind("depth-",0)==0,stencil=name.rfind("stencil-",0)==0;
 unsigned samples=1,mask=15,targets=1;
 bool msaa=sscanf(name.c_str(),"msaa%u-mask%u",&samples,&mask)==2;
 bool mrt=sscanf(name.c_str(),"mrt%u",&targets)==1;
 if(mrt&&(targets!=2&&targets!=4&&targets!=8))return 1;
 if(!blend&&!depth&&!stencil&&!msaa&&!mrt&&name!="scissor"&&name!="color-mask"&&name!="cull-front"&&name!="cull-back")return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 if(![device supportsTextureSampleCount:samples]){emit(@{@"case":@(name.c_str()),@"device":device.name,@"supported":@NO,@"samples":@(samples)});return 77;}
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];if(!library){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 MTLPixelFormat format=msaa?MTLPixelFormatRGBA8Unorm:MTLPixelFormatRGBA32Float;
 MTLPixelFormat depthFormat=stencil?MTLPixelFormatDepth32Float_Stencil8:(depth?MTLPixelFormatDepth32Float:MTLPixelFormatInvalid);
 NSMutableArray*evidence=[NSMutableArray array];NSMutableArray*textures=[NSMutableArray array],*resolved=[NSMutableArray array],*buffers=[NSMutableArray array];
 size_t row=W*(msaa?4:16),bytes=row*H;
 for(unsigned i=0;i<targets;i++){
  MTLTextureDescriptor*desc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:format width:W height:H mipmapped:NO];desc.storageMode=MTLStorageModePrivate;desc.usage=MTLTextureUsageRenderTarget;
  id<MTLTexture>resolve=[device newTextureWithDescriptor:desc];if(!resolve)return 4;[resolved addObject:resolve];
  if(msaa){desc.textureType=MTLTextureType2DMultisample;desc.sampleCount=samples;id<MTLTexture>texture=[device newTextureWithDescriptor:desc];if(!texture)return 4;[textures addObject:texture];}
  else [textures addObject:resolve];
  id<MTLBuffer>buffer=KPCreateHostBuffer(device,nullptr,bytes,true);if(!buffer)return 4;[buffers addObject:buffer];
 }
 id<MTLTexture>depthTexture=nil;if(depth||stencil){MTLTextureDescriptor*desc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:depthFormat width:W height:H mipmapped:NO];desc.storageMode=MTLStorageModePrivate;desc.usage=MTLTextureUsageRenderTarget;depthTexture=[device newTextureWithDescriptor:desc];if(!depthTexture)return 4;}
 auto pipeline=[&](NSString*vertex,NSString*fragment,MTLColorWriteMask writeMask)->id<MTLRenderPipelineState>{
  MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.rasterSampleCount=samples;
  NSString*vs=[vertex isEqualToString:@"vertex_near"]?@"vs_near":([vertex isEqualToString:@"vertex_far"]?@"vs_far":([vertex isEqualToString:@"vertex_half"]?@"vs_half":@"vs_state"));
  NSString*fs=[fragment isEqualToString:@"blend"]?@"fs_blend":([fragment isEqualToString:@"constant_red"]?@"fs_red":([fragment hasPrefix:@"mrt"]?[@"fs_" stringByAppendingString:fragment]:([fragment hasPrefix:@"mask"]?@"fs_mask":@"fs_state")));
  desc.vertexFunction=[library newFunctionWithName:vs];desc.fragmentFunction=[library newFunctionWithName:fs];
  // Stencil-only writer has no fragment shader. Import only its vertex stage.
  if(writeMask==MTLColorWriteMaskNone)desc.fragmentFunction=nil;
  desc.depthAttachmentPixelFormat=depthFormat;desc.stencilAttachmentPixelFormat=stencil?depthFormat:MTLPixelFormatInvalid;
  for(unsigned i=0;i<targets;i++){desc.colorAttachments[i].pixelFormat=format;desc.colorAttachments[i].writeMask=writeMask;}
  if(blend){auto attachment=desc.colorAttachments[0];attachment.blendingEnabled=YES;
   attachment.sourceRGBBlendFactor=MTLBlendFactorSourceAlpha;attachment.destinationRGBBlendFactor=MTLBlendFactorOneMinusSourceAlpha;
   attachment.sourceAlphaBlendFactor=MTLBlendFactorOne;attachment.destinationAlphaBlendFactor=MTLBlendFactorOneMinusSourceAlpha;
   MTLBlendOperation operation=MTLBlendOperationAdd;
   if(name=="blend-subtract")operation=MTLBlendOperationSubtract;
   else if(name=="blend-reverse")operation=MTLBlendOperationReverseSubtract;
   else if(name=="blend-min")operation=MTLBlendOperationMin;
   else if(name=="blend-max")operation=MTLBlendOperationMax;
   else if(name=="blend-one-add"){attachment.sourceRGBBlendFactor=attachment.destinationRGBBlendFactor=MTLBlendFactorOne;attachment.destinationAlphaBlendFactor=MTLBlendFactorOne;}
   else if(name=="blend-constant"){attachment.sourceRGBBlendFactor=MTLBlendFactorBlendColor;attachment.destinationRGBBlendFactor=MTLBlendFactorOneMinusBlendColor;attachment.sourceAlphaBlendFactor=MTLBlendFactorBlendAlpha;attachment.destinationAlphaBlendFactor=MTLBlendFactorOneMinusBlendAlpha;}
   else if(name!="blend-add")return nil;
   attachment.rgbBlendOperation=attachment.alphaBlendOperation=operation;
  }
  if(!nak)return [device newRenderPipelineStateWithDescriptor:desc error:&error];
  NSDictionary*vi=readInfo(shaderDirectory,vertex),*fi=readInfo(shaderDirectory,fragment),*entry=nil;
  NSData*vc=[NSData dataWithContentsOfFile:[shaderDirectory stringByAppendingPathComponent:[vertex stringByAppendingString:@".sass"]]];
  NSData*fc=[NSData dataWithContentsOfFile:[shaderDirectory stringByAppendingPathComponent:[fragment stringByAppendingString:@".sass"]]];
  KeplerImportConfig vertexConfig={[vi[@"registers"]unsignedIntValue],0,0};
  id<MTLRenderPipelineState>state=writeMask==MTLColorWriteMaskNone?KPCreateVertexPipeline(device,desc,vc,vertexConfig,&error,&entry):KPCreateGraphicsPipeline(device,desc,vc,vertexConfig,fc,{[fi[@"registers"]unsignedIntValue],0,0},&error,&entry);
  if(entry){NSMutableDictionary*qualified=[entry mutableCopy];qualified[@"requested_stages"]=@(writeMask==MTLColorWriteMaskNone?1:2);qualified[@"vertex_kind"]=vertex;qualified[@"fragment_kind"]=writeMask==MTLColorWriteMaskNone?@"none":fragment;[evidence addObject:qualified];}return state;
 };
 auto depthState=[&](MTLCompareFunction compare,bool write)->id<MTLDepthStencilState>{MTLDepthStencilDescriptor*desc=[MTLDepthStencilDescriptor new];desc.depthCompareFunction=compare;desc.depthWriteEnabled=write;return [device newDepthStencilStateWithDescriptor:desc];};
 auto stencilState=[&](bool write,bool inverse)->id<MTLDepthStencilState>{MTLDepthStencilDescriptor*desc=[MTLDepthStencilDescriptor new];desc.depthCompareFunction=MTLCompareFunctionAlways;MTLStencilDescriptor*s=[MTLStencilDescriptor new];s.stencilCompareFunction=write?MTLCompareFunctionAlways:(inverse?MTLCompareFunctionNotEqual:MTLCompareFunctionEqual);s.depthStencilPassOperation=write?MTLStencilOperationReplace:MTLStencilOperationKeep;s.readMask=255;s.writeMask=write?255:0;desc.frontFaceStencil=desc.backFaceStencil=s;return [device newDepthStencilStateWithDescriptor:desc];};
 std::array<double,4>clear={.125,.25,.5,.75},cyan=nak?std::array<double,4>{.25,.5,.75,1}:std::array<double,4>{.75,.125,.25,1};
 std::array<double,4>red=nak?std::array<double,4>{.875,.25,.125,1}:std::array<double,4>{.25,.875,.5,1};
 if(msaa||stencil)clear={0,0,0,0};
 double clearDepth=1;MTLCompareFunction singleCompare=MTLCompareFunctionAlways;bool singleDepth=false,depthPass=true;
 if(depth&&name!="depth-near-first"&&name!="depth-far-first"&&name!="depth-write-off"){
  singleDepth=true;clearDepth=.25;
  const std::pair<const char*,MTLCompareFunction> comparisons[]={{"depth-never",MTLCompareFunctionNever},{"depth-less",MTLCompareFunctionLess},{"depth-equal",MTLCompareFunctionEqual},{"depth-less-equal",MTLCompareFunctionLessEqual},{"depth-greater",MTLCompareFunctionGreater},{"depth-not-equal",MTLCompareFunctionNotEqual},{"depth-greater-equal",MTLCompareFunctionGreaterEqual},{"depth-always",MTLCompareFunctionAlways}};
  bool found=false;for(auto pair:comparisons)if(name==pair.first){singleCompare=pair.second;found=true;}
  if(!found)return 1;depthPass=singleCompare==MTLCompareFunctionEqual||singleCompare==MTLCompareFunctionLessEqual||singleCompare==MTLCompareFunctionGreaterEqual||singleCompare==MTLCompareFunctionAlways;
 }
 MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];
 for(unsigned i=0;i<targets;i++){auto attachment=pass.colorAttachments[i];attachment.texture=textures[i];attachment.loadAction=MTLLoadActionClear;attachment.clearColor=MTLClearColorMake(clear[0],clear[1],clear[2],clear[3]);attachment.storeAction=msaa?MTLStoreActionMultisampleResolve:MTLStoreActionStore;if(msaa)attachment.resolveTexture=resolved[i];}
 if(depth||stencil){pass.depthAttachment.texture=depthTexture;pass.depthAttachment.loadAction=MTLLoadActionClear;pass.depthAttachment.storeAction=MTLStoreActionStore;pass.depthAttachment.clearDepth=clearDepth;}
 if(stencil){pass.stencilAttachment.texture=depthTexture;pass.stencilAttachment.loadAction=MTLLoadActionClear;pass.stencilAttachment.storeAction=MTLStoreActionStore;pass.stencilAttachment.clearStencil=0;}
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLRenderCommandEncoder>encoder=[command renderCommandEncoderWithDescriptor:pass];if(!encoder)return 5;
 [encoder setViewport:(MTLViewport){0,0,W,H,0,1}];[encoder setCullMode:MTLCullModeNone];[encoder setBlendColorRed:.25 green:.5 blue:.75 alpha:.5];
 bool drawFailed=false;unsigned draws=0;
 auto draw=[&](NSString*vertex,NSString*fragment,MTLColorWriteMask writeMask,id<MTLDepthStencilState>state){id<MTLRenderPipelineState>p=pipeline(vertex,fragment,writeMask);if(!p){drawFailed=true;return;}[encoder setRenderPipelineState:p];if(state)[encoder setDepthStencilState:state];[encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];draws++;};
 if(stencil){[encoder setStencilReferenceValue:7];draw(@"vertex_half",@"constant",MTLColorWriteMaskNone,stencilState(true,false));draw(@"vertex",@"constant",MTLColorWriteMaskAll,stencilState(false,name=="stencil-inverse"));}
 else if(depth&&!singleDepth){bool farFirst=name=="depth-far-first";draw(farFirst?@"vertex_far":@"vertex_near",farFirst?@"constant_red":@"constant",MTLColorWriteMaskAll,depthState(MTLCompareFunctionLess,name!="depth-write-off"));draw(farFirst?@"vertex_near":@"vertex_far",farFirst?@"constant":@"constant_red",MTLColorWriteMaskAll,depthState(MTLCompareFunctionLess,true));}
 else{
  if(name=="scissor")[encoder setScissorRect:(MTLScissorRect){17,9,31,21}];
  if(name=="cull-front"||name=="cull-back"){[encoder setFrontFacingWinding:MTLWindingCounterClockwise];[encoder setCullMode:name=="cull-front"?MTLCullModeFront:MTLCullModeBack];}
  NSString*fragment=blend?@"blend":(mrt?[@"mrt" stringByAppendingFormat:@"%u",targets]:(msaa?[@"mask" stringByAppendingFormat:@"%u",mask]:@"constant"));
  draw(singleDepth?@"vertex_near":@"vertex",fragment,name=="color-mask"?(MTLColorWriteMaskRed|MTLColorWriteMaskBlue):MTLColorWriteMaskAll,singleDepth?depthState(singleCompare,true):nil);
 }
 [encoder endEncoding];if(drawFailed){fprintf(stderr,"%s\n",error.description.UTF8String);emit(@{@"case":@(name.c_str()),@"device":device.name,@"error":error.description?:@"pipeline failure",@"imports":evidence});return 6;}
 id<MTLBlitCommandEncoder>blit=[command blitCommandEncoder];for(unsigned i=0;i<targets;i++)[blit copyFromTexture:resolved[i] sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1) toBuffer:buffers[i] destinationOffset:0 destinationBytesPerRow:row destinationBytesPerImage:bytes];[blit endEncoding];[command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted){fprintf(stderr,"%s\n",command.error.description.UTF8String);return 7;}
 unsigned mismatches=0;double maxError=0;NSMutableArray*first=[NSMutableArray array];unsigned expectedColoredPixels=0;
 for(unsigned target=0;target<targets;target++){
  const uint8_t*data=(const uint8_t*)((id<MTLBuffer>)buffers[target]).contents;NSMutableArray*pixel=[NSMutableArray array];
  for(unsigned y=0;y<H;y++)for(unsigned x=0;x<W;x++){
   std::array<double,4>expected=cyan;bool colored=true;
   if(blend){auto src=nak?std::array<double,4>{.25,.5,.75,.5}:std::array<double,4>{.75,.125,.25,.25};for(unsigned c=0;c<4;c++){
    double sf=c==3?1:src[3],df=1-src[3];
    if(name=="blend-one-add")sf=df=1;
    if(name=="blend-constant"){const double factors[4]={.25,.5,.75,.5};sf=factors[c];df=1-sf;}
    double a=src[c]*sf,b=clear[c]*df;
    expected[c]=name=="blend-min"?std::min(src[c],clear[c]):(name=="blend-max"?std::max(src[c],clear[c]):(name=="blend-subtract"?a-b:(name=="blend-reverse"?b-a:a+b)));
   }}else if(depth){if(name=="depth-write-off")expected=red;else if(singleDepth&&!depthPass){expected=clear;colored=false;}}
   else if(stencil){bool covered=2.*H*(x+.5)<W*(y+.5+H);if(name=="stencil-inverse")covered=!covered;if(!covered){expected=clear;colored=false;}}
   else if(msaa){unsigned actualMask=nak?mask:15;unsigned live=0;for(unsigned s=0;s<samples;s++)if(actualMask&(1u<<s))live++;for(double&v:expected)v*=double(live)/samples;colored=live!=0;}
   else if(mrt&&target){expected=nak?std::array<double,4>{(target+1)/16.,(target+3)/16.,(15-target)/16.,1}:std::array<double,4>{.875,.75,.5,1};}
   else if(name=="scissor"&&(x<17||x>=48||y<9||y>=30)){expected=clear;colored=false;}
   else if(name=="color-mask"){expected[1]=clear[1];expected[3]=clear[3];}
   else if(name=="cull-front"){expected=clear;colored=false;}
   if(target==0&&colored)expectedColoredPixels++;
   for(unsigned c=0;c<4;c++){
    size_t offset=((y*W+x)*4+c);double actual;
    if(msaa){actual=data[offset];double reference=std::lround(expected[c]*255);double delta=std::abs(actual-reference);maxError=std::max(maxError,delta);if(delta>1)mismatches++;}
    else{float value;memcpy(&value,data+offset*4,4);actual=value;double delta=std::abs(actual-expected[c]);maxError=std::max(maxError,delta);if(!std::isfinite(actual)||delta>1e-6)mismatches++;}
    if(!x&&!y)[pixel addObject:@(actual)];
   }
  }[first addObject:pixel];
 }
 emit(@{@"case":@(name.c_str()),@"device":device.name,@"registry_id":@(device.registryID),@"NAK_imported":@(nak),@"supported":@YES,@"samples":@(samples),@"render_targets":@(targets),@"pixels_checked":@(W*H*targets),@"channels_checked":@(W*H*targets*4),@"expected_colored_pixels":@(expectedColoredPixels),@"draws":@(draws),@"mismatched_channels":@(mismatches),@"maximum_error":@(maxError),@"tolerance":@(msaa?1:1e-6),@"target_format":msaa?@"RGBA8Unorm":@"RGBA32Float",@"imports":evidence,@"command_status":@(command.status),@"first_pixels":first,@"requested_color_and_readback_bytes":@(bytes*targets*2+(msaa?W*H*4*samples:0)),@"memory_scope":@"logical allocation sizes; not physical VRAM residency",@"scope":@"application-local NAK stages through installed raster/ROP transport; correctness fixture, no performance benchmark"});
 return mismatches?10:0;
}}
