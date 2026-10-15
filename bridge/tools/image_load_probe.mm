#import "KeplerProgramImport.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
struct Parameters {float scale[4],bias[4];uint32_t shape[4];};
static uint32_t hash32(uint32_t h){h^=h>>16;h*=0x7feb352du;h^=h>>15;h*=0x846ca68bu;return h^(h>>16);}
static double halfValue(uint16_t h){unsigned e=(h>>10)&31,m=h&1023;double value=e==0?std::ldexp(double(m),-24):std::ldexp(1.+m/1024.,int(e)-15);return h&0x8000?-value:value;}
static bool finish(id<MTLCommandBuffer>command){[command commit];[command waitUntilCompleted];return command.status==MTLCommandBufferStatusCompleted;}
static void emit(NSDictionary *d){NSData *j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char **argv){@autoreleasepool{
 if(argc!=11)return 1;NSString *mode=@(argv[4]);std::string fmt=argv[5];unsigned W=(unsigned)strtoul(argv[6],nullptr,10),H=(unsigned)strtoul(argv[7],nullptr,10),variant=(unsigned)strtoul(argv[8],nullptr,10);bool noCopy=!strcmp(argv[9],"nocopy"),nak=[mode isEqualToString:@"nak"],reference=[mode isEqualToString:@"reference"],control=[mode isEqualToString:@"control"];
 if((!nak&&!reference&&!control)||!W||!H||W>256||H>256||variant>1||(!noCopy&&strcmp(argv[9],"managed")))return 1;
 MTLPixelFormat format=MTLPixelFormatInvalid;unsigned pixelBytes=0,rawComponents=0,components=4;
 if(fmt=="rgba32f"){format=MTLPixelFormatRGBA32Float;pixelBytes=16;rawComponents=4;}
 else if(fmt=="rgba16f"){format=MTLPixelFormatRGBA16Float;pixelBytes=8;rawComponents=2;}
 else if(fmt=="rgba8"){format=MTLPixelFormatRGBA8Unorm;pixelBytes=4;rawComponents=1;}
 else if(fmt=="r32f"){format=MTLPixelFormatR32Float;pixelBytes=4;rawComponents=1;components=1;}
 else return 1;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSError *error=nil;NSDictionary *evidence=nil;id<MTLComputePipelineState>pipeline=nil;
 if(nak){NSDictionary *info=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[3])] options:0 error:nil];if(!info||[info[@"sm"]unsignedIntValue]!=30)return 1;pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],@"surface_load_carrier",[NSData dataWithContentsOfFile:@(argv[2])],{[info[@"registers"]unsignedIntValue],576,576},&error,&evidence);}
 else{id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];pipeline=[device newComputePipelineStateWithFunction:[library newFunctionWithName:reference?@"image_read_reference":@"surface_load_carrier"] error:&error];}
 if(!pipeline){emit(@{@"pipeline_created":@NO,@"error":error.description?:@"no pipeline",@"import":evidence?:@{}});return 3;}
 const unsigned OW=W+(variant?2:0),OH=H+(variant?2:0);const size_t row=(W*pixelBytes+255)&~size_t(255),texBytes=row*H,count=OW*OH,guard=64,outputBytes=count*16+2*guard;
 std::vector<unsigned char>source(texBytes,0xee),initial(outputBytes,0xa5);std::vector<double>decoded(W*H*4,0);
 for(unsigned y=0;y<H;y++)for(unsigned x=0;x<W;x++){
  size_t pixel=y*W+x,offset=y*row+x*pixelBytes;decoded[pixel*4+3]=1;
  for(unsigned c=0;c<components;c++){
   uint32_t h=hash32(unsigned(pixel*4+c)+0x185f39a5u);
   if(fmt=="rgba8"){uint8_t value=(uint8_t)h;source[offset+c]=value;decoded[pixel*4+c]=double(value)/255;}
   else if(fmt=="rgba16f"){uint16_t value=(uint16_t)((h&0x8000)|0x3800|(h&0x7ff));memcpy(source.data()+offset+c*2,&value,2);decoded[pixel*4+c]=halfValue(value);}
   else{float value=float(int(h&2047)-1024)/256.f;memcpy(source.data()+offset+c*4,&value,4);decoded[pixel*4+c]=value;}
  }
 }
 MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:format width:W height:H mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;id<MTLTexture>texture=[device newTextureWithDescriptor:td];
 id<MTLBuffer>uploadHost=KPCreateHostBuffer(device,source.data(),texBytes,noCopy),output=[device newBufferWithLength:outputBytes options:MTLResourceStorageModePrivate],rawOutput=[device newBufferWithLength:outputBytes options:MTLResourceStorageModePrivate];
 id<MTLBuffer>outHost=KPCreateHostBuffer(device,initial.data(),outputBytes,noCopy),rawHost=KPCreateHostBuffer(device,initial.data(),outputBytes,noCopy);
 if(!texture||!uploadHost||!output||!rawOutput||!outHost||!rawHost)return 4;
 Parameters p={{.5,-1.5,2,.25},{.125,-.25,.5,-.75},{OW,OH,variant?UINT32_MAX:0,variant?UINT32_MAX:0}};
 id<MTLBuffer>params=[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];id<MTLCommandQueue>queue=[device newCommandQueue];if(!params||!queue)return 4;
 id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>copy=[upload blitCommandEncoder];[copy copyFromBuffer:uploadHost sourceOffset:0 sourceBytesPerRow:row sourceBytesPerImage:texBytes sourceSize:MTLSizeMake(W,H,1) toTexture:texture destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];[copy copyFromBuffer:outHost sourceOffset:0 toBuffer:output destinationOffset:0 size:outputBytes];[copy copyFromBuffer:rawHost sourceOffset:0 toBuffer:rawOutput destinationOffset:0 size:outputBytes];[copy endEncoding];if(!finish(upload))return 5;
 id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];[encoder setTexture:texture atIndex:0];[encoder setBuffer:params offset:0 atIndex:3];[encoder setBuffer:output offset:guard atIndex:7];[encoder setBuffer:rawOutput offset:guard atIndex:8];[encoder useResource:texture usage:MTLResourceUsageRead|MTLResourceUsageWrite];[encoder dispatchThreadgroups:MTLSizeMake((OW+3)/4,(OH+7)/8,1) threadsPerThreadgroup:MTLSizeMake(4,8,1)];[encoder endEncoding];if(!finish(command)){emit(@{@"command_status":@(command.status),@"error":command.error.description?:@"command failed"});return 6;}
 id<MTLCommandBuffer>read=[queue commandBuffer];copy=[read blitCommandEncoder];[copy copyFromBuffer:output sourceOffset:0 toBuffer:outHost destinationOffset:0 size:outputBytes];[copy copyFromBuffer:rawOutput sourceOffset:0 toBuffer:rawHost destinationOffset:0 size:outputBytes];if(!noCopy){[copy synchronizeResource:outHost];[copy synchronizeResource:rawHost];}[copy endEncoding];if(!finish(read))return 7;
 const float *out=(const float*)((unsigned char*)outHost.contents+guard);const uint32_t *raw=(const uint32_t*)((unsigned char*)rawHost.contents+guard);unsigned bad=0,rawBad=0,guardBad=0,oobPixels=0;double maxError=0;
 for(unsigned y=0;y<OH;y++)for(unsigned x=0;x<OW;x++){
  int sx=int(x)-(variant?1:0),sy=int(y)-(variant?1:0);bool inside=sx>=0&&sy>=0&&sx<int(W)&&sy<int(H);size_t i=y*OW+x;if(!inside)oobPixels++;
  for(unsigned c=0;c<4;c++){
   double v=inside?decoded[(sy*W+sx)*4+c]:0,expected=control?(double((float[]){.25,.5,.75,1}[c])+p.bias[c]):v*p.scale[c]+p.bias[c];
   double difference=std::abs(double(out[i*4+c])-expected);maxError=std::max(maxError,difference);if(!std::isfinite(out[i*4+c])||difference>2e-6)bad++;
   if(nak){uint32_t expectedRaw=0;if(inside&&c<rawComponents)memcpy(&expectedRaw,source.data()+sy*row+sx*pixelBytes+c*4,4);if(raw[i*4+c]!=expectedRaw)rawBad++;}
   else if(control){uint32_t marker[]={0x1234,0x5678,0xabcd,0xeffe};if(raw[i*4+c]!=marker[c])rawBad++;}
   else if(raw[i*4+c]!=0xa5a5a5a5u)rawBad++;
  }
 }
 for(size_t i=0;i<outputBytes;i++)if(i<guard||i>=guard+count*16){if(((unsigned char*)outHost.contents)[i]!=0xa5)guardBad++;if(((unsigned char*)rawHost.contents)[i]!=0xa5)guardBad++;}
 NSString *prefix=@(argv[10]);[[NSData dataWithBytes:source.data() length:texBytes]writeToFile:[prefix stringByAppendingString:@".source.bin"] atomically:YES];[[NSData dataWithBytes:outHost.contents length:outputBytes]writeToFile:[prefix stringByAppendingString:@".output.bin"] atomically:YES];[[NSData dataWithBytes:rawHost.contents length:outputBytes]writeToFile:[prefix stringByAppendingString:@".raw.bin"] atomically:YES];
 emit(@{@"device":device.name,@"registry_id":@(device.registryID),@"mode":mode,@"format":@(fmt.c_str()),@"texture_shape":@[@(W),@(H)],@"output_shape":@[@(OW),@(OH)],@"variant":@(variant),@"staging":noCopy?@"nocopy":@"managed",@"input_bytes_per_row":@(row),@"pixel_bytes":@(pixelBytes),@"pixels_checked":@(count),@"out_of_bounds_pixels":@(oobPixels),@"mismatches":@(bad),@"raw_mismatches":@(rawBad),@"guard_mismatches":@(guardBad),@"maximum_float_error":@(maxError),@"command_status":@(command.status),@"import":evidence?:@{},@"first_pixel":@[@(out[0]),@(out[1]),@(out[2]),@(out[3])],@"scope":@"surface load through a write-carrier metadata profile; explicit raw format unpack; native read reference uses separate shader; no new read_write API tier or performance benchmark"});return bad||rawBad||guardBad?10:0;
}}
