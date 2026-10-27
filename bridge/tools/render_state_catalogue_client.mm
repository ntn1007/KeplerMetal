// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#import "KeplerRenderStateRecords.h"
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#include <stdexcept>
#include <vector>
#if KP_RENDER_ARGUMENT_ENCODERS
#include <thread>
#endif

static void require(bool value,const char *message){if(!value)throw std::runtime_error(message);}
static NSString *sha(NSData *data){unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);NSMutableString *s=[NSMutableString new];for(auto b:h)[s appendFormat:@"%02x",b];return s;}
static void emit(id value){NSData *data=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];require(data!=nil,"JSON encoding");fwrite(data.bytes,1,data.length,stdout);puts("");}
static NSData *load(NSString *assets,NSString *name){NSData *data=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:name]];require(data!=nil,"asset missing");return data;}
#ifndef KP_AIR_RENDER_RESET
#define KP_AIR_RENDER_RESET 0
#endif
#if KP_AIR_RENDER_RESET
#include "AIRRenderResetIntegration.inc"
#endif
struct Vertex{float position[4],color[4];};
static NSData *vertices(unsigned first,bool indexed,unsigned logical,unsigned state){
    static const float colors[2][3][4]={{{.25,.125,.75,1},{.125,.75,.25,1},{.75,.5,.125,1}},{{.5,.375,.25,1},{.375,.25,.5,1},{.125,.5,.625,1}}};
    float x0=logical==0?0:logical==1?32:16,x1=logical==0?32:logical==1?64:48;
    float y0=logical==2?12:0,y1=logical==2?36:48;
    float xy[4][2]={{x0,y1},{x1,y1},{x0,y0},{x1,y0}};unsigned order[]={0,1,2,2,1,3};
    NSMutableData *data=[NSMutableData dataWithLength:4096];memset(data.mutableBytes,0xa5,data.length);
    for(unsigned i=0;i<(indexed?4u:6u);i++){unsigned j=indexed?i:order[i];Vertex v={{xy[j][0]/32.f-1.f,1.f-xy[j][1]/24.f,.5,1},{}};memcpy(v.color,colors[state][logical],16);memcpy((char*)data.mutableBytes+64+(first+i)*32,&v,32);}
    return data;
}
static unsigned functionIndex(unsigned logical,unsigned state,bool resourcesOnly){
    static const unsigned choices[2][3]={{0,1,2},{1,0,1}};
    return choices[resourcesOnly?0:state][logical];
}
static bool accepted(unsigned trial,unsigned slot){
    return trial!=7&&!((trial==1&&slot==1)||(trial==2&&slot==3)||(trial==3&&slot==0)||
        (trial==4&&slot==1)||(trial==5&&slot==3)||(trial==6&&slot==0));
}
@interface WeakObject:NSObject
@property(nonatomic,weak) id value;
@end
@implementation WeakObject
@end
@interface StateCapture:NSObject
@property(nonatomic,strong) id<MTLCommandBuffer> commandBuffer;
@property(nonatomic,strong) NSMutableDictionary<NSString*,id<MTLBuffer>> *readbacks;
@property(nonatomic,strong) NSArray<WeakObject*> *weakOwners;
@property(nonatomic,strong) NSMutableDictionary *row;
@property(nonatomic,strong) NSArray *events;
@end
@implementation StateCapture
@end
static WeakObject *weak(id value){WeakObject *box=[WeakObject new];box.value=value;return box;}

