#import "KeplerProgramImport.h"
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
struct Vertex {float p[4],c[4];};
struct Offset {float v[4];};
struct Parameters {uint64_t addresses[4];uint32_t grid[3],block[3];};
struct ReferenceVertex {double x,y,w;std::array<double,4>color;};
static NSDictionary*info(NSString*d,NSString*k){return [NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[d stringByAppendingPathComponent:[k stringByAppendingString:@"-info.json"]]] options:0 error:nil];}
static NSData*code(NSString*d,NSString*k){return [NSData dataWithContentsOfFile:[d stringByAppendingPathComponent:[k stringByAppendingString:@".sass"]]];}
static void emit(NSDictionary*d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];if(j)fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=7)return 1;NSString*directory=@(argv[2]),*interpolation=@(argv[3]);std::string draw=argv[4],mode=argv[5],memory=argv[6];
 if(![interpolation isEqualToString:@"smooth"]&&![interpolation isEqualToString:@"linear"]&&![interpolation isEqualToString:@"flat"])return 1;
 bool nakV=mode=="vertex"||mode=="both",nakF=mode=="fragment"||mode=="both";if(!nakV&&!nakF&&mode!="native")return 1;
 bool indexed=draw=="indexed16"||draw=="indexed32"||draw=="base-vertex"||draw=="negative-base-vertex"||draw=="indirect-indexed";
 bool indirect=draw=="indirect"||draw=="indirect-indexed"||draw=="indirect-control";
 bool emptyControl=draw=="indirect-control";
 bool instanced=draw=="instanced"||draw=="base-instance"||indirect;
 if(!indexed&&!indirect&&!instanced&&draw!="direct"&&draw!="vertex-start")return 1;
 const unsigned W=64,H=48;unsigned instances=instanced?2:1,baseInstance=(draw=="base-instance"||indirect)?3:0;
 int baseVertex=draw=="base-vertex"||draw=="indirect-indexed"?2:(draw=="negative-base-vertex"?-2:0);
 unsigned prefix=(baseVertex!=0)?2:(draw=="vertex-start"?5:0),vertexStart=draw=="vertex-start"?5:0;
 bool index32=draw=="indexed32";unsigned indexStart=draw=="indirect-indexed"?3:0,indexByteOffset=indexed?16:0,indexPrefix=indexed?(indexByteOffset/(index32?4:2)+indexStart):0;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];if(!library)return 3;
 const float xLeft=-1,xRight=instanced?0:1;
 const float xy[4][2]={{xLeft,-1},{xRight,-1},{xLeft,1},{xRight,1}};
 const float colors[4][4]={{.25,.125,.75,1},{.75,.25,.5,1},{.125,.75,.25,1},{.5,.5,.875,1}};
 const float ws[4]={.5,1,2,1};std::array<Vertex,4>corners;
 for(unsigned i=0;i<4;i++){float w=ws[i];corners[i]={{xy[i][0]*w,xy[i][1]*w,.5f*w,w},{colors[i][0],colors[i][1],colors[i][2],colors[i][3]}};}
 const unsigned order[6]={0,1,2,2,1,3};std::vector<Vertex>vertices(prefix,Vertex{{0,0,0,1},{.875,.0625,.9375,1}});
 std::vector<uint32_t>indices(indexPrefix,0);
 if(indexed){const unsigned packed[4]={3,1,0,2},mapping[4]={2,1,3,0};for(unsigned i:packed)vertices.push_back(corners[i]);for(unsigned i:order)indices.push_back(mapping[i]+prefix-baseVertex);}
 else for(unsigned i:order)vertices.push_back(corners[i]);
 // Keep wrong base/index offsets inside allocated storage for diagnostic failures.
 for(unsigned i=0;i<8;i++)vertices.push_back(Vertex{{0,0,0,1},{.875,.0625,.9375,1}});
 std::vector<Offset>offsets(8);for(unsigned i=0;i<offsets.size();i++)offsets[i]={{0,0,float(i)/64,0}};
 if(instanced){offsets[baseInstance].v[0]=0;offsets[baseInstance+1].v[0]=1;}
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLBlitCommandEncoder>upload=[command blitCommandEncoder];
 NSMutableArray*retained=[NSMutableArray array];
 auto buffer=[&](const void*data,size_t bytes)->id<MTLBuffer>{
  bool noCopy=memory=="nocopy"||memory=="private";id<MTLBuffer>stage=KPCreateHostBuffer(device,data,bytes,noCopy);if(!stage)return nil;[retained addObject:stage];
  if(memory!="private")return stage;id<MTLBuffer>gpu=[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate];if(gpu){[retained addObject:gpu];[upload copyFromBuffer:stage sourceOffset:0 toBuffer:gpu destinationOffset:0 size:bytes];}return gpu;
 };
 if(memory!="managed"&&memory!="nocopy"&&memory!="private")return 1;
 id<MTLBuffer>vbo=buffer(vertices.data(),vertices.size()*sizeof(Vertex)),instanceBuffer=buffer(offsets.data(),offsets.size()*sizeof(Offset)),indexBuffer=nil;
 if(indexed){if(index32)indexBuffer=buffer(indices.data(),indices.size()*4);else{std::vector<uint16_t>small(indices.begin(),indices.end());indexBuffer=buffer(small.data(),small.size()*2);}}
 if(!vbo||!instanceBuffer||(indexed&&!indexBuffer))return 4;
 uint32_t args[8]={};unsigned argumentCount=indexed?5:4;
 if(indexed){args[0]=6;args[1]=instances;args[2]=indexStart;memcpy(args+3,&baseVertex,4);args[4]=baseInstance;}
 else{args[0]=6;args[1]=instances;args[2]=vertexStart;args[3]=baseInstance;}
 uint32_t initial[8],seeds[8];for(unsigned i=0;i<8;i++){initial[i]=i<argumentCount?0:0xc0fe24b1;seeds[i]=args[i]^0x5a5a5a5a;}
 id<MTLBuffer>argumentBuffer=nil,argumentReadback=nil,seedBuffer=nil,parameters=nil;
 if(indirect){
  id<MTLBuffer>initialStage=KPCreateHostBuffer(device,initial,sizeof initial,true);argumentBuffer=[device newBufferWithLength:sizeof initial options:MTLResourceStorageModePrivate];argumentReadback=KPCreateHostBuffer(device,nullptr,sizeof initial,true);
  id<MTLBuffer>seedStage=KPCreateHostBuffer(device,seeds,sizeof seeds,true);seedBuffer=[device newBufferWithLength:sizeof seeds options:MTLResourceStorageModePrivate];
  if(!initialStage||!argumentBuffer||!argumentReadback||!seedStage||!seedBuffer)return 4;
  [upload copyFromBuffer:initialStage sourceOffset:0 toBuffer:argumentBuffer destinationOffset:0 size:sizeof initial];[upload copyFromBuffer:seedStage sourceOffset:0 toBuffer:seedBuffer destinationOffset:0 size:sizeof seeds];
 }
 [upload endEncoding];NSDictionary*computeEvidence=nil;
 if(indirect){
  Parameters p={{seedBuffer.gpuAddress,0,argumentBuffer.gpuAddress,0},{argumentCount,1,1},{32,1,1}};
  if(!p.addresses[0]||!p.addresses[2]){emit(@{@"error":@"Missing GPU buffer address",@"seed_gpu_address":@(p.addresses[0]),@"argument_gpu_address":@(p.addresses[2])});return 5;}
  parameters=KPCreateHostBuffer(device,&p,sizeof p,true);id<MTLComputePipelineState>compute=nil;
  if(emptyControl)compute=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"write_draw_arguments"] error:&error];
  else{NSDictionary*i=info(directory,@"arguments");compute=KPCreatePipeline(device,[NSURL fileURLWithPath:@(argv[1])],@"write_draw_arguments",code(directory,@"arguments"),{[i[@"registers"]unsignedIntValue],576,576},&error,&computeEvidence);}
  if(!compute){emit(@{@"error":error.description?:@"compute pipeline failed",@"compute_import":computeEvidence?:@{}});return 6;}
  id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:compute];[encoder setBuffer:parameters offset:0 atIndex:0];[encoder setBuffer:argumentBuffer offset:0 atIndex:1];[encoder useResource:seedBuffer usage:MTLResourceUsageRead];[encoder useResource:argumentBuffer usage:MTLResourceUsageRead|MTLResourceUsageWrite];[encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[encoder endEncoding];
 }
 MTLVertexDescriptor*input=[MTLVertexDescriptor vertexDescriptor];for(unsigned i=0;i<3;i++){input.attributes[i].format=MTLVertexFormatFloat4;input.attributes[i].offset=i==1?16:0;input.attributes[i].bufferIndex=i==2?1:0;}input.layouts[0].stride=32;input.layouts[0].stepFunction=MTLVertexStepFunctionPerVertex;input.layouts[1].stride=16;input.layouts[1].stepFunction=MTLVertexStepFunctionPerInstance;input.layouts[1].stepRate=1;
 MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.vertexFunction=[library newFunctionWithName:[@"vs_io_" stringByAppendingString:interpolation]];desc.fragmentFunction=[library newFunctionWithName:[@"fs_io_" stringByAppendingString:interpolation]];desc.vertexDescriptor=input;desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
 id<MTLRenderPipelineState>pipeline=nil;NSDictionary*renderEvidence=nil;
 KeplerImportConfig vi={[info(directory,@"vertex")[@"registers"]unsignedIntValue],0,0},fi={[info(directory,interpolation)[@"registers"]unsignedIntValue],0,0};
 if(nakV&&nakF)pipeline=KPCreateGraphicsPipeline(device,desc,code(directory,@"vertex"),vi,code(directory,interpolation),fi,&error,&renderEvidence);
 else if(nakV)pipeline=KPCreateVertexPipeline(device,desc,code(directory,@"vertex"),vi,&error,&renderEvidence);
 else if(nakF)pipeline=KPCreateRenderPipeline(device,desc,code(directory,interpolation),fi,&error,&renderEvidence);
 else pipeline=[device newRenderPipelineStateWithDescriptor:desc error:&error];
 if(!pipeline){emit(@{@"error":error.description?:@"render pipeline failed",@"render_import":renderEvidence?:@{}});return 6;}
 MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[device newTextureWithDescriptor:td];id<MTLBuffer>readback=KPCreateHostBuffer(device,nullptr,W*H*16,true);if(!target||!readback)return 4;
 MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
 id<MTLRenderCommandEncoder>encoder=[command renderCommandEncoderWithDescriptor:pass];[encoder setRenderPipelineState:pipeline];[encoder setViewport:(MTLViewport){0,0,W,H,0,1}];[encoder setCullMode:MTLCullModeNone];[encoder setVertexBuffer:vbo offset:0 atIndex:0];[encoder setVertexBuffer:instanceBuffer offset:0 atIndex:1];
 if(indirect){if(indexed)[encoder drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexType:index32?MTLIndexTypeUInt32:MTLIndexTypeUInt16 indexBuffer:indexBuffer indexBufferOffset:indexByteOffset indirectBuffer:argumentBuffer indirectBufferOffset:0];else [encoder drawPrimitives:MTLPrimitiveTypeTriangle indirectBuffer:argumentBuffer indirectBufferOffset:0];}
 else if(indexed)[encoder drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:6 indexType:index32?MTLIndexTypeUInt32:MTLIndexTypeUInt16 indexBuffer:indexBuffer indexBufferOffset:indexByteOffset instanceCount:instances baseVertex:baseVertex baseInstance:baseInstance];
 else [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:vertexStart vertexCount:6 instanceCount:instances baseInstance:baseInstance];
 [encoder endEncoding];id<MTLBlitCommandEncoder>blit=[command blitCommandEncoder];[blit copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:W*16 destinationBytesPerImage:W*H*16];if(indirect)[blit copyFromBuffer:argumentBuffer sourceOffset:0 toBuffer:argumentReadback destinationOffset:0 size:sizeof initial];[blit endEncoding];[command commit];[command waitUntilCompleted];if(command.status!=MTLCommandBufferStatusCompleted){emit(@{@"error":command.error.description?:@"command failed"});return 7;}
 std::vector<ReferenceVertex>triangles;
 if(!emptyControl)for(unsigned instance=0;instance<instances;instance++)for(unsigned i=0;i<6;i++){
  unsigned id=indexed?indices[indexPrefix+i]+baseVertex:vertexStart+i;const Vertex&v=vertices[id];const Offset&o=offsets[baseInstance+instance];ReferenceVertex r;
  r.w=v.p[3];r.x=((v.p[0]/r.w+o.v[0])+1)*W/2;r.y=(1-(v.p[1]/r.w+o.v[1]))*H/2;
  for(unsigned c=0;c<4;c++)r.color[c]=nakV?(v.c[c]*.5+(c==3?.5:.125)):v.c[c];
  r.color[2]+=double(baseInstance+instance)/(nakV?32:64)+o.v[2];triangles.push_back(r);
 }
 auto cross=[](double ax,double ay,double bx,double by){return ax*by-ay*bx;};
 unsigned mismatches=0,coveredPixels=0;double maxError=0;const float*out=(const float*)readback.contents;NSMutableArray*first=[NSMutableArray array],*actualArguments=[NSMutableArray array];
 for(unsigned y=0;y<H;y++)for(unsigned x=0;x<W;x++){
  std::array<double,4>expected={0,0,0,0};bool covered=false;
  for(size_t t=0;t<triangles.size();t+=3){const auto&a=triangles[t],&b=triangles[t+1],&c=triangles[t+2];double area=cross(b.x-a.x,b.y-a.y,c.x-a.x,c.y-a.y);if(std::abs(area)<1e-12)continue;
   double l1=cross(x+.5-a.x,y+.5-a.y,c.x-a.x,c.y-a.y)/area,l2=cross(b.x-a.x,b.y-a.y,x+.5-a.x,y+.5-a.y)/area,l0=1-l1-l2;if(std::min({l0,l1,l2})<-1e-10)continue;
   covered=true;double weights[3]={l0,l1,l2};const ReferenceVertex*vs[3]={&a,&b,&c};
   if([interpolation isEqualToString:@"flat"])expected=a.color;
   else{if([interpolation isEqualToString:@"smooth"]){double denominator=0;for(unsigned i=0;i<3;i++){weights[i]/=vs[i]->w;denominator+=weights[i];}for(double&weight:weights)weight/=denominator;}
    expected={0,0,0,0};for(unsigned component=0;component<4;component++)for(unsigned i=0;i<3;i++)expected[component]+=weights[i]*vs[i]->color[component];}
   if(nakF)for(unsigned component=0;component<4;component++){const double bias[4]={.0625,.125,.1875,.25};expected[component]=expected[component]*.75+bias[component];}
  }
  if(covered)coveredPixels++;
  for(unsigned c=0;c<4;c++){double actual=out[(y*W+x)*4+c],delta=std::abs(actual-expected[c]);maxError=std::max(maxError,delta);if(!std::isfinite(actual)||delta>2e-6)mismatches++;if(!x&&!y)[first addObject:@(actual)];}
 }
 unsigned argumentMismatches=0,changedGuards=0;if(indirect){const uint32_t*actual=(const uint32_t*)argumentReadback.contents;for(unsigned i=0;i<argumentCount;i++){[actualArguments addObject:@(actual[i])];if(actual[i]!=(emptyControl?0:args[i]))argumentMismatches++;}for(unsigned i=argumentCount;i<8;i++)if(actual[i]!=initial[i])changedGuards++;}
 emit(@{@"device":device.name,@"registry_id":@(device.registryID),@"draw":@(draw.c_str()),@"mode":@(mode.c_str()),@"memory":@(memory.c_str()),@"interpolation":interpolation,@"pixels_checked":@(W*H),@"expected_covered_pixels":@(coveredPixels),@"mismatched_channels":@(mismatches),@"maximum_float_error":@(maxError),@"tolerance":@(2e-6),@"first_pixel":first,@"render_import":renderEvidence?:@{},@"compute_import":computeEvidence?:@{},@"argument_words":actualArguments,@"argument_mismatches":@(argumentMismatches),@"changed_argument_guards":@(changedGuards),@"arguments_produced_on_GPU":@(indirect),@"argument_buffer_private":@(indirect&&argumentBuffer.storageMode==MTLStorageModePrivate),@"argument_reported_storage_mode":@(indirect?argumentBuffer.storageMode:0),@"argument_contents_available":@(indirect&&argumentBuffer.contents!=nullptr),@"argument_CPU_read_before_submit":@NO,@"native_empty_control":@(emptyControl),@"command_status":@(command.status),@"scope":@"application-local vertex/fragment import and CPU raster oracle; indirect parameters produced within same GPU command buffer; no performance benchmark"});
 return mismatches||argumentMismatches||changedGuards?10:0;
}}
