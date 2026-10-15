#import "KeplerProgramImport.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
struct Parameters {float scale[4],bias[4];uint32_t shape[4];};
static void emit(NSDictionary*d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");}
static double halfValue(uint16_t h){unsigned e=(h>>10)&31,m=h&1023;return e==0?std::ldexp(double(m),-24):(e==31?(m?NAN:INFINITY):std::ldexp(1.+m/1024.,int(e)-15));}
static double roundedHalf(double v){if(v==0)return 0;int e=0;std::frexp(v,&e);double step=std::ldexp(1.,std::max(e-11,-24));return std::nearbyint(v/step)*step;}
static double truncatedHalf(double v){if(v==0)return 0;int e=0;std::frexp(v,&e);double step=std::ldexp(1.,std::max(e-11,-24));return std::trunc(v/step)*step;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=11&&argc!=14)return 1;NSString*directory=@(argv[2]);std::string kind=argv[3],mode=argv[4],memory=argv[5],formatName=argv[9];
 unsigned W=(unsigned)strtoul(argv[6],nullptr,10),H=(unsigned)strtoul(argv[7],nullptr,10),D=(unsigned)strtoul(argv[8],nullptr,10);bool nak=mode=="nak",image=kind=="image";
 // argv10 is a parameter variant, allowing uniforms to change without recompilation.
 unsigned variant=(unsigned)strtoul(argv[10],nullptr,10);
 unsigned gx=argc==14?(unsigned)strtoul(argv[11],nullptr,10):4,gy=argc==14?(unsigned)strtoul(argv[12],nullptr,10):8,gz=argc==14?(unsigned)strtoul(argv[13],nullptr,10):1;
 if((!nak&&mode!="native")||(kind!="buffers_a"&&kind!="buffers_b"&&!image)||!W||!H||!D||W*uint64_t(H)*D>1048576||variant>1)return 1;
 if(memory!="managed"&&memory!="nocopy"&&memory!="private")return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSError*error=nil;NSDictionary*evidence=nil;NSString*function=image?@"image_store":@(kind.c_str());id<MTLComputePipelineState>pipeline=nil;
 if(nak){NSDictionary*info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[directory stringByAppendingPathComponent:[@(kind.c_str()) stringByAppendingString:@"-info.json"]]] options:0 error:nil];NSData*code=[NSData dataWithContentsOfFile:[directory stringByAppendingPathComponent:[@(kind.c_str()) stringByAppendingString:@".sass"]]];pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],function,code,{[info[@"registers"]unsignedIntValue],576,576},&error,&evidence);}
 else{id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];pipeline=[device newComputePipelineStateWithFunction:[library newFunctionWithName:function] error:&error];}
 if(!pipeline){emit(@{@"error":error.description?:@"pipeline failed",@"import":evidence?:@{}});return 3;}
 MTLSize limits=device.maxThreadsPerThreadgroup;if(!gx||!gy||!gz||gx>limits.width||gy>limits.height||gz>limits.depth||uint64_t(gx)*gy*gz>pipeline.maxTotalThreadsPerThreadgroup){emit(@{@"error":@"unsupported local group",@"maximum_threads":@(pipeline.maxTotalThreadsPerThreadgroup)});return 4;}
 const size_t count=size_t(W)*H*D;bool noCopy=memory!="managed";
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];
 id<MTLBuffer>input=nil,output=nil,params=nil,readback=nil,inputStage=nil,outputStage=nil;
 id<MTLTexture>texture=nil;size_t row=0,bytes=0,components=4,pixelBytes=16;
 std::vector<float>inputData,initial;std::vector<uint8_t>imageInitial;
 Parameters p={{.5,-1.5,2,.25},{.125,-.25,.5,1},{W,H,D,(uint32_t)count}};
 if(variant){const float scale[]={-2,.125,1.5,-.5},bias[]={.75,.5,-.125,.25};memcpy(p.scale,scale,sizeof scale);memcpy(p.bias,bias,sizeof bias);}
 if(!image){
  inputData.resize(count*4+64,.0f);initial.resize(count*4+32,-8192.25f);
  for(size_t i=0;i<inputData.size();i++){uint32_t h=(uint32_t)i*0x9e3779b9u;h^=h>>16;h*=0x85ebca6bu;h^=h>>13;inputData[i]=float(int(h&63)-32)/32;}
  inputStage=KPCreateHostBuffer(device,inputData.data(),inputData.size()*4,noCopy);outputStage=KPCreateHostBuffer(device,initial.data(),initial.size()*4,noCopy);readback=KPCreateHostBuffer(device,nullptr,initial.size()*4,noCopy);
  if(memory=="private"){input=[device newBufferWithLength:inputData.size()*4 options:MTLResourceStorageModePrivate];output=[device newBufferWithLength:initial.size()*4 options:MTLResourceStorageModePrivate];id<MTLBlitCommandEncoder>copy=[command blitCommandEncoder];[copy copyFromBuffer:inputStage sourceOffset:0 toBuffer:input destinationOffset:0 size:inputData.size()*4];[copy copyFromBuffer:outputStage sourceOffset:0 toBuffer:output destinationOffset:0 size:initial.size()*4];[copy endEncoding];}
  else {input=inputStage;output=outputStage;}
  params=KPCreateHostBuffer(device,&p,sizeof p,noCopy);if(!input||!output||!params||!readback)return 4;
 }else{
  if(D!=1)return 1;MTLPixelFormat format=MTLPixelFormatInvalid;
  if(formatName=="rgba32f")format=MTLPixelFormatRGBA32Float;
  else if(formatName=="rgba16f"){format=MTLPixelFormatRGBA16Float;pixelBytes=8;}
  else if(formatName=="rgba8"){format=MTLPixelFormatRGBA8Unorm;pixelBytes=4;}
  else if(formatName=="r32f"){format=MTLPixelFormatR32Float;pixelBytes=4;components=1;}
  else return 1;
  MTLTextureDescriptor*desc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:format width:W height:H mipmapped:NO];desc.storageMode=MTLStorageModePrivate;desc.usage=MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead;texture=[device newTextureWithDescriptor:desc];if(!texture)return 4;
  row=(W*pixelBytes+255)&~size_t(255);bytes=row*H;imageInitial.resize(bytes+64,0xad);readback=KPCreateHostBuffer(device,imageInitial.data(),imageInitial.size(),noCopy);
 }
 id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];
 if(image)[encoder setTexture:texture atIndex:0];else{unsigned in=kind=="buffers_a"?0:5,out=kind=="buffers_a"?7:2,uniform=kind=="buffers_a"?3:11;[encoder setBuffer:input offset:128 atIndex:in];[encoder setBuffer:output offset:64 atIndex:out];[encoder setBuffer:params offset:0 atIndex:uniform];}
 [encoder dispatchThreadgroups:MTLSizeMake((W+gx-1)/gx,(H+gy-1)/gy,(D+gz-1)/gz) threadsPerThreadgroup:MTLSizeMake(gx,gy,gz)];[encoder endEncoding];
 id<MTLBlitCommandEncoder>copy=[command blitCommandEncoder];if(image)[copy copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:row destinationBytesPerImage:bytes];else [copy copyFromBuffer:output sourceOffset:0 toBuffer:readback destinationOffset:0 size:initial.size()*4];if(!noCopy)[copy synchronizeResource:readback];[copy endEncoding];[command commit];[command waitUntilCompleted];
 if(command.status!=MTLCommandBufferStatusCompleted){emit(@{@"error":command.error.description?:@"command failed"});return 5;}
 unsigned mismatches=0,guards=0,halfNearestMismatches=0,halfTruncationMismatches=0;double maxError=0;NSMutableArray*first=[NSMutableArray array];
 if(!image){const float*actual=(const float*)readback.contents;for(size_t i=0;i<count;i++)for(unsigned c=0;c<4;c++){
   double expected=double(inputData[32+i*4+c])*p.scale[c]+p.bias[c]+(nak?(c+1)/8.:0);double value=actual[16+i*4+c],error=std::abs(value-expected);maxError=std::max(maxError,error);if(!std::isfinite(value)||error>1e-6)mismatches++;if(!i)[first addObject:@(value)];}
  for(unsigned i=0;i<16;i++)if(actual[i]!=initial[i])guards++;for(size_t i=16+count*4;i<initial.size();i++)if(actual[i]!=initial[i])guards++;
 }else{const uint8_t*data=(const uint8_t*)readback.contents;for(unsigned y=0;y<H;y++)for(unsigned x=0;x<W;x++)for(unsigned c=0;c<components;c++){
   const double expectedValues[]={(x+(nak?5:0))/64.,(y+(nak?3:0))/48.,nak?.75:.25,1};double expected=expectedValues[c],actual=0,tolerance=1e-6;
   size_t offset=y*row+x*pixelBytes;
   if(formatName=="rgba8"){actual=data[offset+c];expected=std::lround(std::clamp(expected,0.,1.)*255);tolerance=1;}
   else if(formatName=="rgba16f"){uint16_t h;memcpy(&h,data+offset+c*2,2);actual=halfValue(h);if(actual!=roundedHalf(expected))halfNearestMismatches++;if(actual!=truncatedHalf(expected))halfTruncationMismatches++;expected=truncatedHalf(expected);tolerance=0;}
   else{float v;memcpy(&v,data+offset+c*4,4);actual=v;}
   double error=std::abs(actual-expected);maxError=std::max(maxError,error);if(!std::isfinite(actual)||error>tolerance)mismatches++;if(!x&&!y)[first addObject:@(actual)];
  }for(size_t i=bytes;i<imageInitial.size();i++)if(data[i]!=imageInitial[i])guards++;
 }
 emit(@{@"device":device.name,@"registry_id":@(device.registryID),@"kind":@(kind.c_str()),@"mode":@(mode.c_str()),@"memory":@(memory.c_str()),@"format":@(formatName.c_str()),@"shape":@[@(W),@(H),@(D)],@"local_size":@[@(gx),@(gy),@(gz)],@"maximum_threadgroup_threads":@(pipeline.maxTotalThreadsPerThreadgroup),@"half_conversion_model":formatName=="rgba16f"?@"observed positive-value truncation toward zero":@"not applicable",@"uniform_variant":@(variant),@"values_checked":@(count*(image?components:4)),@"mismatches":@(mismatches),@"changed_guards":@(guards),@"maximum_error":@(maxError),@"half_nearest_model_mismatches":@(halfNearestMismatches),@"half_truncation_model_mismatches":@(halfTruncationMismatches),@"first_value":first,@"command_status":@(command.status),@"import":evidence?:@{},@"scope":@"observed CB1/CB2 resource ABI and SM30 surface store; CPU numeric fixture, no performance benchmark"});return mismatches||guards?10:0;
}}
