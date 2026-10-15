#import "KeplerProgramImport.h"
#include <cstring>
#include <vector>
#include <unistd.h>
struct Vertex{float p[4],c[4];};
struct Parameters{float scale[4],bias[4];uint32_t shape[4];};
static void emit(id x){NSData*d=[NSJSONSerialization dataWithJSONObject:x options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static id<MTLLibrary>load(id<MTLDevice>d,NSString*p,NSError**e){return[d newLibraryWithURL:[NSURL fileURLWithPath:p]error:e];}
static NSDictionary*info(NSString*assets,NSString*name){return[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".json"]]]options:0 error:nil];}
static NSData*code(NSString*assets,NSString*name){return[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".sass"]]];}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*out=@(argv[2]),*requested=@(argv[3]);NSArray*parts=[requested componentsSeparatedByString:@":"];if(parts.count!=2)return 1;NSString*family=parts[0],*policy=parts[1];
 if(![@[@"fragment",@"vertex",@"graphics",@"tessellation",@"host_managed",@"host_nocopy",@"native_render",@"native_tess"]containsObject:family]||![@[@"keep",@"drop",@"cancel"]containsObject:policy])return 1;
 BOOL host=[family hasPrefix:@"host_"],tess=[family isEqual:@"tessellation"]||[family isEqual:@"native_tess"],native=[family hasPrefix:@"native_"]||host,cancelled=[policy isEqual:@"cancel"];
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;NSMutableArray*runs=[NSMutableArray new];
 for(unsigned trial=0;trial<4;trial++){
  id<MTLCommandBuffer>pending=nil;NSMutableDictionary*readbacks=nil,*row=nil;NSArray*callerOwners=nil;__weak id weakPipeline=nil,weakTarget=nil;NSPointerArray*weakBuffers=[NSPointerArray weakObjectsPointerArray];
  @autoreleasepool{
   NSError*error=nil;id<MTLCommandQueue>q=[d newCommandQueue];id<MTLLibrary>lib=load(d,[assets stringByAppendingPathComponent:host?@"resource.metallib":tess?@"tess.metallib":@"vertex.metallib"],&error);if(!lib)return 3;
   id<MTLRenderPipelineState>render=nil;id<MTLComputePipelineState>compute=nil;NSDictionary*proof=@{};NSMutableArray*owners=[NSMutableArray new];NSMutableDictionary*gpu=[NSMutableDictionary new];readbacks=[NSMutableDictionary new];NSMutableDictionary*spec=[NSMutableDictionary new];
   auto hostBuffer=[&](const void*data,NSUInteger bytes,BOOL noCopy)->id<MTLBuffer>{id<MTLBuffer>b=KPCreateHostBuffer(d,data,bytes,noCopy);if(b){[owners addObject:b];[weakBuffers addPointer:(__bridge void*)b];}return b;};
   pending=[q commandBuffer];if(!pending.retainedReferences)return 4;
   auto readBuffer=[&](NSString*name,id<MTLBuffer>source,NSUInteger bytes){id<MTLBuffer>result=[d newBufferWithLength:bytes options:MTLResourceStorageModeShared];if(!result)return false;memset(result.contents,0xa5,bytes);readbacks[name]=result;id<MTLBlitCommandEncoder>blit=[pending blitCommandEncoder];[blit copyFromBuffer:source sourceOffset:0 toBuffer:result destinationOffset:0 size:bytes];[blit endEncoding];return true;};
   if(host){
    const unsigned counts[4]={257,1025,4096,8191};unsigned n=counts[trial];NSUInteger bytes=n*16+128;std::vector<unsigned char>input(bytes,0xa5),output(bytes,0xa5);for(unsigned i=0;i<n;i++)for(unsigned c=0;c<4;c++){float value=float(int((i*17u+c*3u+trial*7u)%67u)-32)/32;memcpy(input.data()+64+i*16+c*4,&value,4);}
    Parameters p={{.5,-1.5,2,.25},{.125f+trial/32.f,-.25f,.5f,1.f},{n,1,1,n}};BOOL noCopy=[family isEqual:@"host_nocopy"];
    id<MTLBuffer>a=hostBuffer(input.data(),bytes,noCopy),b=hostBuffer(output.data(),bytes,noCopy),params=hostBuffer(&p,sizeof p,noCopy);if(!a||!b||!params)return 4;
    compute=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"buffers_a"]error:&error];if(!compute)return 5;
    id<MTLComputeCommandEncoder>e=[pending computeCommandEncoder];[e setComputePipelineState:compute];[e setBuffer:a offset:64 atIndex:0];[e setBuffer:params offset:0 atIndex:3];[e setBuffer:b offset:64 atIndex:7];[e dispatchThreadgroups:MTLSizeMake((n+31)/32,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
    if(!readBuffer(@"input",a,bytes)||!readBuffer(@"output",b,bytes))return 4;
    spec[@"count"]=@(n);spec[@"requested_buffer_bytes"]=@(bytes);spec[@"factory_lengths"]=@[@(a.length),@(b.length),@(params.length)];spec[@"factory_storage_modes"]=@[@(a.storageMode),@(b.storageMode),@(params.storageMode)];spec[@"NoCopy"]=@(noCopy);
   }else{
    MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
    if(tess){
     desc.vertexFunction=[lib newFunctionWithName:@"tess_capture"];desc.rasterizationEnabled=NO;desc.maxTessellationFactor=64;desc.tessellationPartitionMode=MTLTessellationPartitionModeInteger;desc.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionConstant;desc.tessellationOutputWindingOrder=MTLWindingCounterClockwise;
     if(native)render=[d newRenderPipelineStateWithDescriptor:desc error:&error];else{NSDictionary*i=info(assets,@"tess");render=KPCreateTessellationPipeline(d,desc,code(assets,@"tess"),{[i[@"registers"]unsignedIntValue],0,0},&error,&proof);}
    }else{
     desc.vertexFunction=[lib newFunctionWithName:@"vs_io_flat"];desc.fragmentFunction=[lib newFunctionWithName:@"fs_io_flat"];MTLVertexDescriptor*v=[MTLVertexDescriptor vertexDescriptor];for(unsigned i=0;i<3;i++){v.attributes[i].format=MTLVertexFormatFloat4;v.attributes[i].offset=i==1?16:0;v.attributes[i].bufferIndex=i==2?1:0;}v.layouts[0].stride=32;v.layouts[0].stepFunction=MTLVertexStepFunctionPerVertex;v.layouts[1].stride=16;v.layouts[1].stepFunction=MTLVertexStepFunctionPerInstance;v.layouts[1].stepRate=1;desc.vertexDescriptor=v;
     KeplerImportConfig vi={[info(assets,@"vertex")[@"registers"]unsignedIntValue],0,0},fi={[info(assets,@"flat")[@"registers"]unsignedIntValue],0,0};
     if([family isEqual:@"fragment"])render=KPCreateRenderPipeline(d,desc,code(assets,@"flat"),fi,&error,&proof);
     else if([family isEqual:@"vertex"])render=KPCreateVertexPipeline(d,desc,code(assets,@"vertex"),vi,&error,&proof);
     else if([family isEqual:@"graphics"])render=KPCreateGraphicsPipeline(d,desc,code(assets,@"vertex"),vi,code(assets,@"flat"),fi,&error,&proof);
     else render=[d newRenderPipelineStateWithDescriptor:desc error:&error];
    }
    if(!render||(!native&&![proof[@"contract_verified"]boolValue])){emit(@{@"failure":@"pipeline",@"error":error.description?:@"nil",@"import":proof?:@{}});return 5;}
    unsigned W=tess?1:32+trial*16,H=tess?1:24+trial*8;MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[d newTextureWithDescriptor:td];if(!target)return 4;[owners addObject:target];weakTarget=target;MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=tess?MTLStoreActionDontCare:MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
    if(tess){
     const unsigned factors[4]={0,1,8,64};unsigned factor=factors[trial],capacity=32768;size_t lengths[3]={132,capacity*16+128,capacity*16+128};
     id<MTLBlitCommandEncoder>init=[pending blitCommandEncoder];for(unsigned k=0;k<3;k++){NSString*name=@[@"counter",@"coordinates",@"values"][k];std::vector<unsigned char>initial(lengths[k],0xa5);if(k==0)memset(initial.data()+64,0,4);id<MTLBuffer>stage=hostBuffer(initial.data(),lengths[k],YES),g=[d newBufferWithLength:lengths[k]options:MTLResourceStorageModePrivate];if(!stage||!g)return 4;gpu[name]=g;[owners addObject:g];[init copyFromBuffer:stage sourceOffset:0 toBuffer:g destinationOffset:0 size:lengths[k]];}[init endEncoding];
     uint16_t bits=0;if(factor){unsigned exponent=0;while((1u<<(exponent+1))<=factor)exponent++;bits=(exponent+15)<<10;}MTLTriangleTessellationFactorsHalf f={{bits,bits,bits},bits};id<MTLBuffer>fb=hostBuffer(&f,sizeof f,YES);if(!fb)return 4;
     id<MTLRenderCommandEncoder>e=[pending renderCommandEncoderWithDescriptor:pass];[e setRenderPipelineState:render];for(unsigned k=0;k<3;k++)[e setVertexBuffer:gpu[@[@"counter",@"coordinates",@"values"][k]]offset:64 atIndex:k];[e setTessellationFactorBuffer:fb offset:0 instanceStride:0];[e drawPatches:3 patchStart:0 patchCount:1 patchIndexBuffer:nil patchIndexBufferOffset:0 instanceCount:1 baseInstance:0];[e endEncoding];
     for(unsigned k=0;k<3;k++)if(!readBuffer(@[@"counter",@"coordinates",@"values"][k],gpu[@[@"counter",@"coordinates",@"values"][k]],lengths[k]))return 4;
     spec[@"factor"]=@(factor);spec[@"capacity"]=@(capacity);
    }else{
     float color[4]={float(1+trial)/16,float(3+trial)/16,float(7+trial)/16,float(11+trial)/16};float xy[6][2]={{-1,-1},{1,-1},{-1,1},{-1,1},{1,-1},{1,1}};Vertex vertices[6];for(unsigned k=0;k<6;k++){vertices[k]={{xy[k][0],xy[k][1],.5f,1},{color[0],color[1],color[2],color[3]}};}float offset[4]={0,0,0,0};id<MTLBuffer>vb=hostBuffer(vertices,sizeof vertices,YES),ib=hostBuffer(offset,sizeof offset,YES);if(!vb||!ib)return 4;
     id<MTLRenderCommandEncoder>e=[pending renderCommandEncoderWithDescriptor:pass];[e setRenderPipelineState:render];[e setViewport:(MTLViewport){0,0,double(W),double(H),0,1}];[e setCullMode:MTLCullModeNone];[e setVertexBuffer:vb offset:0 atIndex:0];[e setVertexBuffer:ib offset:0 atIndex:1];[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6 instanceCount:1 baseInstance:0];[e endEncoding];
     NSUInteger rowBytes=W*16,total=rowBytes*H+512;id<MTLBuffer>rb=[d newBufferWithLength:total options:MTLResourceStorageModeShared];if(!rb)return 4;memset(rb.contents,0xa5,total);readbacks[@"pixels"]=rb;id<MTLBlitCommandEncoder>b=[pending blitCommandEncoder];[b copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)sourceSize:MTLSizeMake(W,H,1)toBuffer:rb destinationOffset:256 destinationBytesPerRow:rowBytes destinationBytesPerImage:rowBytes*H];[b endEncoding];spec[@"width"]=@(W);spec[@"height"]=@(H);spec[@"color"]=@[@(color[0]),@(color[1]),@(color[2]),@(color[3])];spec[@"prefix_bytes"]=@256;
    }
   }
   weakPipeline=host?(id)compute:(id)render;if([policy isEqual:@"keep"])callerOwners=@[host?(id)compute:(id)render,owners,lib];row=[@{@"trial":@(trial),@"spec":spec,@"import":proof?:@{},@"factory_buffers_observed":@(weakBuffers.count),@"CPU_expected_answers_uploaded":@NO}mutableCopy];
  }
  @autoreleasepool{
   row[@"caller_pool_drained_before_commit"]=@YES;row[@"caller_bundle_retained"]=@(callerOwners!=nil);row[@"status_before_commit"]=@(pending.status);if(pending.status!=MTLCommandBufferStatusNotEnqueued)return 6;
   if(!cancelled){[pending commit];[pending waitUntilCompleted];if(pending.status!=MTLCommandBufferStatusCompleted){emit(@{@"failure":@"GPU",@"error":pending.error.description?:@"nil"});return 7;}}
   row[@"committed"]=@(!cancelled);row[@"command_status"]=@(pending.status);NSMutableDictionary*files=[NSMutableDictionary new];if(!cancelled)for(NSString*name in readbacks){id<MTLBuffer>b=readbacks[name];NSString*f=[NSString stringWithFormat:@"trial-%u-%@.bin",trial,name];[[NSData dataWithBytes:b.contents length:b.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[name]=f;}row[@"files"]=files;
   pending=nil;callerOwners=nil;for(unsigned wait=0;wait<250&&weakPipeline;wait++)usleep(1000);NSUInteger alive=0;for(NSUInteger i=0;i<weakBuffers.count;i++)if([weakBuffers pointerAtIndex:i])alive++;row[@"pipeline_alive_after_release"]=@(weakPipeline!=nil);row[@"factory_buffers_alive_after_release"]=@(alive);row[@"target_alive_after_release"]=@(weakTarget!=nil);[runs addObject:row];
  }
 }
 emit(@{@"mode":requested,@"family":family,@"policy":policy,@"device":d.name,@"registry_id":@(d.registryID),@"native_pipeline_control":@(native),@"runs":runs,@"system_modified":@NO,@"performance_benchmark":@NO,@"scope":@"Own-process ARC factory and resource lifetime, exact frozen shaders, no installed-driver change"});return 0;
}}
