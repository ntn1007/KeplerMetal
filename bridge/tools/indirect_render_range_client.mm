// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#import "KeplerRenderCommandRecords.h"
#include <CommonCrypto/CommonDigest.h>
#include <vector>
#include <cstring>
struct Vertex {float p[4],c[4];};
// Release probes leave only the retained command buffer and CPU readbacks
// outside the inner autorelease pool. Never retain source resources here.
static id<MTLCommandBuffer> deferredBuffer;
static void (^deferredReadback)(void);
static __weak KPCPUICBScope *releasedScope;
static __weak id<MTLIndirectCommandBuffer> releasedICB;
static __weak id<MTLTexture> releasedTexture;
static __weak id<MTLSamplerState> releasedSampler;
static BOOL releasePoolDrained, scopeGoneBeforeCommit, icbGoneBeforeCommit, textureAliveBeforeCommit, samplerAliveBeforeCommit;
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
static void emit(id value){NSData*d=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");}
static void save(id<MTLBuffer>b,NSString*dir,NSString*name){[[NSData dataWithBytes:b.contents length:b.length]writeToFile:[dir stringByAppendingPathComponent:name]atomically:YES];}
static id<MTLLibrary>load(id<MTLDevice>d,NSString*path,NSError**error){return[d newLibraryWithURL:[NSURL fileURLWithPath:path]error:error];}
static void rectangle(std::vector<unsigned char>&raw,unsigned offset,unsigned first,BOOL indexed,int x0,int y0,int x1,int y1,const float color[4]){
    unsigned order[]={0,1,2,2,1,3};float xy[4][2]={{float(x0),float(y1)},{float(x1),float(y1)},{float(x0),float(y0)},{float(x1),float(y0)}};
    for(unsigned i=0;i<(indexed?4:6);i++){unsigned j=indexed?i:order[i];Vertex v={{xy[j][0]/32.f-1.f,1.f-xy[j][1]/24.f,.5f,1.f},{color[0],color[1],color[2],color[3]}};memcpy(raw.data()+offset+(first+i)*sizeof v,&v,sizeof v);}
}
static bool referenceArguments(unsigned trial,unsigned slot,uint32_t value,uint32_t *a){
    if(trial==7||slot==2)return false;
    if((trial==1&&slot==1)||(trial==2&&slot==3)||(trial==3&&slot==0)||
       (trial==4&&slot==1)||(trial==5&&slot==3)||(trial==6&&slot==0))return false;
    unsigned kind=slot==0?0:slot==1?1:2;
    a[0]=3;a[1]=1;a[2]=(slot==0?5:0)+3*((value>>kind)&1u);
    a[3]=slot==0?0:slot==1?2:0xfffffffeu;a[4]=slot==0?0:slot==1?1:2;
    return true;
}
static int runClient(int argc,char**argv){
    if(argc!=4)return 1;NSString*assets=@(argv[1]),*dir=@(argv[2]),*mode=@(argv[3]);
    if(![@[@"gpu",@"native",@"no_consumer",@"lifetime",@"contracts",@"fragment",@"fragment_native",@"fragment_lifetime",@"legacy",@"legacy_native",@"release",@"fragment_release",@"records",@"records_native",@"fragment_records",@"fragment_records_native",@"records_no_consumer",@"records_no_producer",@"records_release",@"fragment_records_release"]containsObject:mode])return 1;
    BOOL release=[mode hasSuffix:@"release"],gpuRecords=[mode containsString:@"records"],noProducer=[mode isEqual:@"records_no_producer"];
    BOOL reference=[mode isEqual:@"native"]||[mode hasSuffix:@"_native"],consume=![mode isEqual:@"no_consumer"]&&![mode isEqual:@"records_no_consumer"],fragment=[mode hasPrefix:@"fragment"],legacyMode=[mode hasPrefix:@"legacy"],lifetime=[mode hasSuffix:@"lifetime"];
    id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}if(!d)return 2;
    id<MTLCommandQueue>q=[d newCommandQueue];Class original=object_getClass(d);NSError*error=nil;
    NSData*legacy=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"render_state_carrier.metallib"]],*vertex=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:fragment?@"combined_render_resources.metallib":@"vertex_io_carrier.metallib"]],*manifest=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:fragment?@"combined.json":@"vertex.json"]],*materializer=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"range.metallib"]];
    KPCPUICBScope*scope=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:legacy expectedSHA256:sha(legacy)error:&error];
    if(!scope||(!legacyMode&&![scope registerRenderVertexLibraryData:vertex expectedSHA256:sha(vertex)manifestData:manifest expectedManifestSHA256:sha(manifest)error:&error])||![scope enableGPUIndirectRenderRangesWithLibraryData:materializer expectedSHA256:sha(materializer)error:&error]){emit(@{@"failure":@"registration",@"error":error.description?:@""});return 3;}
    if(gpuRecords){NSData *recordKernel=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"records.metallib"]];if(![scope enableGPURenderCommandRecordsWithLibraryData:recordKernel expectedSHA256:sha(recordKernel)error:&error]){emit(@{@"failure":@"record registration",@"error":error.description?:@""});return 3;}}
    id<MTLLibrary>test=load(d,[assets stringByAppendingPathComponent:@"test.metallib"],&error);
    id<MTLComputePipelineState>producer=[d newComputePipelineStateWithFunction:[test newFunctionWithName:gpuRecords?@"generate_render_records":@"generate_render_range"]error:&error];
    MTLRenderPipelineDescriptor*md=[MTLRenderPipelineDescriptor new];md.vertexFunction=[test newFunctionWithName:@"vs_range_marker"];md.fragmentFunction=[test newFunctionWithName:@"fs_range_marker"];md.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
    id<MTLRenderPipelineState>marker=[d newRenderPipelineStateWithDescriptor:md error:&error];if(!producer||!marker)return 4;
    NSMutableArray*runs=[NSMutableArray new];id<MTLIndirectCommandBuffer>persistent=nil;NSArray*savedEvents=nil;
    for(unsigned trial=0;trial<(release?1u:8u);trial++){@autoreleasepool{
        NSMutableArray*uploads=[NSMutableArray new],*reads=[NSMutableArray new],*buffers=[NSMutableArray new];
        auto privateBuffer=[&](const std::vector<unsigned char>&data)->id<MTLBuffer>{id<MTLBuffer>u=[d newBufferWithBytes:data.data()length:data.size()options:MTLResourceStorageModeShared],g=[d newBufferWithLength:data.size()options:MTLResourceStorageModePrivate],r=[d newBufferWithLength:data.size()options:MTLResourceStorageModeShared];if(!u||!g||!r)return nil;[uploads addObject:u];[buffers addObject:g];[reads addObject:r];return g;};
        const float colors[3][4]={{.25,.125,.75,1},{.125,.75,.25,1},{.75,.5,.125,1}};
        id<MTLBuffer>vbo[3],instances,index16,index32,markerV,markerP;
        for(unsigned i=0;i<3;i++){std::vector<unsigned char>data(4096,0xa5);rectangle(data,64,i==0?5:i==1?7:3,i!=0,i==0?0:i==1?32:16,i==2?12:0,i==0?32:i==1?64:48,i==2?36:48,colors[i]);vbo[i]=privateBuffer(data);}
        std::vector<unsigned char>idata(512,0xa5);memset(idata.data()+128,0,16*8);instances=privateBuffer(idata);
        unsigned order[]={5,6,7,7,6,8};if(legacyMode){unsigned v[]={0,1,2,2,1,3};memcpy(order,v,sizeof v);}std::vector<unsigned char>i16(256,0xa5),i32(256,0xa5);for(unsigned i=0;i<6;i++){uint16_t s=order[i];uint32_t l=order[i];memcpy(i16.data()+64+i*2,&s,2);memcpy(i32.data()+64+i*4,&l,4);}index16=privateBuffer(i16);index32=privateBuffer(i32);
        std::vector<unsigned char>mdata(4096,0xa5);rectangle(mdata,64,0,NO,0,0,8,48,colors[0]);markerV=privateBuffer(mdata);std::vector<unsigned char>pdat(512,0xa5);float mp[4]={0,0,.625,0};memcpy(pdat.data()+128,mp,16);markerP=privateBuffer(pdat);
        std::vector<unsigned char>seedData(192,0xa5);uint32_t values[16];for(unsigned i=0;i<16;i++)values[i]=(0x13579bdu+i*97u+trial*17u)^0xa3b5c7d9u;memcpy(seedData.data()+64,values,sizeof values);id<MTLBuffer>seeds=privateBuffer(seedData);
        std::vector<unsigned char>rdata(136,0xa5);memset(rdata.data()+64,0,8);id<MTLBuffer>range=privateBuffer(rdata);std::vector<unsigned char>cdata(132,0xa5);memset(cdata.data()+64,0,4);id<MTLBuffer>counter=privateBuffer(cdata);
        id<MTLBuffer>recordSource=nil;if(gpuRecords){std::vector<unsigned char>data(256,0xa5);memset(data.data()+64,0,128);recordSource=privateBuffer(data);if(!recordSource)return 5;}
        if(!vbo[0]||!vbo[1]||!vbo[2]||!instances||!index16||!index32||!markerV||!markerP||!seeds||!range||!counter)return 5;
        id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];for(unsigned i=0;i<buffers.count;i++){id<MTLBuffer>u=uploads[i];[b copyFromBuffer:u sourceOffset:0 toBuffer:buffers[i]destinationOffset:0 size:u.length];}[b endEncoding];
        MTLIndirectCommandBufferDescriptor*desc=[MTLIndirectCommandBufferDescriptor new];desc.commandTypes=MTLIndirectCommandTypeDraw|MTLIndirectCommandTypeDrawIndexed;desc.maxVertexBufferBindCount=legacyMode?0:2;desc.maxFragmentBufferBindCount=fragment?1:0;
        id<MTLIndirectCommandBuffer>icb=lifetime?persistent:nil;if(!icb)icb=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:4 options:MTLResourceStorageModeShared];else[icb resetWithRange:NSMakeRange(0,4)];if(!icb)return 5;if(lifetime)persistent=icb;
        NSMutableArray *fragmentTextures=[NSMutableArray new],*fragmentSamplers=[NSMutableArray new],*fragmentParams=[NSMutableArray new],*fragmentShared=[NSMutableArray new],*fragmentPrivate=[NSMutableArray new],*fragmentUploads=[NSMutableArray new],*fragmentReads=[NSMutableArray new];
        if(fragment){
            for(unsigned bank=0;bank<2;bank++){
                MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageShaderRead;
                id<MTLTexture>tex=[d newTextureWithDescriptor:td];std::vector<float>pixels(64*48*4);
                for(unsigned y=0;y<48;y++)for(unsigned x=0;x<64;x++){float*pixel=&pixels[(y*64+x)*4];pixel[0]=bank?float(7-x%8)/8.f:float(x%8)/16.f;pixel[1]=bank?float(7-y%8)/8.f:float(y%8)/16.f;pixel[2]=bank?float((2*x+y)%8)/8.f:float((x+y)%8)/16.f;pixel[3]=1;}
                id<MTLBuffer>u=[d newBufferWithBytes:pixels.data()length:pixels.size()*4 options:MTLResourceStorageModeShared],r=[d newBufferWithLength:pixels.size()*4 options:MTLResourceStorageModeShared];if(!tex||!u||!r)return 5;
                [fragmentTextures addObject:tex];[fragmentUploads addObject:u];[fragmentReads addObject:r];
                b=[cb blitCommandEncoder];[b copyFromBuffer:u sourceOffset:0 sourceBytesPerRow:1024 sourceBytesPerImage:49152 sourceSize:MTLSizeMake(64,48,1)toTexture:tex destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];[b endEncoding];
            }
            for(unsigned i=0;i<3;i++){
                MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];sd.minFilter=sd.magFilter=i==1?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;sd.sAddressMode=sd.tAddressMode=MTLSamplerAddressModeClampToEdge;sd.supportArgumentBuffers=YES;id<MTLSamplerState>sampler=[d newSamplerStateWithDescriptor:sd];
                id<MTLBuffer>p=[d newBufferWithLength:512 options:MTLResourceStorageModeShared],a=[d newBufferWithLength:1024 options:MTLResourceStorageModeShared];if(!sampler||!p||!a)return 5;memset(p.contents,0xa5,512);memset(a.contents,0xa5,1024);
                float parameters[3][8]={{.5,1,1,1,.125,0,0,0},{1,1.5,.5,1,0,.125,0,0},{.75,.5,2,1,0,0,.25,0}};memcpy((char*)p.contents+256,parameters[i],32);
                NSString*name=@[@"smooth",@"linear",@"flat"][i];NSDictionary*resources=@{@0:fragmentTextures[i==1?1:0],@1:sampler,@2:@{@"buffer":p,@"offset":@256}};
                if(![scope encodeFragmentArgumentBuffer:a offset:256 pipelineName:name bindingIndex:0 resources:resources error:&error])return 5;
                id<MTLBuffer>g=[scope newPrivateFragmentArgumentBufferForPipeline:name bindingIndex:0 sources:@[@{@"buffer":a,@"offset":@256}]selectedBank:0 commandBuffer:cb counter:nil error:&error];if(!g)return 5;
                [fragmentSamplers addObject:sampler];[fragmentParams addObject:p];[fragmentShared addObject:a];[fragmentPrivate addObject:g];
            }
        }
        for(unsigned i=0;i<3;i++){unsigned slot=i==2?3:i;id<MTLIndirectRenderCommand>c=[icb indirectRenderCommandAtIndex:slot];[c setRenderPipelineState:legacyMode?scope.renderPipeline:[scope renderPipelineForName:@[@"smooth",@"linear",@"flat"][i]]];if(!legacyMode){[c setVertexBuffer:vbo[i]offset:64 atIndex:0];[c setVertexBuffer:instances offset:128 atIndex:1];}if(fragment)[c setFragmentBuffer:fragmentPrivate[i]offset:256 atIndex:0];if(!i)[c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:legacyMode?0:5 vertexCount:legacyMode?3:6 instanceCount:1 baseInstance:0];else[c drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:legacyMode?3:6 indexType:i==1?MTLIndexTypeUInt16:MTLIndexTypeUInt32 indexBuffer:i==1?index16:index32 indexBufferOffset:64 instanceCount:1 baseVertex:legacyMode?0:i==1?2:-2 baseInstance:legacyMode?0:i==1?1:2];}
        uint32_t cfg[4]={trial,trial,4,0};id<MTLBuffer>config=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];if(!config)return 5;memset(config.contents,0,256);memcpy(config.contents,cfg,16);
        if(trial!=7&&!noProducer){id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:producer];[e setBuffer:seeds offset:64 atIndex:0];[e setBuffer:range offset:64 atIndex:1];[e setBuffer:counter offset:64 atIndex:2];[e setBuffer:config offset:0 atIndex:3];if(gpuRecords)[e setBuffer:recordSource offset:64 atIndex:4];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];}
        NSMutableArray*refusals=[NSMutableArray new];
        BOOL prepared=YES;if(!reference)prepared=gpuRecords?[scope prepareIndirectRenderCommands:icb commandRecords:recordSource commandRecordsOffset:64 indirectBuffer:range indirectBufferOffset:64 commandBuffer:cb error:&error]:[scope prepareIndirectRenderCommands:icb indirectBuffer:range indirectBufferOffset:64 commandBuffer:cb error:&error];
        if(!prepared){emit(@{@"failure":@"prepare",@"error":error.description?:@""});return 6;}
        id<MTLIndirectCommandBuffer>backup=nil;
        if([mode isEqual:@"contracts"]&&trial<2){
            BOOL result=NO;
            auto refused=[&](NSString*name,BOOL result,NSError*failure){if(result||!failure)return NO;[refusals addObject:name];return YES;};
            error=nil;result=[scope prepareIndirectRenderCommands:icb indirectBuffer:range indirectBufferOffset:64 commandBuffer:cb error:&error];if(!refused(@"pending_reprepare",result,error))return 12;
            error=nil;result=[scope prepareIndirectRenderCommands:icb indirectBuffer:range indirectBufferOffset:65 commandBuffer:cb error:&error];if(!refused(@"misaligned_range",result,error))return 12;
            id<MTLBuffer>shortRange=[d newBufferWithLength:4 options:MTLResourceStorageModeShared];
            error=nil;result=[scope prepareIndirectRenderCommands:icb indirectBuffer:shortRange indirectBufferOffset:0 commandBuffer:cb error:&error];if(!refused(@"short_range",result,error))return 12;
            id<MTLCommandQueue>foreign=[d newCommandQueue];id<MTLCommandBuffer>wrong=[foreign commandBuffer];
            error=nil;result=[scope prepareIndirectRenderCommands:icb indirectBuffer:range indirectBufferOffset:64 commandBuffer:wrong error:&error];if(!refused(@"foreign_queue",result,error))return 12;
            id<MTLCommandBuffer>unretained=[q commandBufferWithUnretainedReferences];if(!unretained||unretained.retainedReferences)return 12;
            error=nil;result=[scope prepareIndirectRenderCommands:icb indirectBuffer:range indirectBufferOffset:64 commandBuffer:unretained error:&error];if(!refused(@"unretained_command_buffer",result,error))return 12;
            error=nil;result=[scope enableGPUIndirectRenderRangesWithLibraryData:materializer expectedSHA256:@"0000000000000000000000000000000000000000000000000000000000000000" error:&error];if(!refused(@"wrong_kernel_pin",result,error))return 12;
            backup=[d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:4 options:MTLResourceStorageModeShared];if(!KPCopyCPUICBCommands(icb,NSMakeRange(0,4),backup,0,&error))return 12;
        }
        id plan=reference?nil:[(id)icb valueForKey:@"indirectRenderPlan"];id<MTLBuffer>args=plan?[plan valueForKey:@"arguments"]:nil,witness=plan?[plan valueForKey:@"witness"]:nil,argsHost=args?[d newBufferWithLength:args.length options:MTLResourceStorageModeShared]:nil,witnessHost=witness?[d newBufferWithLength:witness.length options:MTLResourceStorageModeShared]:nil;
        if(args&&(!argsHost||!witnessHost))return 5;
        MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[d newTextureWithDescriptor:td];id<MTLBuffer>image=[d newBufferWithLength:49664 options:MTLResourceStorageModeShared];if(!target||!image)return 5;memset(image.contents,0xa5,image.length);
        MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
        id<MTLRenderCommandEncoder>e=[scope renderEncoderWithDescriptor:pass commandBuffer:cb error:&error];if(!e)return 7;[e setViewport:(MTLViewport){0,0,64,48,0,1}];[e setRenderPipelineState:marker];[e setVertexBuffer:markerV offset:0 atIndex:0];[e setVertexBufferOffset:64 atIndex:0];if(trial%2)[e setVertexBytes:mp length:16 atIndex:1];else[e setVertexBuffer:markerP offset:128 atIndex:1];if(trial%2)[e setFragmentBytes:mp length:16 atIndex:0];else[e setFragmentBuffer:markerP offset:128 atIndex:0];
        MTLScissorRect scissor=trial%2?MTLScissorRect{3,4,57,39}:MTLScissorRect{0,0,64,48};[e setScissorRect:scissor];
        uint32_t v=values[(trial*5+3)%16],first=0,count=4;if(trial==1){first=v%4;count=1;}else if(trial==2)count=1+v%4;else if(trial==3){first=v%4;count=4-first;}else if(trial==4){first=v%4;count=0;}else if(trial==5){first=5;count=0;}else if(trial==6){first=0xfffffffe;count=3;}else if(trial==7){first=0;count=0;}
        if(gpuRecords){first=0;count=trial==7||noProducer?0:4;}
        BOOL valid=first<=4&&count<=4-MIN(first,4u);
        auto rejectCall=[&](NSString*name,void(^call)(void)){BOOL rejected=NO;@try{call();}@catch(NSException*x){rejected=YES;}if(rejected)[refusals addObject:name];return rejected;};
        if(backup){
            if(!rejectCall(@"wrong_range_object",^{[e executeCommandsInBuffer:icb indirectBuffer:seeds indirectBufferOffset:64];})||!rejectCall(@"wrong_range_offset",^{[e executeCommandsInBuffer:icb indirectBuffer:range indirectBufferOffset:0];})||!rejectCall(@"copied_ICB_has_no_preparation",^{[e executeCommandsInBuffer:backup indirectBuffer:range indirectBufferOffset:64];}))return 12;
            if(trial==0)[[icb indirectRenderCommandAtIndex:0]setVertexBuffer:vbo[0]offset:80 atIndex:0];else[icb resetWithRange:NSMakeRange(1,1)];
            if(!rejectCall(trial==0?@"mutated_command":@"reset_command",^{[e executeCommandsInBuffer:icb indirectBuffer:range indirectBufferOffset:64];}))return 12;
            if(!KPCopyCPUICBCommands(backup,NSMakeRange(0,4),icb,0,&error))return 12;
        }
        if(consume){@try{
            if(reference){for(unsigned i=0;i<3;i++){unsigned slot=i==2?3:i;if(!valid||slot<first||slot-first>=count)continue;uint32_t a[5]={};if(gpuRecords&&!referenceArguments(trial,slot,v,a))continue;[e setRenderPipelineState:legacyMode?scope.renderPipeline:[scope renderPipelineForName:@[@"smooth",@"linear",@"flat"][i]]];if(!legacyMode){[e setVertexBuffer:vbo[i]offset:64 atIndex:0];[e setVertexBuffer:instances offset:128 atIndex:1];}if(fragment)[e setFragmentBuffer:fragmentPrivate[i]offset:256 atIndex:0];if(!i)[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:gpuRecords?a[2]:legacyMode?0:5 vertexCount:gpuRecords?a[0]:legacyMode?3:6 instanceCount:1 baseInstance:0];else[e drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:gpuRecords?a[0]:legacyMode?3:6 indexType:i==1?MTLIndexTypeUInt16:MTLIndexTypeUInt32 indexBuffer:i==1?index16:index32 indexBufferOffset:64+(gpuRecords?a[2]*(i==1?2:4):0) instanceCount:1 baseVertex:legacyMode?0:i==1?2:-2 baseInstance:legacyMode?0:i==1?1:2];}[e setRenderPipelineState:marker];[e setVertexBuffer:markerV offset:64 atIndex:0];if(trial%2)[e setVertexBytes:mp length:16 atIndex:1];else[e setVertexBuffer:markerP offset:128 atIndex:1];if(trial%2)[e setFragmentBytes:mp length:16 atIndex:0];else[e setFragmentBuffer:markerP offset:128 atIndex:0];}
            else[e executeCommandsInBuffer:icb indirectBuffer:range indirectBufferOffset:64];
        }@catch(NSException*x){[e endEncoding];emit(@{@"failure":@"execute",@"reason":x.reason?:@""});return 8;}}
        if(backup&&!rejectCall(@"duplicate_execution",^{[e executeCommandsInBuffer:icb indirectBuffer:range indirectBufferOffset:64];}))return 12;
        Class nativeEncoderClass=class_getSuperclass(object_getClass(e));uintptr_t identity=(uintptr_t)(__bridge const void*)icb;
        [e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6 instanceCount:1 baseInstance:0];[e endEncoding];
        b=[cb blitCommandEncoder];[b copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)sourceSize:MTLSizeMake(64,48,1)toBuffer:image destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];
        for(unsigned i=0;i<buffers.count;i++){id<MTLBuffer>g=buffers[i];[b copyFromBuffer:g sourceOffset:0 toBuffer:reads[i]destinationOffset:0 size:g.length];}if(args){[b copyFromBuffer:args sourceOffset:0 toBuffer:argsHost destinationOffset:0 size:args.length];[b copyFromBuffer:witness sourceOffset:0 toBuffer:witnessHost destinationOffset:0 size:witness.length];}for(unsigned i=0;i<fragmentTextures.count;i++)[b copyFromTexture:fragmentTextures[i]sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)sourceSize:MTLSizeMake(64,48,1)toBuffer:fragmentReads[i]destinationOffset:0 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[b endEncoding];BOOL released=NO,restoredBeforeCommit=NO;
        if(release){releasedScope=scope;releasedICB=icb;if(fragment){releasedTexture=fragmentTextures[1];releasedSampler=fragmentSamplers[1];}}
        if(release||(lifetime&&trial==7)){[scope restore];restoredBeforeCommit=object_getClass(d)==original&&object_getClass(e)==nativeEncoderClass;savedEvents=scope.events;scope=nil;persistent=nil;icb=nil;plan=nil;args=nil;witness=nil;for(unsigned i=0;i<3;i++)vbo[i]=nil;instances=nil;index16=nil;index32=nil;markerV=nil;markerP=nil;seeds=nil;range=nil;counter=nil;config=nil;recordSource=nil;marker=nil;producer=nil;[buffers removeAllObjects];[uploads removeAllObjects];[fragmentTextures removeAllObjects];[fragmentSamplers removeAllObjects];[fragmentParams removeAllObjects];[fragmentShared removeAllObjects];[fragmentPrivate removeAllObjects];[fragmentUploads removeAllObjects];released=YES;}
        if(release){
            // Capture numerical readbacks and scalar metadata only. The outer
            // main drains this entire call's autorelease pool before commit.
            NSArray *events=savedEvents;
            NSDictionary *identityRow=KPKepler880MIdentity(d);
            NSString *deviceName=d.name;
            NSNumber *registry=@(d.registryID);
            deferredBuffer=cb;
            deferredReadback=^{
                NSString *prefix=@"trial-0";
                save(image,dir,[prefix stringByAppendingString:@".image.bin"]);
                for(unsigned i=0;i<reads.count;i++)save(reads[i],dir,[prefix stringByAppendingFormat:@".buffer-%u.bin",i]);
                save(argsHost,dir,[prefix stringByAppendingString:@".arguments.bin"]);
                save(witnessHost,dir,[prefix stringByAppendingString:@".witness.bin"]);
                for(unsigned i=0;i<fragmentReads.count;i++)save(fragmentReads[i],dir,[prefix stringByAppendingFormat:@".texture-%u.bin",i]);
                NSDictionary *row=@{@"fragment_resources":@(fragment),@"legacy_geometry":@NO,
                    @"api_refusals":@[],@"ICB_object_identity":@(identity),
                    @"released_before_commit":@YES,@"classes_restored_before_commit":@(restoredBeforeCommit),
                    @"autorelease_pool_drained_before_commit":@(releasePoolDrained),
                    @"scope_deallocated_before_commit":@(scopeGoneBeforeCommit),
                    @"ICB_deallocated_before_commit":@(icbGoneBeforeCommit),
                    @"fragment_texture_alive_before_commit":@(textureAliveBeforeCommit),
                    @"fragment_sampler_alive_before_commit":@(samplerAliveBeforeCommit),
                    @"trial":@0,@"expected_range":@[@0,@4],@"scissor":@[@0,@0,@64,@48],
                    @"native_reference":@NO,@"consumer_encoded":@YES,@"producer_dispatches":@1,
                    @"command_status":@(cb.status),@"inline_marker_parameter":@NO};
                emit(@{@"status":@"COMPLETED",@"device":deviceName,@"registry_id":registry,
                    @"device_identity":identityRow,@"mode":mode,@"runs":@[row],@"scope_events":events,
                    @"scope_restored":@(restoredBeforeCommit),@"range_CPU_read_before_render":@NO,
                    @"CPU_resolved_range_supplied":@NO,@"performance_benchmark":@NO});
            };
            return 0;
        }
        [cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted){emit(@{@"failure":@"completion",@"error":cb.error.description?:@""});return 9;}
        NSString*prefix=[NSString stringWithFormat:@"trial-%u",trial];save(image,dir,[prefix stringByAppendingString:@".image.bin"]);for(unsigned i=0;i<reads.count;i++)save(reads[i],dir,[prefix stringByAppendingFormat:@".buffer-%u.bin",i]);if(argsHost){save(argsHost,dir,[prefix stringByAppendingString:@".arguments.bin"]);save(witnessHost,dir,[prefix stringByAppendingString:@".witness.bin"]);}
        for(unsigned i=0;i<fragmentReads.count;i++)save(fragmentReads[i],dir,[prefix stringByAppendingFormat:@".texture-%u.bin",i]);
        [runs addObject:@{@"fragment_resources":@(fragment),@"legacy_geometry":@(legacyMode),@"api_refusals":refusals,@"ICB_object_identity":@(identity),@"released_before_commit":@(released),@"classes_restored_before_commit":@(restoredBeforeCommit),@"trial":@(trial),@"expected_range":@[@(first),@(count)],@"scissor":@[@(scissor.x),@(scissor.y),@(scissor.width),@(scissor.height)],@"native_reference":@(reference),@"consumer_encoded":@(consume),@"producer_dispatches":trial==7||noProducer?@0:@1,@"command_status":@(cb.status),@"inline_marker_parameter":@(trial%2!=0)}];
    }}
    [scope restore];BOOL restored=object_getClass(d)==original;
    emit(@{@"status":restored?@"COMPLETED":@"FAIL",@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":KPKepler880MIdentity(d),@"mode":mode,@"runs":runs,@"scope_events":scope?scope.events:savedEvents,@"scope_restored":@(restored),@"range_CPU_read_before_render":@NO,@"CPU_resolved_range_supplied":@(reference),@"performance_benchmark":@NO});return restored?0:10;
}
int main(int argc,char **argv){
    int result=0;
    @autoreleasepool {
        @autoreleasepool { result=runClient(argc,argv); }
        if(!result&&deferredBuffer){
            releasePoolDrained=YES;
            scopeGoneBeforeCommit=releasedScope==nil;
            icbGoneBeforeCommit=releasedICB==nil;
            textureAliveBeforeCommit=releasedTexture!=nil;
            samplerAliveBeforeCommit=releasedSampler!=nil;
            [deferredBuffer commit];
            [deferredBuffer waitUntilCompleted];
            if(deferredBuffer.status!=MTLCommandBufferStatusCompleted){
                emit(@{@"failure":@"deferred completion",@"error":deferredBuffer.error.description?:@""});
                result=9;
            }else deferredReadback();
            deferredReadback=nil;
            deferredBuffer=nil;
        }
    }
    return result;
}
