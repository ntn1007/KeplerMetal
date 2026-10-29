// Narrow experimental bootstrap for one pinned executable and one shader snapshot.
// Not a general Metal compatibility layer; no native shared class is modified.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import <CommonCrypto/CommonDigest.h>
#import <dlfcn.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#ifndef KM_APPROVED_APP_SHA256
#error Expected the hash of the signed experimental client
#endif
static NSString* const appHash=@KM_APPROVED_APP_SHA256;
static NSString* const carrierHash=@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7";
static NSString* const transformHash=@"c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43";
static NSString* const manifestHash=@"055fbb885cba637a2af12d9f4636b76ec6b2e9d437ce1c2e678395dc13065973";
static KPCPUICBScope *scope;static id<MTLDevice> scopedDevice;static id<MTLCommandQueue> scopedQueue;static BOOL usedQueue;
static NSString* hash(NSData*d){if(!d||d.length>64*1024*1024)return nil;unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString string];for(unsigned i=0;i<sizeof(digest);i++)[s appendFormat:@"%02x",digest[i]];return s;}
static void emitEvents(void){@autoreleasepool{const char*p=getenv("KM_EVENT_PATH");if(!p||!scope)return;NSError*e=nil;NSData*d=[NSJSONSerialization dataWithJSONObject:scope.events options:NSJSONWritingPrettyPrinted error:&e];if(d)[d writeToFile:@(p) options:NSDataWritingAtomic error:&e];}}
static id<MTLCommandQueue> scopedNewQueue(id self,SEL cmd) NS_RETURNS_RETAINED;
static id<MTLCommandQueue> scopedNewQueue(id self,SEL cmd){if(self!=scopedDevice){Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),cmd);typedef id<MTLCommandQueue>(*Fn)(id,SEL) __attribute__((ns_returns_retained));return ((Fn)method_getImplementation(m))(self,cmd);}if(usedQueue)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Only one queue is qualified"];usedQueue=YES;fprintf(stderr,"KM_BOOT queue matched\n");return scopedQueue;}
static char functionTag;
static id<MTLFunction> approvedFunction(id self,SEL cmd,NSString*name) NS_RETURNS_RETAINED;
static id<MTLFunction> approvedFunction(id self,SEL cmd,NSString*name){
 Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),cmd);typedef id<MTLFunction>(*Fn)(id,SEL,NSString*) __attribute__((ns_returns_retained));id<MTLFunction>f=((Fn)method_getImplementation(m))(self,cmd,name);
 if(f&&[@[@"vs_io_smooth",@"fs_io_smooth",@"vs_io_flat",@"fs_io_flat"] containsObject:name])objc_setAssociatedObject(f,&functionTag,@YES,OBJC_ASSOCIATION_RETAIN_NONATOMIC);return f;
}
static id<MTLLibrary> scopedLibrary(id self,SEL cmd,NSString*path,NSError**error) NS_RETURNS_RETAINED;
static id<MTLLibrary> scopedLibrary(id self,SEL cmd,NSString*path,NSError**error){
 Class base=class_getSuperclass(object_getClass(self));Method fileMethod=class_getInstanceMethod(base,cmd);typedef id<MTLLibrary>(*FileFn)(id,SEL,NSString*,NSError**) __attribute__((ns_returns_retained));
 NSData*snapshot=[NSData dataWithContentsOfFile:path];if(self!=scopedDevice||![hash(snapshot)isEqual:transformHash]){fprintf(stderr,"KM_BOOT library unapproved\n");return ((FileFn)method_getImplementation(fileMethod))(self,cmd,path,error);}
 dispatch_data_t bytes=dispatch_data_create(snapshot.bytes,snapshot.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)snapshot.length;});SEL dataSelector=@selector(newLibraryWithData:error:);Method dataMethod=class_getInstanceMethod(base,dataSelector);typedef id<MTLLibrary>(*DataFn)(id,SEL,dispatch_data_t,NSError**) __attribute__((ns_returns_retained));
 id<MTLLibrary>lib=((DataFn)method_getImplementation(dataMethod))(self,dataSelector,bytes,error);if(!lib)return nil;
 Class original=object_getClass(lib);Method functionMethod=class_getInstanceMethod(original,@selector(newFunctionWithName:));NSString*name=[@"KMApprovedLibrary_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];Class dynamic=objc_allocateClassPair(original,name.UTF8String,0);
 if(!dynamic||!functionMethod||!class_addMethod(dynamic,@selector(newFunctionWithName:),(IMP)approvedFunction,method_getTypeEncoding(functionMethod))){if(dynamic)objc_disposeClassPair(dynamic);fprintf(stderr,"KM_BOOT library adaptation refused\n");return nil;}objc_registerClassPair(dynamic);if(class_getInstanceSize(dynamic)!=class_getInstanceSize(original))return nil;object_setClass(lib,dynamic);fprintf(stderr,"KM_BOOT library snapshot approved\n");return lib;
}
static BOOL exactVertexDescriptor(MTLVertexDescriptor*v){if(!v)return NO;for(NSUInteger i=0;i<31;i++){MTLVertexAttributeDescriptor*a=v.attributes[i];MTLVertexBufferLayoutDescriptor*l=v.layouts[i];MTLVertexFormat format=i<3?MTLVertexFormatFloat4:MTLVertexFormatInvalid;NSUInteger offset=i==1?16:0,buffer=i==2?1:0,stride=i==0?32:i==1?16:0;MTLVertexStepFunction step=i==1?MTLVertexStepFunctionPerInstance:MTLVertexStepFunctionPerVertex;if(a.format!=format||a.offset!=offset||a.bufferIndex!=buffer||l.stride!=stride||l.stepFunction!=step||l.stepRate!=1)return NO;}return YES;}
static BOOL otherColorAttachmentsEmpty(MTLRenderPipelineDescriptor*p){for(NSUInteger i=1;i<8;i++)if(p.colorAttachments[i].pixelFormat!=MTLPixelFormatInvalid)return NO;return YES;}
static id<MTLRenderPipelineState> scopedNewPipeline(id self,SEL cmd,MTLRenderPipelineDescriptor*p,NSError**error) NS_RETURNS_RETAINED;
static id<MTLRenderPipelineState> scopedNewPipeline(id self,SEL cmd,MTLRenderPipelineDescriptor*p,NSError**error){
 NSString*name=nil;if([p.vertexFunction.name isEqual:@"vs_io_smooth"]&&[p.fragmentFunction.name isEqual:@"fs_io_smooth"])name=@"smooth";else if([p.vertexFunction.name isEqual:@"vs_io_flat"]&&[p.fragmentFunction.name isEqual:@"fs_io_flat"])name=@"flat";
 BOOL match=self==scopedDevice&&name&&[objc_getAssociatedObject(p.vertexFunction,&functionTag)boolValue]&&[objc_getAssociatedObject(p.fragmentFunction,&functionTag)boolValue]&&p.rasterizationEnabled&&p.supportIndirectCommandBuffers&&exactVertexDescriptor(p.vertexDescriptor)&&otherColorAttachmentsEmpty(p)&&p.colorAttachments[0].pixelFormat==MTLPixelFormatRGBA32Float&&p.colorAttachments[0].writeMask==MTLColorWriteMaskAll&&!p.colorAttachments[0].blendingEnabled&&!p.alphaToCoverageEnabled&&!p.alphaToOneEnabled&&p.sampleCount==1&&p.depthAttachmentPixelFormat==MTLPixelFormatInvalid&&p.stencilAttachmentPixelFormat==MTLPixelFormatInvalid;
 if(match){fprintf(stderr,"KM_BOOT registered pipeline %s matched\n",name.UTF8String);return [scope renderPipelineForName:name];}fprintf(stderr,"KM_BOOT descriptor not qualified; forwarding native factory\n");Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),cmd);typedef id<MTLRenderPipelineState>(*Fn)(id,SEL,MTLRenderPipelineDescriptor*,NSError**) __attribute__((ns_returns_retained));return ((Fn)method_getImplementation(m))(self,cmd,p,error);
}
static bool add(Class c,Class parent,SEL selector,IMP imp){Method m=class_getInstanceMethod(parent,selector);return m&&class_addMethod(c,selector,imp,method_getTypeEncoding(m));}
static id<MTLDevice> replacement(void) NS_RETURNS_RETAINED;
static id<MTLDevice> replacement(void){fprintf(stderr,"KM_BOOT enter\n");@autoreleasepool{
 // Recursion is per-thread; simultaneous independent callers wait for the
 // initial scope, then receive that same device. Failure stays fail-closed.
 static std::mutex initializationMutex;static bool failed=false;static thread_local bool entered=false;
 if(entered){fprintf(stderr,"KM_BOOT recursive device discovery refused\n");return nil;}
 struct EntryGuard { bool &flag; explicit EntryGuard(bool &value):flag(value){flag=true;} ~EntryGuard(){flag=false;} } guard(entered);
 std::lock_guard<std::mutex> lock(initializationMutex);
 if(scopedDevice){fprintf(stderr,"KM_BOOT device reused\n");return scopedDevice;}
 if(failed)return nil;
 failed=true;
 uint32_t length=0;_NSGetExecutablePath(nullptr,&length);if(length==0||length>8192)return nil;char*name=(char*)calloc(length,1);if(!name)return nil;int got=_NSGetExecutablePath(name,&length);NSData*binary=got==0?[NSData dataWithContentsOfFile:@(name)]:nil;free(name);const char*path=getenv("KM_CARRIER_PATH");NSData*data=path?[NSData dataWithContentsOfFile:@(path)]:nil;
 if(![hash(binary)isEqual:appHash]||![hash(data)isEqual:carrierHash]){fprintf(stderr,"KM_BOOT identity refused\n");return nil;}
 NSArray<id<MTLDevice>>*devices=MTLCopyAllDevices();if(devices.count!=1||!KPKepler880MIdentity(devices[0])){fprintf(stderr,"KM_BOOT device count or identity refused\n");return nil;}id<MTLDevice>d=devices[0];fprintf(stderr,"KM_BOOT got single qualified device\n");
 NSError*error=nil;id<MTLCommandQueue>q=[d newCommandQueue];KPCPUICBScope*s=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:data expectedSHA256:carrierHash error:&error];if(!s){fprintf(stderr,"KM_BOOT scope refused %s\n",error.description.UTF8String?:"");return nil;}
 const char*shaderPath=getenv("KM_TRANSFORM_PATH"),*manifestPath=getenv("KM_MANIFEST_PATH");NSData*shader=shaderPath?[NSData dataWithContentsOfFile:@(shaderPath)]:nil,*manifest=manifestPath?[NSData dataWithContentsOfFile:@(manifestPath)]:nil;
 if(![hash(shader)isEqual:transformHash]||![hash(manifest)isEqual:manifestHash]||![s registerRenderVertexLibraryData:shader expectedSHA256:transformHash manifestData:manifest expectedManifestSHA256:manifestHash error:&error]){[s restore];fprintf(stderr,"KM_BOOT transform identity refused %s\n",error.description.UTF8String?:"");return nil;}
 Class dyn=object_getClass(d),base=class_getSuperclass(dyn);bool ok=add(dyn,base,@selector(newCommandQueue),(IMP)scopedNewQueue)&&add(dyn,base,@selector(newLibraryWithFile:error:),(IMP)scopedLibrary)&&add(dyn,base,@selector(newRenderPipelineStateWithDescriptor:error:),(IMP)scopedNewPipeline);
 if(!ok||![s enableAutomaticRenderEncoderFactoriesWithError:&error]){[s restore];fprintf(stderr,"KM_BOOT setup refused %s\n",error.description.UTF8String?:"");return nil;}
 scope=s;scopedDevice=d;scopedQueue=q;atexit(emitEvents);fprintf(stderr,"KM_BOOT enabled\n");return d;
}}
__attribute__((used)) static struct {const void*replacement;const void*replacee;} interpose[] __attribute__((section("__DATA,__interpose")))={{(const void*)replacement,(const void*)MTLCreateSystemDefaultDevice}};