static StateCapture *encodeFrame(id<MTLDevice>device,id<MTLCommandQueue>queue,NSString *assets,
    id<MTLComputePipelineState>producer,id<MTLRenderPipelineState>marker,unsigned trial,NSString *mode){
    bool native=[mode hasSuffix:@"native"],pipelineOnly=[mode hasPrefix:@"pipeline_only"],resourcesOnly=[mode hasPrefix:@"resources_only"];
    bool produce=trial!=7&&![mode isEqual:@"no_producer"],consume=![mode isEqual:@"no_consumer"];
    NSError *error=nil;Class original=object_getClass(device);
    NSData *legacy=load(assets,@"render_state_carrier.metallib"),*library=load(assets,@"combined_render_resources.metallib"),*profile=load(assets,@"combined.json"),*materializer=load(assets,@"state.metallib");
    KPCPUICBScope *scope=[KPCPUICBScope installRenderingOnDevice:device queue:queue libraryData:legacy expectedSHA256:sha(legacy)error:&error];
    BOOL registered=scope&&[scope registerRenderVertexLibraryData:library expectedSHA256:sha(library)manifestData:profile expectedManifestSHA256:sha(profile)error:&error];require(registered,error.description.UTF8String?:"scope registration");
    BOOL enabled=[scope enableGPURenderStateCatalogueWithLibraryData:materializer expectedSHA256:sha(materializer)error:&error];require(enabled,error.description.UTF8String?:"state registration");
#if KP_RENDER_ARGUMENT_ENCODERS
#include "RenderRecordArgumentsSetup.inc"
#endif
    StateCapture *capture=[StateCapture new];capture.readbacks=[NSMutableDictionary new];
    id<MTLCommandBuffer>cb=[queue commandBuffer];require(cb&&cb.retainedReferences,"retained command buffer");capture.commandBuffer=cb;
    NSMutableDictionary<NSString*,id<MTLBuffer>> *buffers=[NSMutableDictionary new];
    NSMutableArray *leases=[NSMutableArray new];
    auto privateBuffer=[&](NSString *name,NSData *data)->id<MTLBuffer>{
        id<MTLBuffer>stage=[device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared],gpu=[device newBufferWithLength:data.length options:MTLResourceStorageModePrivate],read=[device newBufferWithLength:data.length options:MTLResourceStorageModeShared];
        require(stage&&gpu&&read,"buffer allocation");id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:stage sourceOffset:0 toBuffer:gpu destinationOffset:0 size:data.length];[b endEncoding];buffers[name]=gpu;capture.readbacks[name]=read;return gpu;
    };
    auto bytes=[&](NSUInteger length)->NSMutableData*{NSMutableData *data=[NSMutableData dataWithLength:length];memset(data.mutableBytes,0xa5,length);return data;};
    id<MTLBuffer>vbo[2][3];
    for(unsigned state=0;state<2;state++)for(unsigned i=0;i<3;i++){
        if(state&&pipelineOnly){vbo[state][i]=vbo[0][i];continue;}
        vbo[state][i]=privateBuffer([NSString stringWithFormat:@"state-%u.vertex-%u",state,i],vertices(i==0?5:i==1?7:3,i!=0,i,state));
    }
    NSMutableData *instanceData=bytes(512);memset((char*)instanceData.mutableBytes+128,0,128);id<MTLBuffer>instances=privateBuffer(@"instances",instanceData);
    id<MTLBuffer>indices[2];unsigned order[]={5,6,7,7,6,8};
    for(unsigned kind=0;kind<2;kind++){NSMutableData *data=bytes(256);for(unsigned i=0;i<6;i++)if(kind)((uint32_t*)((char*)data.mutableBytes+64))[i]=order[i];else((uint16_t*)((char*)data.mutableBytes+64))[i]=order[i];indices[kind]=privateBuffer([NSString stringWithFormat:@"indices-%u",kind],data);}
#if KP_TYPED_INDEXED_RENDER
    if([mode isEqual:@"indexed_contracts"]){NSMutableData *data=bytes(256);for(unsigned i=0;i<6;i++)((uint16_t*)((char*)data.mutableBytes+64))[i]=order[i];indices[0]=[device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];require(indices[0]!=nil,"shared certified index allocation");buffers[@"indices-0"]=indices[0];}
