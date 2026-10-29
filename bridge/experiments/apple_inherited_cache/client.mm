// SPDX-License-Identifier: MIT
// Bounded host for the separately obtained and locally adapted Apple renderer.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <MetalKit/MetalKit.h>
#import <QuartzCore/QuartzCore.h>
#import "KeplerCPUICB.h"
#import "AAPLRenderer.h"
#import "AAPLViewController.h"
extern "C" {
NSString *KMMode, *KMLegacy, *KMShader, *KMManifest, *KMOutput;
KPCPUICBScope *KMScope;
NSMutableArray *KMFrames, *KMDepthActions, *KMSubmittedCBs;
NSInteger KMRefusals, KMBindingRefusals;
BOOL KMActive;
}
static void need(BOOL x, NSString *s){if(!x) @throw [NSException exceptionWithName:@"RealRenderer" reason:s userInfo:nil];}
struct CloseWindow { __strong NSWindow *w; ~CloseWindow(){[w orderOut:nil];[w close];} };
int main(int argc,char **argv){@autoreleasepool{@try{
 need(argc==7,@"arguments");KMLegacy=@(argv[1]);KMShader=@(argv[2]);KMManifest=@(argv[3]);KMOutput=@(argv[4]);KMMode=@(argv[5]);need([@[@"direct",@"auto",@"blank"] containsObject:KMMode],@"mode");KMFrames=[NSMutableArray new];KMDepthActions=[NSMutableArray new];KMSubmittedCBs=[NSMutableArray new];
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"device");
 [NSApplication sharedApplication];[NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];[NSApp finishLaunching];
 NSBundle *bundle=[NSBundle bundleWithPath:@(argv[6])];need(bundle!=nil,@"storyboard bundle");NSStoryboard *storyboard=[NSStoryboard storyboardWithName:@"Main" bundle:bundle];need(storyboard!=nil,@"storyboard");id initial=[storyboard instantiateInitialController];need([initial isKindOfClass:NSWindowController.class],@"initial controller");NSWindowController *wc=initial;NSWindow *w=wc.window;need(w!=nil,@"window");CloseWindow cleanup{w};w.releasedWhenClosed=NO;w.ignoresMouseEvents=YES;[w setContentSize:NSMakeSize(64,48)];
 NSViewController *vc=w.contentViewController;need([vc isKindOfClass:AAPLViewController.class],@"Apple view controller");NSView *loaded=vc.view;need([loaded isKindOfClass:MTKView.class],@"storyboard MTKView");MTKView*v=(MTKView*)loaded;need(v.delegate!=nil&&[v.delegate isKindOfClass:AAPLRenderer.class]&&v.device==d,@"Apple renderer or GPU");v.autoResizeDrawable=NO;v.drawableSize=CGSizeMake(64,48);[(AAPLRenderer*)v.delegate mtkView:v drawableSizeWillChange:v.drawableSize];[w orderFrontRegardless];[CATransaction flush];[NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.15]];need(w.isVisible&&!w.isKeyWindow,@"window state");
 NSMutableArray*submissionStatuses=[NSMutableArray new],*pendingObservations=[NSMutableArray new];for(int i=0;i<8;i++){v.drawableSize=CGSizeMake(64,48);[(AAPLRenderer*)v.delegate mtkView:v drawableSizeWillChange:CGSizeMake(64,i%2?32:48)];KMActive=YES;[v draw];KMActive=NO;need(KMFrames.count==(NSUInteger)(i+1)&&KMSubmittedCBs.count==KMFrames.count,@"missing frame");id<MTLCommandBuffer>submitted=KMSubmittedCBs.lastObject;[submissionStatuses addObject:@(submitted.status)];NSUInteger pending=0;for(id<MTLCommandBuffer>observed in KMSubmittedCBs){MTLCommandBufferStatus st=observed.status;if(st>=MTLCommandBufferStatusCommitted&&st<MTLCommandBufferStatusCompleted)pending++;}[pendingObservations addObject:@(pending)];}
 [KMSubmittedCBs.lastObject waitUntilCompleted];for(id<MTLCommandBuffer>submitted in KMSubmittedCBs)need(submitted.status==MTLCommandBufferStatusCompleted,submitted.error.description?:@"GPU failed");
 NSMutableArray *rows=[NSMutableArray new];for(NSUInteger i=0;i<KMFrames.count;i++){id<MTLBuffer>b=KMFrames[i];const unsigned char*p=(const unsigned char*)b.contents;for(NSUInteger k=0;k<256;k++)need(p[k]==0xa5&&p[b.length-1-k]==0xa5,@"guard");NSString*file=[KMOutput stringByAppendingPathComponent:[NSString stringWithFormat:@"frame-%lu.bin",(unsigned long)i]];need([[NSData dataWithBytes:p length:b.length]writeToURL:[NSURL fileURLWithPath:file] options:NSDataWritingWithoutOverwriting error:nil],@"capture write");[rows addObject:@{@"frame":@(i),@"aspect_variant":@(i%2),@"completed":@YES,@"guard_bytes":@512,@"color_readback":@YES}];}
 NSArray*events=KMScope?KMScope.events:@[];if(KMScope)[KMScope restore];NSDictionary*result=@{@"status":@"PASS",@"mode":KMMode,@"device":d.name,@"registry_id":@(d.registryID),@"actual_apple_renderer":@YES,@"original_storyboard":@YES,@"actual_apple_view_controller":@YES,@"application_modified":@YES,@"framebuffer_only":@NO,@"depth_actions":KMDepthActions,@"submission_statuses":submissionStatuses,@"pending_observations":pendingObservations,@"only_last_waited_explicitly":@YES,@"refusals":@(KMRefusals),@"binding_refusals":@(KMBindingRefusals),@"window_visible":@(w.isVisible),@"window_key":@(w.isKeyWindow),@"cases":rows,@"events":events};NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];need(j!=nil,@"json");fwrite(j.bytes,1,j.length,stdout);putchar('\n');return 0;
 }@catch(NSException*x){fprintf(stderr,"%s: %s\n",x.name.UTF8String,x.reason.UTF8String);return 1;}}}
