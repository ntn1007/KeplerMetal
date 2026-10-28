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
#include <map>
#ifndef KM_APPROVED_APP_SHA256
#error Expected the hash of the signed experimental client
#endif
static NSString* const appHash=@KM_APPROVED_APP_SHA256;
static NSString* const carrierHash=@"0985a3057cd487352d801abcd180bf05a681b8dc7357ee5400db044098c32c4c";
static NSString* const manifestHash=@"c7dcdc81adba7f7ba6cf8175ecc179a086a9bd150b44d71ca1a39ad18846ef9a";
static KPCPUICBScope *scope;static id<MTLDevice> scopedDevice;static id<MTLCommandQueue> scopedQueue;static BOOL usedQueue;
static NSString* hash(NSData*d){if(!d||d.length>64*1024*1024)return nil;unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString string];for(unsigned i=0;i<sizeof(digest);i++)[s appendFormat:@"%02x",digest[i]];return s;}
static void emitEvents(void){@autoreleasepool{const char*p=getenv("KM_EVENT_PATH");if(!p||!scope)return;NSError*e=nil;NSData*d=[NSJSONSerialization dataWithJSONObject:scope.events options:NSJSONWritingPrettyPrinted error:&e];if(d)[d writeToFile:@(p) options:NSDataWritingAtomic error:&e];}}
static id<MTLCommandQueue> scopedNewQueue(id self,SEL cmd) NS_RETURNS_RETAINED;
static id<MTLCommandQueue> scopedNewQueue(id self,SEL cmd){if(self!=scopedDevice){Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),cmd);typedef id<MTLCommandQueue>(*Fn)(id,SEL) __attribute__((ns_returns_retained));return ((Fn)method_getImplementation(m))(self,cmd);}if(usedQueue)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Only one queue is qualified"];usedQueue=YES;fprintf(stderr,"KM_BOOT queue matched\n");return scopedQueue;}
static char functionTag;
static id<MTLFunction> approvedFunction(id self,SEL cmd,NSString*name) NS_RETURNS_RETAINED;
static id<MTLFunction> approvedFunction(id self,SEL cmd,NSString*name){
 Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),cmd);typedef id<MTLFunction>(*Fn)(id,SEL,NSString*) __attribute__((ns_returns_retained));id<MTLFunction>f=((Fn)method_getImplementation(m))(self,cmd,name);
 if(f&&([name isEqual:@"partial_builtin_barrier"]||[name isEqual:@"partial_buffer_stencil"]))objc_setAssociatedObject(f,&functionTag,@YES,OBJC_ASSOCIATION_RETAIN_NONATOMIC);return f;
}
static id<MTLLibrary> scopedLibrary(id self,SEL cmd,NSString*path,NSError**error) NS_RETURNS_RETAINED;
static id<MTLLibrary> scopedLibrary(id self,SEL cmd,NSString*path,NSError**error){
 Class base=class_getSuperclass(object_getClass(self));Method fileMethod=class_getInstanceMethod(base,cmd);typedef id<MTLLibrary>(*FileFn)(id,SEL,NSString*,NSError**) __attribute__((ns_returns_retained));
 NSData*snapshot=[NSData dataWithContentsOfFile:path];if(self!=scopedDevice||![hash(snapshot)isEqual:carrierHash]){fprintf(stderr,"KM_BOOT library unapproved\n");return ((FileFn)method_getImplementation(fileMethod))(self,cmd,path,error);}
 dispatch_data_t bytes=dispatch_data_create(snapshot.bytes,snapshot.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)snapshot.length;});SEL dataSelector=@selector(newLibraryWithData:error:);Method dataMethod=class_getInstanceMethod(base,dataSelector);typedef id<MTLLibrary>(*DataFn)(id,SEL,dispatch_data_t,NSError**) __attribute__((ns_returns_retained));
 id<MTLLibrary>lib=((DataFn)method_getImplementation(dataMethod))(self,dataSelector,bytes,error);if(!lib)return nil;
 Class original=object_getClass(lib);Method functionMethod=class_getInstanceMethod(original,@selector(newFunctionWithName:));NSString*name=[@"KMApprovedLibrary_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];Class dynamic=objc_allocateClassPair(original,name.UTF8String,0);
 if(!dynamic||!functionMethod||!class_addMethod(dynamic,@selector(newFunctionWithName:),(IMP)approvedFunction,method_getTypeEncoding(functionMethod))){if(dynamic)objc_disposeClassPair(dynamic);fprintf(stderr,"KM_BOOT library adaptation refused\n");return nil;}objc_registerClassPair(dynamic);if(class_getInstanceSize(dynamic)!=class_getInstanceSize(original))return nil;object_setClass(lib,dynamic);fprintf(stderr,"KM_BOOT library snapshot approved\n");return lib;
}
static id<MTLComputePipelineState> scopedNewPipeline(id self,SEL cmd,id<MTLFunction>function,NSError**error) NS_RETURNS_RETAINED;
static id<MTLComputePipelineState> scopedNewPipeline(id self,SEL cmd,id<MTLFunction>function,NSError**error){
 if(self==scopedDevice&&[objc_getAssociatedObject(function,&functionTag) boolValue]){id<MTLComputePipelineState>pipeline=[scope pipelineForFunction:function.name];if(pipeline){fprintf(stderr,"KM_BOOT compute pipeline matched %s\n",function.name.UTF8String);return pipeline;}}
 Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),cmd);typedef id<MTLComputePipelineState>(*Fn)(id,SEL,id<MTLFunction>,NSError**) __attribute__((ns_returns_retained));return ((Fn)method_getImplementation(m))(self,cmd,function,error);
}
// Encoders are adapted per instance; ordinary blits retain native behavior.
@interface KMAutoBlitLink : NSObject
@property(nonatomic) Class originalClass;
@property(nonatomic,weak) id<MTLCommandBuffer> commandBuffer;
@property(nonatomic) BOOL adapted;
@end
@implementation KMAutoBlitLink
@end
static char autoBlitKey;
static std::mutex autoBlitMutex;
static std::map<uintptr_t,Class> autoBlitClasses,autoBoundClasses;
static void scopedCopy(id self,SEL selector,id<MTLIndirectCommandBuffer>source,NSRange range,id<MTLIndirectCommandBuffer>destination,NSUInteger index){
 KMAutoBlitLink*link=objc_getAssociatedObject(self,&autoBlitKey);if(!link||!scope)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Blit scope absent"];
 Class project=NSClassFromString(@"KPComputeICB");BOOL a=project&&[source isKindOfClass:project],b=project&&[destination isKindOfClass:project];
 if(!a&&!b){Method m=class_getInstanceMethod(link.originalClass,selector);if(!m){[self doesNotRecognizeSelector:selector];return;}typedef void(*Fn)(id,SEL,id,NSRange,id,NSUInteger);((Fn)method_getImplementation(m))(self,selector,source,range,destination,index);return;}
 if(!a||!b||link.adapted)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Mixed ICB ownership or second copy not qualified"];
 if(!link.commandBuffer||link.commandBuffer.commandQueue!=scopedQueue||link.commandBuffer.status!=MTLCommandBufferStatusNotEnqueued||!link.commandBuffer.retainedReferences)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Copy needs a retained uncommitted buffer on the scope queue"];
 NSError*error=nil;NSUInteger before=0;for(NSDictionary*e in scope.events)if([e[@"operation"]isEqual:@"materialize_CPU_command"])before++;
 if(![scope prepareExperimentalPartialGPUCopyFrom:source sourceRange:range destination:destination destinationIndex:index error:&error]){NSUInteger after=0;for(NSDictionary*e in scope.events)if([e[@"operation"]isEqual:@"materialize_CPU_command"])after++;fprintf(stderr,"KM_BOOT preflight refused materializations %lu %lu\n",(unsigned long)before,(unsigned long)after);[NSException raise:@"KeplerStandaloneUnsupported" format:@"Copy preparation refused: %@",error.localizedDescription?:@"unknown"];}
 if(![scope adaptBlitEncoder:self error:&error])[NSException raise:@"KeplerStandaloneUnsupported" format:@"Blit adaptation refused: %@",error.localizedDescription?:@"unknown"];link.adapted=YES;
 Class parent=object_getClass(self),bound=nil;{std::lock_guard<std::mutex>lock(autoBlitMutex);auto it=autoBoundClasses.find((uintptr_t)(__bridge const void*)parent);if(it!=autoBoundClasses.end())bound=it->second;else{NSString*n=[@"KMAutoBoundBlit_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];bound=objc_allocateClassPair(parent,n.UTF8String,0);Method m=class_getInstanceMethod(parent,selector);if(!bound||!m||!class_addMethod(bound,selector,(IMP)scopedCopy,method_getTypeEncoding(m))){if(bound)objc_disposeClassPair(bound);bound=nil;}else{objc_registerClassPair(bound);autoBoundClasses[(uintptr_t)(__bridge const void*)parent]=bound;}}}
 if(!bound||class_getInstanceSize(bound)!=class_getInstanceSize(parent))[NSException raise:@"KeplerStandaloneUnsupported" format:@"Bound blit layout differs"];object_setClass(self,bound);
 typedef void(*Fn)(id,SEL,id,NSRange,id,NSUInteger);((Fn)class_getMethodImplementation(parent,selector))(self,selector,source,range,destination,index);fprintf(stderr,"KM_BOOT object GPU copy encoded\n");
}
static void scopedEnd(id self,SEL selector){
 KMAutoBlitLink*link=objc_getAssociatedObject(self,&autoBlitKey);if(!link)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Blit end scope absent"];Method m=class_getInstanceMethod(link.originalClass,selector);if(!m)[NSException raise:@"KeplerStandaloneUnsupported" format:@"Native blit end missing"];
 NSString*reason=nil;@try{typedef void(*Fn)(id,SEL);((Fn)method_getImplementation(m))(self,selector);}@catch(NSException*x){reason=x.reason?:@"Native end failed";}
 if(link.adapted){NSError*error=nil;if(![scope detachEndedExperimentalBlitEncoder:self error:&error])reason=error.localizedDescription?:@"Ended blit detach failed";}
 object_setClass(self,link.originalClass);objc_setAssociatedObject(self,&autoBlitKey,nil,OBJC_ASSOCIATION_ASSIGN);if(reason)[NSException raise:@"KeplerStandaloneUnsupported" format:@"%@",reason];
}
static id<MTLBlitCommandEncoder> scopedBlit(id self,SEL selector){
 Class parent=class_getSuperclass(object_getClass(self));typedef id<MTLBlitCommandEncoder>(*Fn)(id,SEL);id<MTLBlitCommandEncoder>encoder=((Fn)class_getMethodImplementation(parent,selector))(self,selector);if(!encoder)return nil;
 Class original=object_getClass(encoder);Ivar v=class_getInstanceVariable(original,"_commandBuffer");if(![NSStringFromClass(original)hasPrefix:@"NVMTL"]||!v||ivar_getOffset(v)!=32||object_getIvar(encoder,v)!=self||objc_getAssociatedObject(encoder,&autoBlitKey)){[encoder endEncoding];[NSException raise:@"KeplerStandaloneUnsupported" format:@"Native blit profile differs"];}
 Class dynamic=nil;{std::lock_guard<std::mutex>lock(autoBlitMutex);auto it=autoBlitClasses.find((uintptr_t)(__bridge const void*)original);if(it!=autoBlitClasses.end())dynamic=it->second;else{NSString*n=[@"KMAutoBlit_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];dynamic=objc_allocateClassPair(original,n.UTF8String,0);SEL copy=@selector(copyIndirectCommandBuffer:sourceRange:destination:destinationIndex:);Method cm=class_getInstanceMethod(original,copy);const char*types=cm?method_getTypeEncoding(cm):protocol_getMethodDescription(@protocol(MTLBlitCommandEncoder),copy,YES,YES).types;Method end=class_getInstanceMethod(original,@selector(endEncoding));if(!dynamic||!types||!end||!class_addMethod(dynamic,copy,(IMP)scopedCopy,types)||!class_addMethod(dynamic,@selector(endEncoding),(IMP)scopedEnd,method_getTypeEncoding(end))){if(dynamic)objc_disposeClassPair(dynamic);dynamic=nil;}else{objc_registerClassPair(dynamic);autoBlitClasses[(uintptr_t)(__bridge const void*)original]=dynamic;}}}
 if(!dynamic||class_getInstanceSize(dynamic)!=class_getInstanceSize(original)){[encoder endEncoding];[NSException raise:@"KeplerStandaloneUnsupported" format:@"Automatic blit class differs"];}
 KMAutoBlitLink*link=[KMAutoBlitLink new];link.originalClass=original;link.commandBuffer=self;objc_setAssociatedObject(encoder,&autoBlitKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(encoder,dynamic);return encoder;
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
 uint32_t length=0;_NSGetExecutablePath(nullptr,&length);if(length==0||length>8192)return nil;char*name=(char*)calloc(length,1);if(!name)return nil;int got=_NSGetExecutablePath(name,&length);NSData*binary=got==0?[NSData dataWithContentsOfFile:@(name)]:nil;free(name);const char*path=getenv("KM_CARRIER_PATH");NSData*data=path?[NSData dataWithContentsOfFile:@(path)]:nil;const char*mp=getenv("KM_MANIFEST_PATH");NSData*manifest=mp?[NSData dataWithContentsOfFile:@(mp)]:nil;
 if(![hash(binary)isEqual:appHash]||![hash(data)isEqual:carrierHash]||![hash(manifest)isEqual:manifestHash]){fprintf(stderr,"KM_BOOT identity refused\n");return nil;}
 NSArray<id<MTLDevice>>*devices=MTLCopyAllDevices();if(devices.count!=1||!KPKepler880MIdentity(devices[0])){fprintf(stderr,"KM_BOOT device count or identity refused\n");return nil;}id<MTLDevice>d=devices[0];fprintf(stderr,"KM_BOOT got single qualified device\n");
 NSError*error=nil;id<MTLCommandQueue>q=[d newCommandQueue];KPCPUICBScope*s=[KPCPUICBScope installOnDevice:d queue:q libraryData:data expectedSHA256:carrierHash manifestData:manifest expectedManifestSHA256:manifestHash error:&error];if(!s){fprintf(stderr,"KM_BOOT scope refused %s\n",error.description.UTF8String?:"");return nil;}
 Class dyn=object_getClass(d),base=class_getSuperclass(dyn);bool ok=add(dyn,base,@selector(newCommandQueue),(IMP)scopedNewQueue)&&add(dyn,base,@selector(newLibraryWithFile:error:),(IMP)scopedLibrary)&&add(dyn,base,@selector(newComputePipelineStateWithFunction:error:),(IMP)scopedNewPipeline);
 if(!ok||![s enableExperimentalPartialGridWithError:&error]||![s enableExperimentalPartialGPUCopyWithError:&error]||![s enableAutomaticComputeEncoderFactoriesWithError:&error]){[s restore];fprintf(stderr,"KM_BOOT setup refused %s\n",error.description.UTF8String?:"");return nil;}
 scope=s;scopedDevice=d;scopedQueue=q;
 id<MTLCommandBuffer>sample=[q commandBuffer];Class automatic=object_getClass(sample),native=class_getSuperclass(automatic);
 if(!sample||![NSStringFromClass(automatic)hasPrefix:@"KPAutomaticCommandBuffer_"]||!add(automatic,native,@selector(blitCommandEncoder),(IMP)scopedBlit)){[s restore];scope=nil;scopedDevice=nil;scopedQueue=nil;fprintf(stderr,"KM_BOOT blit factory refused\n");return nil;}
 atexit(emitEvents);fprintf(stderr,"KM_BOOT enabled\n");return d;
}}
__attribute__((used)) static struct {const void*replacement;const void*replacee;} interpose[] __attribute__((section("__DATA,__interpose")))={{(const void*)replacement,(const void*)MTLCreateSystemDefaultDevice}};