#endif
    NSMutableData *markerData=[vertices(0,false,0,0)mutableCopy];
    // Marker uses only x in [0,8), unlike the candidate's left rectangle.
    for(unsigned i=0;i<6;i++){Vertex *v=(Vertex*)((char*)markerData.mutableBytes+64+i*32);v->position[0]=(v->position[0]+1.f)/4.f-1.f;}
    id<MTLBuffer>markerVertices=privateBuffer(@"marker.vertices",markerData);
    NSMutableData *markerParams=bytes(512);float mp[]={0,0,.625,0};memcpy((char*)markerParams.mutableBytes+128,mp,16);id<MTLBuffer>markerBuffer=privateBuffer(@"marker.parameters",markerParams);
    id<MTLTexture>textures[2];id<MTLBuffer>textureRead[2];
    for(unsigned bank=0;bank<2;bank++){
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageShaderRead;textures[bank]=[device newTextureWithDescriptor:td];
        std::vector<float>pixels(64*48*4);for(unsigned y=0;y<48;y++)for(unsigned x=0;x<64;x++){float *p=&pixels[(y*64+x)*4];p[0]=bank?float(7-x%8)/8:float(x%8)/16;p[1]=bank?float(7-y%8)/8:float(y%8)/16;p[2]=bank?float((2*x+y)%8)/8:float((x+y)%8)/16;p[3]=1;}
        id<MTLBuffer>stage=[device newBufferWithBytes:pixels.data()length:pixels.size()*4 options:MTLResourceStorageModeShared];textureRead[bank]=[device newBufferWithLength:pixels.size()*4 options:MTLResourceStorageModeShared];require(textures[bank]&&stage&&textureRead[bank],"texture allocation");
        id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromBuffer:stage sourceOffset:0 sourceBytesPerRow:1024 sourceBytesPerImage:49152 sourceSize:MTLSizeMake(64,48,1)toTexture:textures[bank]destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];[b endEncoding];[leases addObject:textures[bank]];
    }
    id<MTLBuffer>fragmentTables[2][3];id<MTLSamplerState>samplers[2][3];
    for(unsigned state=0;state<2;state++)for(unsigned i=0;i<3;i++){
        if(state&&pipelineOnly){fragmentTables[state][i]=fragmentTables[0][i];samplers[state][i]=samplers[0][i];continue;}
        unsigned function=functionIndex(i,state,resourcesOnly);NSString *name=@[@"smooth",@"linear",@"flat"][function];
        MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];sd.minFilter=sd.magFilter=MTLSamplerMinMagFilterLinear;sd.sAddressMode=sd.tAddressMode=state?MTLSamplerAddressModeRepeat:MTLSamplerAddressModeClampToEdge;sd.supportArgumentBuffers=YES;samplers[state][i]=[device newSamplerStateWithDescriptor:sd];
        NSMutableData *parameters=bytes(512);float p[3][8]={{.5,1,1,1,.125,0,0,0},{1,1.5,.5,1,0,.125,0,0},{.75,.5,2,1,0,0,.25,0}};if(state){p[i][4]+=.0625;p[i][5]+=.03125;p[i][6]+=.015625;}memcpy((char*)parameters.mutableBytes+256,p[i],32);
        id<MTLBuffer>params=privateBuffer([NSString stringWithFormat:@"state-%u.parameters-%u",state,i],parameters);
        id<MTLBuffer>shared=[device newBufferWithLength:1024 options:MTLResourceStorageModeShared];memset(shared.contents,0xa5,shared.length);
        NSDictionary *resources=@{@0:textures[state],@1:samplers[state][i],@2:@{@"buffer":params,@"offset":@256}};
        BOOL encoded=[scope encodeFragmentArgumentBuffer:shared offset:256 pipelineName:name bindingIndex:0 resources:resources error:&error];require(encoded,error.description.UTF8String?:"argument encoding");
        fragmentTables[state][i]=[scope newPrivateFragmentArgumentBufferForPipeline:name bindingIndex:0 sources:@[@{@"buffer":shared,@"offset":@256}]selectedBank:0 commandBuffer:cb counter:nil error:&error];require(fragmentTables[state][i]!=nil,error.description.UTF8String?:"private table");
        [leases addObjectsFromArray:@[params,samplers[state][i],shared,fragmentTables[state][i]]];
    }
    MTLIndirectCommandBufferDescriptor *descriptor=[MTLIndirectCommandBufferDescriptor new];descriptor.commandTypes=MTLIndirectCommandTypeDraw|MTLIndirectCommandTypeDrawIndexed;descriptor.maxVertexBufferBindCount=2;descriptor.maxFragmentBufferBindCount=1;
    id<MTLIndirectCommandBuffer>commands[2];
    for(unsigned state=0;state<2;state++){
        commands[state]=[device newIndirectCommandBufferWithDescriptor:descriptor maxCommandCount:4 options:MTLResourceStorageModeShared];require(commands[state]!=nil,"ICB allocation");
        for(unsigned i=0;i<3;i++){
            unsigned slot=i==2?3:i,function=functionIndex(i,state,resourcesOnly);id<MTLIndirectRenderCommand>c=[commands[state]indirectRenderCommandAtIndex:slot];
            [c setRenderPipelineState:[scope renderPipelineForName:@[@"smooth",@"linear",@"flat"][function]]];[c setVertexBuffer:vbo[state][i]offset:64 atIndex:0];[c setVertexBuffer:instances offset:128 atIndex:1];[c setFragmentBuffer:fragmentTables[state][i]offset:256 atIndex:0];
            if(!i)[c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:5 vertexCount:6 instanceCount:1 baseInstance:0];else[c drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:6 indexType:i==1?MTLIndexTypeUInt16:MTLIndexTypeUInt32 indexBuffer:indices[i-1]indexBufferOffset:64 instanceCount:1 baseVertex:i==1?2:-2 baseInstance:i==1?1:2];
        }
    }
    KPRenderStateCatalogue *foreign=[scope newRenderStateCatalogueWithCommands:commands[0]alternatives:@[commands[1]]error:&error];
    KPRenderStateCatalogue *catalogue=[scope newRenderStateCatalogueWithCommands:commands[0]alternatives:@[commands[1]]error:&error];require(foreign&&catalogue,error.description.UTF8String?:"catalogue creation");
    NSArray *ids=catalogue.stateIdentifiers,*foreignIDs=foreign.stateIdentifiers;
    for(unsigned which=0;which<2;which++){NSMutableData *data=bytes(144);for(unsigned i=0;i<2;i++)((uint64_t*)((char*)data.mutableBytes+64))[i]=[(which?foreignIDs[i]:ids[i])unsignedLongLongValue];privateBuffer(which?@"foreign-identities":@"identities",data);}
    NSMutableData *seeds=bytes(192);uint32_t values[16];for(unsigned i=0;i<16;i++)values[i]=(0x13579bdu+i*97u+trial*17u)^0xa3b5c7d9u;memcpy((char*)seeds.mutableBytes+64,values,64);privateBuffer(@"seeds",seeds);
    NSMutableData *range=bytes(136),*counter=bytes(132),*records=bytes(384);memset((char*)range.mutableBytes+64,0,8);memset((char*)counter.mutableBytes+64,0,4);memset((char*)records.mutableBytes+64,0,256);privateBuffer(@"range",range);privateBuffer(@"counter",counter);privateBuffer(@"records",records);
    uint32_t config[4]={trial,trial,4,[mode isEqual:@"forced_0"]?1u:[mode isEqual:@"forced_1"]?2u:0u};id<MTLBuffer>cfg=[device newBufferWithLength:256 options:MTLResourceStorageModeShared];memset(cfg.contents,0,256);memcpy(cfg.contents,config,16);
    if(produce){id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:producer];[e setBuffer:buffers[@"seeds"]offset:64 atIndex:0];[e setBuffer:buffers[@"range"]offset:64 atIndex:1];[e setBuffer:buffers[@"counter"]offset:64 atIndex:2];[e setBuffer:cfg offset:0 atIndex:3];[e setBuffer:buffers[@"identities"]offset:64 atIndex:4];[e setBuffer:buffers[@"records"]offset:64 atIndex:5];[e setBuffer:buffers[@"foreign-identities"]offset:64 atIndex:6];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];}
