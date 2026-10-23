// SPDX-License-Identifier: MIT
// Constructor/serialization test only. This client never dispatches a kernel.
#import "KeplerProgramImport.h"
#import "KeplerNativeCAS.h"
#import "KeplerGPUIdentity.h"
#import <objc/runtime.h>
#include <atomic>
#include <thread>
#include <vector>
#include <cstdio>

@interface KPNestedDevice : NSProxy
@property(nonatomic,strong) id<MTLDevice> target;
@property(nonatomic,strong) NSURL *carrier;
@property(nonatomic,strong) NSData *program, *casLibrary, *certificate;
@property(nonatomic,strong) NSDictionary *pins;
@property(nonatomic,strong) NSMutableArray *refusals;
@end
@implementation KPNestedDevice
- (NSMethodSignature*)methodSignatureForSelector:(SEL)s{return [(id)_target methodSignatureForSelector:s];}
- (void)forwardInvocation:(NSInvocation*)invocation{[invocation invokeWithTarget:_target];}
- (id<MTLLibrary>)newLibraryWithURL:(NSURL*)url error:(NSError**)error {
    NSError *nested=nil; NSDictionary *proof=nil;
    id p=KPCreatePipeline((id)self,_carrier,@"write_draw_arguments",_program,{24,576,576},&nested,&proof);
    [_refusals addObject:@{@"API":@"generic_compute",@"refused":@(!p&&nested!=nil),@"error":nested.localizedDescription?:@""}];
    nested=nil;proof=nil;
    p=KPCreateGraphicsPipeline((id)self,nil,_program,{24,0,0},_program,{24,0,0},&nested,&proof);
    [_refusals addObject:@{@"API":@"generic_graphics",@"refused":@(!p&&nested!=nil),@"error":nested.localizedDescription?:@""}];
    nested=nil;proof=nil;
    p=KPCreateCertifiedNativeCASPipeline((id)self,_casLibrary,_pins[@"cas_library_SHA256"],_certificate,_pins[@"cas_certificate_SHA256"],&nested,&proof);
    [_refusals addObject:@{@"API":@"certified_CAS",@"refused":@(!p&&nested!=nil),@"error":nested.localizedDescription?:@""}];
    nested=nil;proof=nil;
    p=KPCreateCertifiedNativeCASPipeline((id)self,nil,nil,nil,nil,&nested,&proof);
    [_refusals addObject:@{@"API":@"invalid_CAS",@"refused":@(!p&&nested!=nil),@"error":nested.localizedDescription?:@""}];
    return [_target newLibraryWithURL:url error:error];
}
@end
static NSData *load(NSString *root,NSString *name){return [NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:name]];}
static void emit(id d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=2)return 1;NSString*root=@(argv[1]);
    NSDictionary*pins=[NSJSONSerialization JSONObjectWithData:load(root,@"pins.json") options:0 error:nil];
    id<MTLDevice>d=MTLCreateSystemDefaultDevice();NSDictionary*identity=KPKepler880MIdentity(d);if(!identity)return 2;
    NSURL*url=[NSURL fileURLWithPath:[root stringByAppendingPathComponent:@"vertex/vertex_io_carrier.metallib"]];
    NSData*program=load(root,@"vertex/arguments.sass"),*vertex=load(root,@"vertex/vertex.sass"),*fragment=load(root,@"vertex/smooth.sass");
    NSData*casLibrary=load(root,[@"cas/" stringByAppendingString:pins[@"cas_library"]]);
    NSData*certificate=load(root,[@"cas/" stringByAppendingString:pins[@"cas_certificate"]]);
    NSError*error=nil;id<MTLLibrary>library=[d newLibraryWithURL:url error:&error];if(!library)return 3;
    MTLRenderPipelineDescriptor*desc=[MTLRenderPipelineDescriptor new];
    desc.vertexFunction=[library newFunctionWithName:@"vs_io_smooth"];desc.fragmentFunction=[library newFunctionWithName:@"fs_io_smooth"];
    MTLVertexDescriptor*input=[MTLVertexDescriptor vertexDescriptor];
    for(unsigned i=0;i<3;i++){input.attributes[i].format=MTLVertexFormatFloat4;input.attributes[i].offset=i==1?16:0;input.attributes[i].bufferIndex=i==2?1:0;}
    input.layouts[0].stride=32;input.layouts[0].stepFunction=MTLVertexStepFunctionPerVertex;
    input.layouts[1].stride=16;input.layouts[1].stepFunction=MTLVertexStepFunctionPerInstance;desc.vertexDescriptor=input;
    desc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
    Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));if(!method)return 3;
    IMP before=method_getImplementation(method);
    KPNestedDevice*proxy=[KPNestedDevice alloc];proxy.target=d;proxy.carrier=url;proxy.program=program;
    proxy.casLibrary=casLibrary;proxy.certificate=certificate;proxy.pins=pins;proxy.refusals=[NSMutableArray new];
    NSDictionary*nestedProof=nil;
    id outer=KPCreatePipeline((id)proxy,url,@"write_draw_arguments",program,{24,576,576},&error,&nestedProof);
    bool nestedOK=outer&&proxy.refusals.count==4;
    for(NSDictionary*r in proxy.refusals)nestedOK&=[r[@"refused"]boolValue]&&[r[@"error"] containsString:@"Nested"];
    std::atomic<unsigned>ready{0};std::atomic<bool>go{false};
    NSMutableArray*results=[NSMutableArray new];std::vector<std::thread>threads;
    for(unsigned kind=0;kind<3;kind++)threads.emplace_back([&,kind]{@autoreleasepool{
        ready++;while(!go.load())std::this_thread::yield();
        NSError*e=nil;NSDictionary*proof=nil;id pipeline=nil;
        if(kind==0)pipeline=KPCreatePipeline(d,url,@"write_draw_arguments",program,{24,576,576},&e,&proof);
        if(kind==1)pipeline=KPCreateGraphicsPipeline(d,desc,vertex,{24,0,0},fragment,{24,0,0},&e,&proof);
        if(kind==2)pipeline=KPCreateCertifiedNativeCASPipeline(d,casLibrary,pins[@"cas_library_SHA256"],certificate,pins[@"cas_certificate_SHA256"],&e,&proof);
        @synchronized(results){[results addObject:@{@"kind":@(kind),@"pipeline_created":@(pipeline!=nil),@"expected_cached_refusal":@(kind==0),@"error":e.description?:@"",@"proof":proof?:@{}}];}
    }});
    while(ready.load()!=3)std::this_thread::yield();go=true;for(auto&t:threads)t.join();
    bool ok=nestedOK&&[nestedProof[@"constructor_restored"]boolValue]&&method_getImplementation(method)==before;
    for(NSDictionary*r in results){
        NSDictionary*p=r[@"proof"];bool restored=[p[@"constructor_restored"]boolValue];
        if([r[@"kind"]unsignedIntValue]==0)ok&=![r[@"pipeline_created"]boolValue]&&restored&&
            ![p[@"contract_verified"]boolValue]&&[p[@"target_imports"]unsignedIntValue]==0&&
            [r[@"error"] containsString:@"Decoded program contract did not match"];
        else ok&=[r[@"pipeline_created"]boolValue]&&restored;
    }
    emit(@{@"device":d.name,@"registry_id":@(d.registryID),@"device_identity":identity,@"nested_imports":proxy.refusals,
        @"outer_pipeline_created":@(outer!=nil),@"outer_import":nestedProof?:@{},@"outer_error":error.description?:@"",@"concurrent_imports":results,
        @"constructor_restored_after_join":@(method_getImplementation(method)==before),@"status":ok?@"PASS":@"FAIL",
        @"GPU_dispatches":@0,@"scope":@"Import contract and cross-API host serialization; no execution or performance claim"});
    return ok?0:10;
}}
