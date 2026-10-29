// SPDX-License-Identifier: MIT
// Process-local experiment for one signed Apple Release sample executable.
// No family/capability answers or system classes are changed.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <MetalKit/MetalKit.h>
#import <QuartzCore/QuartzCore.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import <CommonCrypto/CommonDigest.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#include <mutex>
#include <cstdlib>
#ifndef KM_APPROVED_APP_SHA256
#error Signed Apple executable hash is required
#endif
#ifndef KM_DEFAULT_LIBRARY_SHA256
#error Release bundle default library hash is required
#endif
static NSString *const appHash=@KM_APPROVED_APP_SHA256;
static NSString *const defaultHash=@KM_DEFAULT_LIBRARY_SHA256;
static NSString *const shaderHash=@"04d8d8ae6a4485d3be0262e971c365cfff1d5bb04f88f24cdbdfa0ffdee6afa2";
static NSString *const carrierHash=@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7";
static NSString *const manifestHash=@"b5798a3c5129c4cec893c487cbc9211a439deaedd14a1c3a4857114a949e0ace";
static KPCPUICBScope *scope; static id<MTLDevice> device; static id<MTLCommandQueue> queue; static NSData *certifiedDefault;
static BOOL usedQueue; static char functionTag; static id<MTLBuffer> capture; static id<MTLCommandBuffer> capturedCB;
static NSString *hash(NSData *d){if(!d||d.length>64*1024*1024)return nil;unsigned char x[32];CC_SHA256(d.bytes,(CC_LONG)d.length,x);NSMutableString *s=[NSMutableString new];for(unsigned char v:x)[s appendFormat:@"%02x",v];return s;}
static NSData *asset(const char *key){const char *v=getenv(key);return v?[NSData dataWithContentsOfFile:@(v)]:nil;}
static void refuse(NSString *s){@throw [NSException exceptionWithName:@"KeplerAppleOriginalRefused" reason:s userInfo:nil];}
static id<MTLCommandQueue> newQueue(id self,SEL cmd) NS_RETURNS_RETAINED;
static id<MTLCommandQueue> newQueue(id self,SEL cmd){if(self!=device||usedQueue)refuse(@"Unexpected device or second queue");usedQueue=YES;return queue;}
static id<MTLFunction> function(id self,SEL cmd,NSString *name) NS_RETURNS_RETAINED;
static id<MTLFunction> function(id self,SEL cmd,NSString *name){Class base=class_getSuperclass(object_getClass(self));typedef id<MTLFunction>(*F)(id,SEL,NSString*) __attribute__((ns_returns_retained));id<MTLFunction> f=((F)class_getMethodImplementation(base,cmd))(self,cmd,name);if(f&&[@[@"vertexShader",@"fragmentShader"] containsObject:name])objc_setAssociatedObject(f,&functionTag,@YES,OBJC_ASSOCIATION_RETAIN_NONATOMIC);return f;}
static id<MTLLibrary> defaultLibrary(id self,SEL cmd) NS_RETURNS_RETAINED;
static id<MTLLibrary> defaultLibrary(id self,SEL cmd){
 NSURL *url=[[NSBundle mainBundle] URLForResource:@"default" withExtension:@"metallib"];
 NSData *snapshot=url.isFileURL?[NSData dataWithContentsOfURL:url]:nil;
 if(self!=device||![hash(snapshot) isEqual:defaultHash]||![snapshot isEqual:certifiedDefault])refuse(@"Release bundle library identity differs");
 Class base=class_getSuperclass(object_getClass(self));typedef id<MTLLibrary>(*F)(id,SEL) __attribute__((ns_returns_retained));id<MTLLibrary> lib=((F)class_getMethodImplementation(base,cmd))(self,cmd);if(!lib)refuse(@"Native default library unavailable");
 Class original=object_getClass(lib);Method method=class_getInstanceMethod(original,@selector(newFunctionWithName:));NSString *n=[@"KMAppleReleaseLibrary_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];Class dyn=objc_allocateClassPair(original,n.UTF8String,0);
 if(!dyn||!method||!class_addMethod(dyn,@selector(newFunctionWithName:),(IMP)function,method_getTypeEncoding(method)))refuse(@"Cannot tag native library functions");objc_registerClassPair(dyn);if(class_getInstanceSize(dyn)!=class_getInstanceSize(original))refuse(@"Library object layout differs");object_setClass(lib,dyn);fprintf(stderr,"KM_APP original default library loaded\n");return lib;
}
static BOOL emptyVertex(MTLVertexDescriptor *v){if(!v)return YES;for(NSUInteger i=0;i<31;i++){MTLVertexAttributeDescriptor *a=v.attributes[i];MTLVertexBufferLayoutDescriptor *l=v.layouts[i];if(a.format!=MTLVertexFormatInvalid||a.offset||a.bufferIndex||l.stride||l.stepFunction!=MTLVertexStepFunctionPerVertex||l.stepRate!=1)return NO;}return YES;}
static id<MTLRenderPipelineState> pipeline(id self,SEL cmd,MTLRenderPipelineDescriptor *p,NSError **error) NS_RETURNS_RETAINED;
static id<MTLRenderPipelineState> pipeline(id self,SEL cmd,MTLRenderPipelineDescriptor *p,NSError **error){
 BOOL other=YES;for(NSUInteger i=1;i<8;i++)other=other&&p.colorAttachments[i].pixelFormat==MTLPixelFormatInvalid;
 BOOL ok=self==device&&[objc_getAssociatedObject(p.vertexFunction,&functionTag) boolValue]&&[objc_getAssociatedObject(p.fragmentFunction,&functionTag) boolValue]&&[p.vertexFunction.name isEqual:@"vertexShader"]&&[p.fragmentFunction.name isEqual:@"fragmentShader"]&&emptyVertex(p.vertexDescriptor)&&p.rasterizationEnabled&&p.supportIndirectCommandBuffers&&other&&p.colorAttachments[0].pixelFormat==MTLPixelFormatBGRA8Unorm&&p.colorAttachments[0].writeMask==MTLColorWriteMaskAll&&!p.colorAttachments[0].blendingEnabled&&!p.alphaToCoverageEnabled&&!p.alphaToOneEnabled&&p.sampleCount==1&&p.depthAttachmentPixelFormat==MTLPixelFormatDepth32Float&&p.stencilAttachmentPixelFormat==MTLPixelFormatInvalid;
 if(!ok)refuse(@"Apple pipeline descriptor outside bounded profile");id<MTLRenderPipelineState> result=[scope renderPipelineForName:@"apple_explicit_view"];if(!result)refuse(@"Registered pipeline unavailable");fprintf(stderr,"KM_APP selected pipeline created from same default library bytes\n");return result;
}
static MTKView *findView(NSView *view){if([view isKindOfClass:MTKView.class])return (MTKView*)view;for(NSView *v in view.subviews){MTKView *found=findView(v);if(found)return found;}return nil;}
// Only the lab-created automatic command-buffer class is extended, in this
// one process. Capture is encoded before the application's native present.
static void present(id self,SEL cmd,id<MTLDrawable> drawable){
 if(capture)refuse(@"Only one captured drawable is qualified");
 if(![drawable conformsToProtocol:@protocol(CAMetalDrawable)])refuse(@"Drawable type differs");
 id<MTLTexture> t=((id<CAMetalDrawable>)drawable).texture;
 if(!t||t.framebufferOnly||t.width!=800||t.height!=600||t.pixelFormat!=MTLPixelFormatBGRA8Unorm)refuse(@"Capture target differs");
 capture=[device newBufferWithLength:1997312 options:MTLResourceStorageModeShared];if(!capture)refuse(@"Capture buffer unavailable");memset(capture.contents,0xa5,capture.length);
 id<MTLBlitCommandEncoder> blit=[(id<MTLCommandBuffer>)self blitCommandEncoder];if(!blit)refuse(@"Capture blit unavailable");
 [blit copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(800,600,1) toBuffer:capture destinationOffset:256 destinationBytesPerRow:3328 destinationBytesPerImage:1996800];[blit endEncoding];capturedCB=self;
 Class base=class_getSuperclass(object_getClass(self));typedef void(*F)(id,SEL,id<MTLDrawable>);((F)class_getMethodImplementation(base,cmd))(self,cmd,drawable);
}
static id<MTLCommandBuffer> captureQueueBuffer(id self,SEL cmd){
 Class base=class_getSuperclass(object_getClass(self));typedef id<MTLCommandBuffer>(*F)(id,SEL);id<MTLCommandBuffer> cb=((F)class_getMethodImplementation(base,cmd))(self,cmd);if(!cb)refuse(@"Command buffer unavailable");
 Class dyn=object_getClass(cb),native=class_getSuperclass(dyn);Method method=class_getInstanceMethod(native,@selector(presentDrawable:));
 if(!method||(!class_addMethod(dyn,@selector(presentDrawable:),(IMP)present,method_getTypeEncoding(method))&&class_getMethodImplementation(dyn,@selector(presentDrawable:))!=(IMP)present))refuse(@"Local present hook unavailable");return cb;
}
static Class enableCaptureQueue(void){
 Class original=object_getClass(queue);Method m=class_getInstanceMethod(original,@selector(commandBuffer));NSString *n=[@"KMAppleCaptureQueue_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];Class child=objc_allocateClassPair(original,n.UTF8String,0);
 if(!child||!m||!class_addMethod(child,@selector(commandBuffer),(IMP)captureQueueBuffer,method_getTypeEncoding(m)))refuse(@"Local capture queue unavailable");objc_registerClassPair(child);if(class_getInstanceSize(child)!=class_getInstanceSize(original))refuse(@"Queue layout differs");object_setClass(queue,child);return original;
}
static void finish(void){@autoreleasepool{
 const char *path=getenv("KM_REPORT_PATH");if(!path)return;MTKView *view=nil;NSWindow *window=nil;for(NSWindow *w in NSApp.windows){MTKView *v=findView(w.contentView);if(v){if(view){fprintf(stderr,"KM_APP multiple views refused\n");[NSApp terminate:nil];return;}view=v;window=w;}}
 CGSize initial=view?view.drawableSize:CGSizeZero;BOOL initialFramebufferOnly=view?view.framebufferOnly:NO;
 if(view){if(initial.width!=800||initial.height!=600)refuse(@"Original drawable extent differs");view.paused=YES;view.framebufferOnly=NO;[CATransaction flush];Class original=enableCaptureQueue();[view draw];object_setClass(queue,original);}
 id<MTLCommandBuffer> fence=[queue commandBuffer];[fence commit];[fence waitUntilCompleted];NSArray *events=[scope.events copy]?:@[];NSUInteger draws=0;for(NSDictionary *e in events)if([e[@"operation"] isEqual:@"execute_CPU_render_ICB"])draws++;
 BOOL guards=NO,readback=NO;if(capture&&capturedCB.status==MTLCommandBufferStatusCompleted){const unsigned char *p=(const unsigned char*)capture.contents;guards=YES;for(NSUInteger k=0;k<256;k++)guards=guards&&p[k]==0xa5&&p[capture.length-1-k]==0xa5;NSString *output=[@(path) stringByDeletingLastPathComponent];readback=[[NSData dataWithBytes:p length:capture.length]writeToFile:[output stringByAppendingPathComponent:@"frame.bin"] atomically:YES];}
 NSDictionary *report=@{@"status":@"TERMINAL_OBSERVATION",@"device":device.name?:@"",@"registry_id":@(device.registryID),@"family_mac2":@([device supportsFamily:MTLGPUFamilyMac2]),@"view_found":@(view!=nil),@"window_visible":@(window.isVisible),@"initial_drawable_width":@(initial.width),@"initial_drawable_height":@(initial.height),@"initial_framebuffer_only":@(initialFramebufferOnly),@"window_resized_by_bootstrap":@NO,@"fence_status":@(fence.status),@"captured_command_status":@(capturedCB?capturedCB.status:0),@"guards_intact":@(guards),@"draw_events":@(draws),@"events":events,@"pixel_readback":@(readback),@"shader_substitution":@NO,@"pipeline_replacement":@YES,@"default_library_byte_matched":@YES};
 NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];if(data)[data writeToFile:@(path) atomically:YES];[scope restore];[NSApp terminate:nil];
}}
static bool add(Class d,Class base,SEL s,IMP imp){Method m=class_getInstanceMethod(base,s);return m&&class_addMethod(d,s,imp,method_getTypeEncoding(m));}
static id<MTLDevice> replacement(void) NS_RETURNS_RETAINED;
static id<MTLDevice> replacement(void){@autoreleasepool{
 static std::mutex mutex;static bool failed=false;static thread_local bool entered=false;if(entered)return nil;struct Guard{bool &x;explicit Guard(bool &v):x(v){x=true;}~Guard(){x=false;}}guard(entered);std::lock_guard<std::mutex>lock(mutex);if(device)return device;if(failed)return nil;failed=true;
 uint32_t n=0;_NSGetExecutablePath(nullptr,&n);if(!n||n>8192)return nil;char *p=(char*)calloc(n,1);if(!p)return nil;int rc=_NSGetExecutablePath(p,&n);NSData *binary=rc==0?[NSData dataWithContentsOfFile:@(p)]:nil;free(p);
 NSURL *url=[[NSBundle mainBundle] URLForResource:@"default" withExtension:@"metallib"];NSData *carrier=asset("KM_CARRIER_PATH"),*shader=url.isFileURL?[NSData dataWithContentsOfURL:url]:nil,*copy=asset("KM_SHADER_PATH"),*manifest=asset("KM_MANIFEST_PATH");if(![hash(binary)isEqual:appHash]||![hash(carrier)isEqual:carrierHash]||![hash(shader)isEqual:shaderHash]||![shader isEqual:copy]||![hash(manifest)isEqual:manifestHash]){fprintf(stderr,"KM_APP identity refused\n");return nil;}
 NSArray<id<MTLDevice>> *devices=MTLCopyAllDevices();if(devices.count!=1||!KPKepler880MIdentity(devices[0]))return nil;id<MTLDevice>d=devices[0];id<MTLCommandQueue>q=[d newCommandQueue];NSError *error=nil;KPCPUICBScope *s=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:carrier expectedSHA256:carrierHash error:&error];if(!s)return nil;
 if(![s registerRenderVertexLibraryData:shader expectedSHA256:shaderHash manifestData:manifest expectedManifestSHA256:manifestHash error:&error]){[s restore];return nil;}
 Class dyn=object_getClass(d),base=class_getSuperclass(dyn);BOOL ok=add(dyn,base,@selector(newCommandQueue),(IMP)newQueue)&&add(dyn,base,@selector(newDefaultLibrary),(IMP)defaultLibrary)&&add(dyn,base,@selector(newRenderPipelineStateWithDescriptor:error:),(IMP)pipeline);
 if(!ok||![s enableAutomaticRenderEncoderFactoriesWithError:&error]){[s restore];fprintf(stderr,"KM_APP setup refused %s\n",error.description.UTF8String?:"");return nil;}scope=s;device=d;queue=q;certifiedDefault=[shader copy];
 dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),dispatch_get_main_queue(),^{finish();});fprintf(stderr,"KM_APP scoped adaptation enabled\n");return d;
}}
// A refused setup should not leave the sample's GUI running indefinitely.
// This cannot interrupt a blocked GPU or main thread and is never a kill.
__attribute__((constructor)) static void watchdog(void){dispatch_after(dispatch_time(DISPATCH_TIME_NOW,12*NSEC_PER_SEC),dispatch_get_main_queue(),^{fprintf(stderr,"KM_APP watchdog requested normal termination\n");[NSApp terminate:nil];});}
__attribute__((used)) static struct {const void *replacement;const void *replacee;} interpose[] __attribute__((section("__DATA,__interpose")))={{(const void*)replacement,(const void*)MTLCreateSystemDefaultDevice}};