#if KP_AIR_RENDER_RESET
#if KP_RENDER_ARGUMENT_ENCODERS
#include "RenderRecordArgumentsEncode.inc"
#else
#include "AIRRenderResetEncode.inc"
#endif
#endif
    NSMutableArray *refusals=[NSMutableArray new];
    id<MTLIndirectCommandBuffer>backup=nil,backupAlternative=nil;
    if([mode isEqual:@"contracts"]&&trial<2){
        auto refused=[&](NSString *name,BOOL result,NSError *failure){require(!result&&failure!=nil,"expected API refusal");[refusals addObject:name];};
        error=nil;KPRenderStateCatalogue *bad=[scope newRenderStateCatalogueWithCommands:commands[0]alternatives:@[commands[0]]error:&error];refused(@"duplicate_source",bad!=nil,error);
        id<MTLIndirectCommandBuffer>other=[device newIndirectCommandBufferWithDescriptor:descriptor maxCommandCount:5 options:MTLResourceStorageModeShared];
        error=nil;bad=[scope newRenderStateCatalogueWithCommands:commands[0]alternatives:@[other]error:&error];refused(@"source_capacity",bad!=nil,error);
        id<MTLIndirectCommandBuffer>large=[device newIndirectCommandBufferWithDescriptor:descriptor maxCommandCount:9 options:MTLResourceStorageModeShared],largeAlternative=[device newIndirectCommandBufferWithDescriptor:descriptor maxCommandCount:9 options:MTLResourceStorageModeShared];
        error=nil;bad=[scope newRenderStateCatalogueWithCommands:large alternatives:@[largeAlternative]error:&error];refused(@"expanded_capacity",bad!=nil,error);
        error=nil;BOOL result=[scope enableGPURenderStateCatalogueWithLibraryData:materializer expectedSHA256:@"0000000000000000000000000000000000000000000000000000000000000000" error:&error];refused(@"wrong_kernel_pin",result,error);
        error=nil;result=[scope prepareIndirectRenderCommands:commands[1]stateCatalogue:catalogue commandRecords:buffers[@"records"]commandRecordsOffset:64 indirectBuffer:buffers[@"range"]indirectBufferOffset:64 commandBuffer:cb error:&error];refused(@"wrong_execution_ICB",result,error);
        id<MTLBuffer>shortRecords=[device newBufferWithLength:255 options:MTLResourceStorageModeShared];
        error=nil;result=[scope prepareIndirectRenderCommands:commands[0]stateCatalogue:catalogue commandRecords:shortRecords commandRecordsOffset:0 indirectBuffer:buffers[@"range"]indirectBufferOffset:64 commandBuffer:cb error:&error];refused(@"short_records",result,error);
        error=nil;result=[scope prepareIndirectRenderCommands:commands[0]stateCatalogue:catalogue commandRecords:buffers[@"records"]commandRecordsOffset:68 indirectBuffer:buffers[@"range"]indirectBufferOffset:64 commandBuffer:cb error:&error];refused(@"misaligned_records",result,error);
        error=nil;result=[scope prepareIndirectRenderCommands:commands[0]stateCatalogue:catalogue commandRecords:buffers[@"records"]commandRecordsOffset:64 indirectBuffer:buffers[@"range"]indirectBufferOffset:65 commandBuffer:cb error:&error];refused(@"misaligned_range",result,error);
        backup=[device newIndirectCommandBufferWithDescriptor:descriptor maxCommandCount:4 options:MTLResourceStorageModeShared];backupAlternative=[device newIndirectCommandBufferWithDescriptor:descriptor maxCommandCount:4 options:MTLResourceStorageModeShared];
        require(KPCopyCPUICBCommands(commands[0],NSMakeRange(0,4),backup,0,&error)&&KPCopyCPUICBCommands(commands[1],NSMakeRange(0,4),backupAlternative,0,&error),"backup source snapshots");
    }
    if(!native){BOOL prepared=[scope prepareIndirectRenderCommands:commands[0]stateCatalogue:catalogue commandRecords:buffers[@"records"]commandRecordsOffset:64 indirectBuffer:buffers[@"range"]indirectBufferOffset:64 commandBuffer:cb error:&error];require(prepared,error.description.UTF8String?:"catalogue preparation");}
    if(backup){error=nil;BOOL result=[scope prepareIndirectRenderCommands:commands[0]stateCatalogue:catalogue commandRecords:buffers[@"records"]commandRecordsOffset:64 indirectBuffer:buffers[@"range"]indirectBufferOffset:64 commandBuffer:cb error:&error];require(!result&&error!=nil,"pending preparation refusal");[refusals addObject:@"pending_preparation"];}
    id plan=native?nil:[(id)commands[0]valueForKey:@"indirectRenderPlan"];id<MTLBuffer>args=plan?[plan valueForKey:@"arguments"]:nil,witness=plan?[plan valueForKey:@"witness"]:nil;
    id<MTLBuffer>templates=plan?[plan valueForKey:@"templates"]:nil;
    for(NSString *name in @[@"arguments",@"witness",@"templates"]){id<MTLBuffer>source=[name isEqual:@"arguments"]?args:[name isEqual:@"witness"]?witness:templates;if(source)capture.readbacks[name]=[device newBufferWithLength:source.length options:MTLResourceStorageModeShared];}
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[device newTextureWithDescriptor:td];id<MTLBuffer>image=[device newBufferWithLength:49664 options:MTLResourceStorageModeShared];require(target&&image,"target allocation");memset(image.contents,0xa5,image.length);capture.readbacks[@"image"]=image;
    MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
    id<MTLRenderCommandEncoder>e=[scope renderEncoderWithDescriptor:pass commandBuffer:cb error:&error];require(e!=nil,"render encoder");Class nativeClass=class_getSuperclass(object_getClass(e));
    [e setViewport:(MTLViewport){0,0,64,48,0,1}];[e setRenderPipelineState:marker];[e setVertexBuffer:markerVertices offset:64 atIndex:0];if(trial%2){[e setVertexBytes:mp length:16 atIndex:1];[e setFragmentBytes:mp length:16 atIndex:0];}else{[e setVertexBuffer:markerBuffer offset:128 atIndex:1];[e setFragmentBuffer:markerBuffer offset:128 atIndex:0];}
    MTLScissorRect scissor=trial%2?MTLScissorRect{3,4,57,39}:MTLScissorRect{0,0,64,48};[e setScissorRect:scissor];
    id<MTLIndirectCommandBuffer>executionCommands=commands[0];
    auto rejectCall=[&](NSString *name,void(^call)(void)){BOOL rejected=NO;@try{call();}@catch(NSException *exception){rejected=YES;}require(rejected,"expected execution refusal");[refusals addObject:name];};
    if(backup){
        rejectCall(@"wrong_range_object",^{[e executeCommandsInBuffer:executionCommands indirectBuffer:buffers[@"seeds"]indirectBufferOffset:64];});
        rejectCall(@"wrong_range_offset",^{[e executeCommandsInBuffer:executionCommands indirectBuffer:buffers[@"range"]indirectBufferOffset:0];});
        rejectCall(@"copy_has_no_preparation",^{[e executeCommandsInBuffer:backup indirectBuffer:buffers[@"range"]indirectBufferOffset:64];});
        [commands[1]resetWithRange:NSMakeRange(1,1)];
        rejectCall(@"mutated_alternative",^{[e executeCommandsInBuffer:executionCommands indirectBuffer:buffers[@"range"]indirectBufferOffset:64];});
        require(KPCopyCPUICBCommands(backupAlternative,NSMakeRange(0,4),commands[1],0,&error),"restore exact alternative snapshot");
    }
    if(consume){if(native){
        uint32_t value=values[(trial*5+3)%16];
        for(unsigned i=0;i<3;i++){
            unsigned slot=i==2?3:i;if(!produce)continue;
#if KP_TYPED_INDEXED_RENDER
            if(i&&airDispatchesReset(mode)){if(!airIndexReferenceAccepted(trial,i,mode))continue;}
            else if(!accepted(trial,slot))continue;
#elif KP_TYPED_RENDER_DRAW
            if(!i&&airDispatchesReset(mode)){if(!airDrawReferenceAccepted(trial,mode))continue;}
            else if(!accepted(trial,slot))continue;
#else
            if(!accepted(trial,slot))continue;
#endif
#if KP_AIR_RENDER_RESET
            if(slot==3&&airAppliesReset(mode))continue;
#endif
            unsigned state=(value>>(i+3))&1,start=(i==0?5:0)+3*((value>>i)&1),function=functionIndex(i,state,resourcesOnly);
            uint32_t drawCount=3,drawInstances=1,drawBase=0;
#if KP_TYPED_RENDER_DRAW
            if(!i&&airDispatchesReset(mode)){uint32_t seed=airDrawSeed(trial);start=5u+3u*((seed>>3)&1u);drawCount=3u*((seed>>4)&3u);drawInstances=(seed>>6)&1u;drawBase=(seed>>8)&3u;}
#endif
#if KP_TYPED_INDEXED_RENDER
            if(i&&airDispatchesReset(mode))airIndexDrawArguments(trial,i,mode,start,drawCount,drawInstances);
#endif
            [e setRenderPipelineState:[scope renderPipelineForName:@[@"smooth",@"linear",@"flat"][function]]];[e setVertexBuffer:vbo[state][i]offset:64 atIndex:0];[e setVertexBuffer:instances offset:128 atIndex:1];[e setFragmentBuffer:fragmentTables[state][i]offset:256 atIndex:0];
            if(!i)[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:start vertexCount:drawCount instanceCount:drawInstances baseInstance:drawBase];else[e drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:drawCount indexType:i==1?MTLIndexTypeUInt16:MTLIndexTypeUInt32 indexBuffer:indices[i-1]indexBufferOffset:64+start*(i==1?2:4)instanceCount:drawInstances baseVertex:i==1?2:-2 baseInstance:i==1?1:2];
            for(id resource in leases)if([resource conformsToProtocol:@protocol(MTLResource)])[e useResource:resource usage:MTLResourceUsageRead stages:MTLRenderStageFragment];
        }
        [e setRenderPipelineState:marker];[e setVertexBuffer:markerVertices offset:64 atIndex:0];if(trial%2){[e setVertexBytes:mp length:16 atIndex:1];[e setFragmentBytes:mp length:16 atIndex:0];}else{[e setVertexBuffer:markerBuffer offset:128 atIndex:1];[e setFragmentBuffer:markerBuffer offset:128 atIndex:0];}
        NSArray *keep=[leases copy];[cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)keep.count;}];
    }else[e executeCommandsInBuffer:commands[0]indirectBuffer:buffers[@"range"]indirectBufferOffset:64];}
    if(backup)rejectCall(@"duplicate_execution",^{[e executeCommandsInBuffer:executionCommands indirectBuffer:buffers[@"range"]indirectBufferOffset:64];});
    [e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6 instanceCount:1 baseInstance:0];[e endEncoding];
    id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];[b copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)sourceSize:MTLSizeMake(64,48,1)toBuffer:image destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];
    for(NSString *name in buffers){id<MTLBuffer>source=buffers[name];[b copyFromBuffer:source sourceOffset:0 toBuffer:capture.readbacks[name]destinationOffset:0 size:source.length];}
    if(templates)[b copyFromBuffer:templates sourceOffset:0 toBuffer:capture.readbacks[@"templates"]destinationOffset:0 size:templates.length];
    if(args){[b copyFromBuffer:args sourceOffset:0 toBuffer:capture.readbacks[@"arguments"]destinationOffset:0 size:args.length];[b copyFromBuffer:witness sourceOffset:0 toBuffer:capture.readbacks[@"witness"]destinationOffset:0 size:witness.length];}
    for(unsigned bank=0;bank<2;bank++){[b copyFromTexture:textures[bank]sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)sourceSize:MTLSizeMake(64,48,1)toBuffer:textureRead[bank]destinationOffset:0 destinationBytesPerRow:1024 destinationBytesPerImage:49152];capture.readbacks[[NSString stringWithFormat:@"texture-%u",bank]]=textureRead[bank];}[b endEncoding];
    capture.weakOwners=@[weak(scope),weak(commands[0]),weak(commands[1]),weak(samplers[0][1]),weak(samplers[1][1])];
    [scope restore];require(object_getClass(device)==original&&object_getClass(e)==nativeClass,"class restoration");capture.events=scope.events;
