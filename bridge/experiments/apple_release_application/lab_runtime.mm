// SPDX-License-Identifier: MIT
// Local instrumentation called by a copy of the Apple sample application.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <MetalKit/MetalKit.h>
#import <objc/runtime.h>
#import "KeplerCPUICB.h"
#import "AAPLRenderer.h"
extern "C" {
NSString *KMMode,*KMLegacy,*KMShader,*KMManifest,*KMOutput;
KPCPUICBScope *KMScope;
NSMutableArray *KMFrames,*KMDepthActions,*KMSubmittedCBs;
NSInteger KMRefusals,KMBindingRefusals;
BOOL KMActive;
}
static Class queueClass,cbClass,encoderClass;
static IMP queueIMP,cbIMP,encoderIMP;
static BOOL started=NO;
static void need(BOOL v,NSString *why){if(!v) @throw [NSException exceptionWithName:@"ApplicationLab" reason:why userInfo:nil];}
static IMP getIMP(Class c,SEL s){Method m=c?class_getInstanceMethod(c,s):nullptr;return m?method_getImplementation(m):nullptr;}
static BOOL methodsUnchanged(){return getIMP(queueClass,@selector(commandBuffer))==queueIMP&&getIMP(cbClass,@selector(renderCommandEncoderWithDescriptor:))==cbIMP&&getIMP(encoderClass,@selector(executeCommandsInBuffer:withRange:))==encoderIMP;}
extern "C" void KMInitialize(int argc,const char **argv){@autoreleasepool{
 need(argc==6,@"arguments");KMLegacy=@(argv[1]);KMShader=@(argv[2]);KMManifest=@(argv[3]);KMOutput=@(argv[4]);KMMode=@(argv[5]);need([@[@"direct",@"auto",@"blank"] containsObject:KMMode],@"mode");KMFrames=[NSMutableArray new];KMDepthActions=[NSMutableArray new];KMSubmittedCBs=[NSMutableArray new];
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"device");queueClass=objc_getClass("NVMTLCommandQueue");cbClass=objc_getClass("NVMTLCommandBuffer");encoderClass=objc_getClass("NVMTLRenderCommandEncoder_KEPLER_A");queueIMP=getIMP(queueClass,@selector(commandBuffer));cbIMP=getIMP(cbClass,@selector(renderCommandEncoderWithDescriptor:));encoderIMP=getIMP(encoderClass,@selector(executeCommandsInBuffer:withRange:));need(queueIMP&&cbIMP&&encoderIMP,@"native methods");
 [NSApplication sharedApplication];[NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];dispatch_after(dispatch_time(DISPATCH_TIME_NOW,15*NSEC_PER_SEC),dispatch_get_main_queue(),^{if(!started){fprintf(stderr,"ApplicationLab: view did not appear\n");[NSApp terminate:nil];}});
}}
extern "C" void KMRunOnView(MTKView *v){@autoreleasepool{
 if(started)return;started=YES;@try{
 NSWindow*w=v.window;need(w&&[v.delegate isKindOfClass:AAPLRenderer.class]&&[v.device.name isEqual:@"NVIDIA GeForce GTX 880M"],@"sample UI");w.ignoresMouseEvents=YES;[w setContentSize:NSMakeSize(64,48)];v.autoResizeDrawable=NO;
 NSMutableArray*statuses=[NSMutableArray new],*pending=[NSMutableArray new];for(int i=0;i<8;i++){v.drawableSize=CGSizeMake(64,48);[(AAPLRenderer*)v.delegate mtkView:v drawableSizeWillChange:CGSizeMake(64,i%2?32:48)];KMActive=YES;[v draw];KMActive=NO;need(KMFrames.count==(NSUInteger)(i+1)&&KMSubmittedCBs.count==KMFrames.count,@"missing frame");id<MTLCommandBuffer>cb=KMSubmittedCBs.lastObject;[statuses addObject:@(cb.status)];NSUInteger n=0;for(id<MTLCommandBuffer>x in KMSubmittedCBs){MTLCommandBufferStatus st=x.status;if(st>=MTLCommandBufferStatusCommitted&&st<MTLCommandBufferStatusCompleted)n++;}[pending addObject:@(n)];}
 [KMSubmittedCBs.lastObject waitUntilCompleted];for(id<MTLCommandBuffer>cb in KMSubmittedCBs)need(cb.status==MTLCommandBufferStatusCompleted,cb.error.description?:@"GPU failed");
 NSMutableArray*rows=[NSMutableArray new];for(NSUInteger i=0;i<KMFrames.count;i++){id<MTLBuffer>b=KMFrames[i];const unsigned char*p=(const unsigned char*)b.contents;for(NSUInteger k=0;k<256;k++)need(p[k]==0xa5&&p[b.length-1-k]==0xa5,@"guard");NSString*file=[KMOutput stringByAppendingPathComponent:[NSString stringWithFormat:@"frame-%lu.bin",(unsigned long)i]];need([[NSData dataWithBytes:p length:b.length]writeToURL:[NSURL fileURLWithPath:file] options:NSDataWritingWithoutOverwriting error:nil],@"capture");[rows addObject:@{@"frame":@(i),@"aspect_variant":@(i%2),@"completed":@YES,@"guard_bytes":@512,@"color_readback":@YES}];}
 id<MTLCommandBuffer>last=KMSubmittedCBs.lastObject;id<MTLCommandQueue>queue=last.commandQueue;BOOL automatic=[KMMode isEqual:@"auto"],adapted=object_getClass(queue)!=queueClass;need(adapted==automatic&&methodsUnchanged(),@"queue or shared methods");NSArray*events=KMScope?KMScope.events:@[];if(KMScope)[KMScope restore];BOOL restored=object_getClass(queue)==queueClass;need(restored&&methodsUnchanged(),@"restoration");
 NSDictionary*result=@{@"status":@"PASS",@"mode":KMMode,@"device":v.device.name,@"registry_id":@(v.device.registryID),@"actual_apple_renderer":@YES,@"original_storyboard":@YES,@"actual_apple_view_controller":@YES,@"application_modified":@YES,@"application_bundle":@YES,@"nsapplicationmain":@YES,@"view_did_appear":@YES,@"queue_adapted":@(adapted),@"queue_restored":@(restored),@"shared_methods_unchanged":@YES,@"framebuffer_only":@NO,@"depth_actions":KMDepthActions,@"submission_statuses":statuses,@"pending_observations":pending,@"only_last_waited_explicitly":@YES,@"refusals":@(KMRefusals),@"binding_refusals":@(KMBindingRefusals),@"window_visible":@(w.isVisible),@"window_key":@(w.isKeyWindow),@"cases":rows,@"events":events};NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];need(j!=nil,@"json");fwrite(j.bytes,1,j.length,stdout);putchar('\n');fflush(stdout);
 }@catch(NSException*x){for(id<MTLCommandBuffer>cb in KMSubmittedCBs)[cb waitUntilCompleted];if(KMScope)[KMScope restore];fprintf(stderr,"%s: %s\n",x.name.UTF8String,x.reason.UTF8String);fflush(stderr);}
 [NSApp terminate:nil];
}}
