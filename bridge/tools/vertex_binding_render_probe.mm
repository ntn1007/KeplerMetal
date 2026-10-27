// SPDX-License-Identifier: MIT
// Explicit adapted-client laboratory probe. All Metal execution is launched by
// the signed/reserved wrapper; this is not a general Apple ICB implementation.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#import "KeplerRenderStateRecords.h"
#import "AIRCertifiedResetPipeline.h"
#import <CommonCrypto/CommonDigest.h>
#include <cstring>
#include <stdexcept>

static void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
static NSData *load(NSString*dir,NSString*name){NSData*d=[NSData dataWithContentsOfFile:[dir stringByAppendingPathComponent:name]];need(d!=nil,"missing asset");return d;}
static NSString *hash(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(auto x:h)[s appendFormat:@"%02x",x];return s;}
static void save(id<MTLBuffer>buffer,NSString*path){need(![[NSFileManager defaultManager]fileExistsAtPath:path],"output exists");need([[NSData dataWithBytes:buffer.contents length:buffer.length]writeToFile:path atomically:YES],"save output");}
static void emit(id v){NSData*d=[NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingPrettyPrinted error:nil];need(d!=nil,"JSON");fwrite(d.bytes,1,d.length,stdout);puts("");}
struct Vertex{float position[4],color[4];};
static NSMutableData *guarded(NSUInteger n){NSMutableData*d=[NSMutableData dataWithLength:n];memset(d.mutableBytes,0xa5,n);return d;}
static NSData *vertices(bool alternate){
 NSMutableData*d=guarded(256);float p[3][4]={{-1,-1,0.5,1},{3,-1,0.5,1},{-1,3,0.5,1}};
 const float a[4]={.75,.125,.25,1},b[4]={.125,.75,.25,1};
 for(unsigned i=0;i<3;i++){Vertex v={};memcpy(v.position,p[i],16);memcpy(v.color,alternate?b:a,16);memcpy((char*)d.mutableBytes+64+i*sizeof(v),&v,sizeof(v));}return d;
}
int main(int argc,char**argv){@autoreleasepool{@try{try{
 need(argc==4,"assets output mode");NSString*assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 NSArray*modes=@[@"gpu",@"native",@"no_dispatch",@"no_dispatch_native",@"disabled",@"disabled_native",@"foreign",@"foreign_native",@"reverse",@"reverse_native",@"reverse_no_dispatch",@"reverse_no_dispatch_native",@"contracts"];
 need([modes containsObject:mode],"unsupported mode");bool native=[mode hasSuffix:@"native"],reverse=[mode hasPrefix:@"reverse"],dispatch=[mode rangeOfString:@"no_dispatch"].location==NSNotFound,foreign=[mode hasPrefix:@"foreign"],enabled=![mode hasPrefix:@"disabled"];
 id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)){need(!device,"ambiguous GPU");device=d;}need(device!=nil,"GPU absent");
 NSError*error=nil;NSDictionary*inspection=nil;NSString*certificate=[assets stringByAppendingPathComponent:@"vertex.certificate.json"];
 id<MTLComputePipelineState>check=KPNewCertifiedResetPipeline(device,[assets stringByAppendingPathComponent:@"vertex.metallib"],certificate,[out stringByAppendingPathComponent:@"constructor-captures"],&inspection,&error);need(check!=nil,error.description.UTF8String?:"certified constructor");
 id<MTLCommandQueue>queue=[device newCommandQueue];NSData*legacy=load(assets,@"render_state_carrier.metallib"),*library=load(assets,@"vertex_io_carrier.metallib"),*manifest=load(assets,@"vertex_profiles.json"),*materializer=load(assets,@"state.metallib");
 KPCPUICBScope*scope=[KPCPUICBScope installRenderingOnDevice:device queue:queue libraryData:legacy expectedSHA256:hash(legacy)error:&error];need(scope!=nil,error.description.UTF8String?:"scope");
 need([scope registerRenderVertexLibraryData:library expectedSHA256:hash(library)manifestData:manifest expectedManifestSHA256:hash(manifest)error:&error],error.description.UTF8String?:"vertex registration");
 need([scope enableGPURenderStateCatalogueWithLibraryData:materializer expectedSHA256:hash(materializer)error:&error],error.description.UTF8String?:"state registration");
 NSData*producer=load(assets,@"vertex.metallib");id<MTLFunction>function=[scope newRenderCommandFunctionWithLibraryData:producer expectedSHA256:hash(producer)functionName:@"probe_boundary" rootBufferIndex:0 error:&error];need(function!=nil,error.description.UTF8String?:"function");
 id<MTLComputePipelineState>pso=[device newComputePipelineStateWithFunction:function error:&error];need(pso!=nil,error.description.UTF8String?:"producer PSO");NSDictionary*program=nil;
 need(KPCheckCertifiedResetPipeline(pso,certificate,[out stringByAppendingPathComponent:@"native-program.bin"],&program,&error),error.description.UTF8String?:"program certificate");
 id<MTLRenderPipelineState>pipeline=[scope renderPipelineForName:@"smooth"];need(pipeline!=nil,"render pipeline");
 id<MTLBuffer>vertexA=[device newBufferWithBytes:vertices(false).bytes length:256 options:MTLResourceStorageModeShared];
 id<MTLBuffer>vertexB=[device newBufferWithBytes:vertices(true).bytes length:256 options:MTLResourceStorageModeShared];
 id<MTLBuffer>unknown=[device newBufferWithBytes:vertices(true).bytes length:256 options:MTLResourceStorageModeShared];
 NSMutableData*instanceData=guarded(160);memset((char*)instanceData.mutableBytes+64,0,16);id<MTLBuffer>instance=[device newBufferWithBytes:instanceData.bytes length:160 options:MTLResourceStorageModeShared];
 need(vertexA&&vertexB&&unknown&&instance,"vertex allocations");
 MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeDraw;desc.maxVertexBufferBindCount=2;desc.maxFragmentBufferBindCount=0;
 id<MTLIndirectCommandBuffer>commands[2];for(unsigned i=0;i<2;i++){
  commands[i]=[device newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];need(commands[i]!=nil,"ICB");
  id<MTLIndirectRenderCommand>c=[commands[i]indirectRenderCommandAtIndex:0];[c setRenderPipelineState:pipeline];[c setVertexBuffer:i?vertexB:vertexA offset:64 atIndex:0];[c setVertexBuffer:instance offset:64 atIndex:1];[c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];
 }
 KPRenderStateCatalogue*catalogue=[scope newRenderStateCatalogueWithCommands:commands[0] alternatives:@[commands[1]]error:&error];need(catalogue!=nil,error.description.UTF8String?:"catalogue");NSArray*ids=catalogue.stateIdentifiers;
 id<MTLCommandBuffer>cb=[queue commandBuffer];need(cb&&cb.retainedReferences,"command buffer");
 NSMutableData*recordData=guarded(192);KPRenderStateCommandRecord record={};record.magic=KP_RENDER_STATE_COMMAND_MAGIC;record.kind=0;record.arguments[0]=3;record.arguments[1]=1;record.state_identity=[ids[reverse?1:0]unsignedLongLongValue];memcpy((char*)recordData.mutableBytes+64,&record,sizeof(record));
 NSMutableData*rangeData=guarded(136);uint32_t range[2]={0,1};memcpy((char*)rangeData.mutableBytes+64,range,8);
 NSMutableData*outputData=guarded(132);
 auto upload=[&](NSData*data)->id<MTLBuffer>{id<MTLBuffer>stage=[device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];id<MTLBuffer>target=[device newBufferWithLength:data.length options:MTLResourceStorageModePrivate];need(stage&&target,"upload buffer");id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:stage sourceOffset:0 toBuffer:target destinationOffset:0 size:data.length];[b endEncoding];return target;};
 id<MTLBuffer>records=upload(recordData),rangeGPU=upload(rangeData),outGPU=upload(outputData);
 NSMutableArray*refusals=[NSMutableArray new];
 if([mode isEqual:@"contracts"]){
  id<MTLIndirectCommandBuffer>bad=[device newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];
  id<MTLIndirectRenderCommand>bc=[bad indirectRenderCommandAtIndex:0];[bc setRenderPipelineState:pipeline];[bc setVertexBuffer:records offset:64 atIndex:0];[bc setVertexBuffer:instance offset:64 atIndex:1];[bc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];
  KPRenderStateCatalogue*badCatalogue=[scope newRenderStateCatalogueWithCommands:bad alternatives:@[] error:&error];need(badCatalogue!=nil,error.description.UTF8String?:"alias catalogue");error=nil;
  id rejected=[scope newVertexRenderCommandArgumentContextWithCommands:bad stateCatalogue:badCatalogue commandRecords:records commandRecordsOffset:64 commandBuffer:cb error:&error];need(!rejected&&error!=nil,"record/vertex alias must be refused");[refusals addObject:@"vertex_records_overlap"];
 }

 KPRenderCommandArgumentContext*context=[scope newVertexRenderCommandArgumentContextWithCommands:commands[0] stateCatalogue:catalogue commandRecords:records commandRecordsOffset:64 commandBuffer:cb error:&error];need(context!=nil,error.description.UTF8String?:"vertex context");need(context.vertexTransitionCount==6&&context.vertexTransitionTableOffset==128,"transition table shape");
 id<MTLArgumentEncoder>argument=[function newArgumentEncoderWithBufferIndex:0];need(argument.encodedLength==8&&argument.alignment==8,"root encoder");id<MTLBuffer>root=[device newBufferWithLength:136 options:MTLResourceStorageModeShared];memset(root.contents,0xa5,136);
 if([mode isEqual:@"contracts"]){BOOL rejected=NO;[argument setArgumentBuffer:vertexA offset:64];@try{[argument setIndirectCommandBuffer:commands[0]atIndex:0];}@catch(NSException*x){rejected=YES;}need(rejected,"root/vertex alias must be refused");[refusals addObject:@"vertex_root_alias"];}
 [argument setArgumentBuffer:root offset:64];[argument setIndirectCommandBuffer:commands[0]atIndex:0];
 if(dispatch){uint32_t cfg[4]={1,enabled?1u:0u,0,0};id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:pso];need([scope prepareRenderCommandArgumentContext:context argumentBuffer:root offset:64 computeEncoder:e commandBuffer:cb error:&error],error.description.UTF8String?:"context preparation");[e setBuffer:outGPU offset:64 atIndex:1];[e setBuffer:foreign?unknown:reverse?vertexA:vertexB offset:64 atIndex:2];[e setBytes:cfg length:16 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];}
 if(!native)need([scope prepareIndirectRenderCommands:commands[0] stateCatalogue:catalogue commandRecords:records commandRecordsOffset:64 indirectBuffer:rangeGPU indirectBufferOffset:64 commandBuffer:cb error:&error],error.description.UTF8String?:"materializer preparation");
 MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[device newTextureWithDescriptor:td];need(target!=nil,"target");
 MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
 id<MTLRenderCommandEncoder>render=[scope renderEncoderWithDescriptor:pass commandBuffer:cb error:&error];need(render!=nil,error.description.UTF8String?:"render encoder");[render setViewport:(MTLViewport){0,0,64,48,0,1}];[render setRenderPipelineState:pipeline];[render setVertexBuffer:vertexA offset:64 atIndex:0];[render setVertexBuffer:instance offset:64 atIndex:1];
 if(native){if(!foreign){[render setVertexBuffer:dispatch&&enabled?(reverse?vertexA:vertexB):(reverse?vertexB:vertexA) offset:64 atIndex:0];[render drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];}}
 else [render executeCommandsInBuffer:commands[0] indirectBuffer:rangeGPU indirectBufferOffset:64];[render endEncoding];
 id<MTLBuffer>image=[device newBufferWithLength:49664 options:MTLResourceStorageModeShared],recordRead=[device newBufferWithLength:192 options:MTLResourceStorageModeShared],outputRead=[device newBufferWithLength:132 options:MTLResourceStorageModeShared],contextRead=[device newBufferWithLength:context.contextBuffer.length options:MTLResourceStorageModeShared];need(image&&recordRead&&outputRead&&contextRead,"readback");memset(image.contents,0xa5,image.length);
 id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1)toBuffer:image destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[b copyFromBuffer:records sourceOffset:0 toBuffer:recordRead destinationOffset:0 size:192];[b copyFromBuffer:outGPU sourceOffset:0 toBuffer:outputRead destinationOffset:0 size:132];[b copyFromBuffer:context.contextBuffer sourceOffset:0 toBuffer:contextRead destinationOffset:0 size:context.contextBuffer.length];[b endEncoding];
 [scope restore];[cb commit];[cb waitUntilCompleted];need(cb.status==MTLCommandBufferStatusCompleted,cb.error.description.UTF8String?:"GPU command buffer failed");
 save(root,[out stringByAppendingPathComponent:@"root.bin"]);save(vertexA,[out stringByAppendingPathComponent:@"vertex-a.bin"]);save(vertexB,[out stringByAppendingPathComponent:@"vertex-b.bin"]);save(instance,[out stringByAppendingPathComponent:@"instance.bin"]);
 save(image,[out stringByAppendingPathComponent:@"image.bin"]);save(recordRead,[out stringByAppendingPathComponent:@"records.bin"]);save(outputRead,[out stringByAppendingPathComponent:@"output.bin"]);save(contextRead,[out stringByAppendingPathComponent:@"context.bin"]);
 emit(@{@"status":@"COMPLETED",@"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"device_identity":KPKepler880MIdentity(device),@"dispatches":@(dispatch?1:0),@"native_reference":@(native),@"command_status":@(cb.status),@"identities":ids,@"context_address":@(context.contextBuffer.gpuAddress+context.contextOffset),@"records_address":@(records.gpuAddress+64),@"vertex_addresses":@[@(vertexA.gpuAddress+64),@(vertexB.gpuAddress+64),@(instance.gpuAddress+64),@(unknown.gpuAddress+64)],@"transition_count":@(context.vertexTransitionCount),@"refusals":refusals,@"context_size":@(context.contextBuffer.length),@"program":program,@"inspection":inspection,@"native_Apple_ICB_ABI":@NO,@"performance_benchmark":@NO});
 return 0;
 }catch(const std::exception&e){fprintf(stderr,"C++ error: %s\n",e.what());return 2;}}@catch(NSException*x){fprintf(stderr,"Objective-C error: %s\n",x.reason.UTF8String);return 3;}}}