#if KP_RENDER_ARGUMENT_ENCODERS
    require(object_getClass(recordProducerFunction)==recordProducerNativeClass,"render root function class restoration");
    require([recordProducerFunction newArgumentEncoderWithBufferIndex:0].encodedLength==0,"native root getter restoration");
    if([mode isEqual:@"arguments_contracts"]&&trial==0){BOOL refused=NO;@try{[recordArgumentEncoder setArgumentBuffer:resetRootGPU offset:64];}@catch(NSException*x){refused=YES;}require(refused,"restored encoder must refuse");[recordRefusals addObject:@"setter_after_restore"];}
    capture.weakOwners=[capture.weakOwners arrayByAddingObjectsFromArray:@[weak(recordArgumentContext),weak(recordArgumentEncoder)]];
#endif
    capture.row=[@{@"trial":@(trial),@"native_reference":@(native),@"producer_dispatches":@(produce?1u:0u),@"api_refusals":refusals,@"consumer_encoded":@(consume),@"identifiers":ids,@"foreign_identifiers":foreignIDs,@"scissor":@[@(scissor.x),@(scissor.y),@(scissor.width),@(scissor.height)],@"classes_restored_before_commit":@YES}mutableCopy];
#if KP_AIR_RENDER_RESET
    capture.row[@"AIR_reset"]=resetRow;
#endif
    return capture;
}

int main(int argc,char **argv){@autoreleasepool{@try{try{
    require(argc==4,"arguments");NSString *assets=@(argv[1]),*directory=@(argv[2]),*mode=@(argv[3]);
#if KP_TYPED_INDEXED_RENDER
    require([airIndexedModes()containsObject:mode],"typed indexed mode");
#elif KP_TYPED_RENDER_DRAW
    require([@[@"draw_gpu",@"draw_native",@"draw_reference",@"draw_no_dispatch",@"draw_no_dispatch_native",@"draw_after_reset",@"draw_after_reset_native",@"draw_then_reset",@"draw_then_reset_native"]containsObject:mode],"typed draw mode");
#elif KP_RENDER_ARGUMENT_ENCODERS
    require([@[@"arguments_gpu",@"arguments_native",@"arguments_device",@"arguments_reflection",@"arguments_arrays",@"arguments_reuse",@"arguments_no_reset",@"arguments_no_reset_native",@"arguments_contracts"]containsObject:mode],"render argument mode");
#elif KP_AIR_RENDER_RESET
    require([@[@"air_gpu",@"air_native",@"air_reference",@"air_no_reset",@"air_no_reset_native",@"air_bad_context",@"air_bad_context_native"]containsObject:mode],"AIR mode");
#else
    require([@[@"gpu",@"native",@"pipeline_only",@"pipeline_only_native",@"resources_only",@"resources_only_native",@"forced_0",@"forced_1",@"no_producer",@"no_consumer",@"release",@"contracts"]containsObject:mode],"mode");
#endif
    id<MTLDevice>device=nil;for(id<MTLDevice>d in MTLCopyAllDevices())if(KPKepler880MIdentity(d)){require(device==nil,"multiple devices");device=d;}require(device!=nil,"GTX identity");id<MTLCommandQueue>queue=[device newCommandQueue];NSError *error=nil;
#if KP_AIR_RENDER_RESET
    airInitializeReset(device,assets,directory,mode);
#endif
    id<MTLLibrary>producerLibrary=[device newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"producer.metallib"]]error:&error],markerLibrary=[device newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:@"test.metallib"]]error:&error];
    id<MTLComputePipelineState>producer=[device newComputePipelineStateWithFunction:[producerLibrary newFunctionWithName:@"generate_render_state_records"]error:&error];
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[markerLibrary newFunctionWithName:@"vs_range_marker"];pd.fragmentFunction=[markerLibrary newFunctionWithName:@"fs_range_marker"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;id<MTLRenderPipelineState>marker=[device newRenderPipelineStateWithDescriptor:pd error:&error];require(producer&&marker,"native pipeline creation");
    NSMutableArray *runs=[NSMutableArray new],*events=[NSMutableArray new];unsigned trials=[mode isEqual:@"release"]?1:8;
    for(unsigned trial=0;trial<trials;trial++){
        StateCapture *capture=nil;@autoreleasepool{capture=encodeFrame(device,queue,assets,producer,marker,trial,mode);}
        for(unsigned i=0;i<3;i++)require(capture.weakOwners[i].value==nil,"software owner retained after pool drain");
#if KP_RENDER_ARGUMENT_ENCODERS
        require(capture.weakOwners[5].value!=nil&&capture.weakOwners[6].value==nil,"owned root context lease/encoder release");
        capture.row[@"root_context_alive_before_commit"]=@YES;capture.row[@"argument_encoder_released_before_commit"]=@YES;capture.row[@"root_function_restored_before_commit"]=@YES;
#endif
        [capture.row addEntriesFromDictionary:@{@"autorelease_pool_drained_before_commit":@YES,@"scope_deallocated_before_commit":@YES,@"ICBs_deallocated_before_commit":@YES,@"sampler_0_alive_before_commit":@(capture.weakOwners[3].value!=nil),@"sampler_1_alive_before_commit":@(capture.weakOwners[4].value!=nil)}];
        [capture.commandBuffer commit];[capture.commandBuffer waitUntilCompleted];require(capture.commandBuffer.status==MTLCommandBufferStatusCompleted,"GPU completion");capture.row[@"command_status"]=@(capture.commandBuffer.status);
        for(NSString *name in capture.readbacks){id<MTLBuffer>buffer=capture.readbacks[name];NSString *file=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"trial-%u.%@.bin",trial,name]];require([[NSData dataWithBytes:buffer.contents length:buffer.length]writeToFile:file atomically:YES],"readback save");}
        [runs addObject:capture.row];[events addObjectsFromArray:capture.events];
    }
    emit(@{
#if KP_AIR_RENDER_RESET
        @"reset_pipeline":airResetReceipt,
#endif
        @"status":@"COMPLETED",@"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"device_identity":KPKepler880MIdentity(device),@"scope_events":events,@"runs":runs,@"GPU_choice_CPU_read":@NO,@"CPU_resolved_state_supplied":@([mode hasSuffix:@"native"]),@"native_Apple_ICB_ABI":@NO,@"performance_benchmark":@NO});return 0;
}catch(const std::exception &e){emit(@{@"failure":@(e.what())});return 10;}}@catch(NSException *e){emit(@{@"failure":e.reason?:@"Objective-C exception"});return 11;}}}
