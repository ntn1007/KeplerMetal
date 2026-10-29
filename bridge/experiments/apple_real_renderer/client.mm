// SPDX-License-Identifier: MIT
// Bounded host for the separately obtained and locally adapted Apple renderer.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <MetalKit/MetalKit.h>
#import <QuartzCore/QuartzCore.h>
#import "KeplerCPUICB.h"
#import "AAPLRenderer.h"
extern "C" {
NSString *KMMode, *KMLegacy, *KMShader, *KMManifest, *KMOutput;
KPCPUICBScope *KMScope;
NSMutableArray *KMFrames;
}
static void need(BOOL x, NSString *s){if(!x) @throw [NSException exceptionWithName:@"RealRenderer" reason:s userInfo:nil];}
struct CloseWindow { __strong NSWindow *w; ~CloseWindow(){[w orderOut:nil];[w close];} };
int main(int argc,char **argv){@autoreleasepool{@try{
 need(argc==6,@"arguments");KMLegacy=@(argv[1]);KMShader=@(argv[2]);KMManifest=@(argv[3]);KMOutput=@(argv[4]);KMMode=@(argv[5]);need([@[@"direct",@"auto",@"blank"] containsObject:KMMode],@"mode");KMFrames=[NSMutableArray new];
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();need(d&&[d.name isEqual:@"NVIDIA GeForce GTX 880M"],@"device");
 [NSApplication sharedApplication];[NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];[NSApp finishLaunching];NSScreen*screen=NSScreen.mainScreen;need(screen!=nil,@"no screen");NSRect r=screen.visibleFrame;NSWindow*w=[[NSWindow alloc]initWithContentRect:NSMakeRect(NSMinX(r)+8,NSMinY(r)+8,64,48) styleMask:NSWindowStyleMaskBorderless backing:NSBackingStoreBuffered defer:NO];need(w!=nil,@"window");CloseWindow cleanup{w};w.releasedWhenClosed=NO;w.ignoresMouseEvents=YES;
 MTKView*v=[[MTKView alloc]initWithFrame:NSMakeRect(0,0,64,48) device:d];v.paused=YES;v.enableSetNeedsDisplay=NO;v.framebufferOnly=NO;v.autoResizeDrawable=NO;v.drawableSize=CGSizeMake(64,48);w.contentView=v;AAPLRenderer*renderer=[[AAPLRenderer alloc]initWithMetalKitView:v];need(renderer!=nil,@"renderer");v.delegate=renderer;[renderer mtkView:v drawableSizeWillChange:v.drawableSize];[w orderFrontRegardless];[CATransaction flush];[NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.15]];need(w.isVisible&&!w.isKeyWindow,@"window state");
 for(int i=0;i<2;i++){[v draw];need(KMFrames.count==(NSUInteger)(i+1),@"missing frame");[NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.05]];}
 NSMutableArray *rows=[NSMutableArray new];for(NSUInteger i=0;i<KMFrames.count;i++){id<MTLBuffer>b=KMFrames[i];const unsigned char*p=(const unsigned char*)b.contents;for(NSUInteger k=0;k<256;k++)need(p[k]==0xa5&&p[b.length-1-k]==0xa5,@"guard");NSString*file=[KMOutput stringByAppendingPathComponent:[NSString stringWithFormat:@"frame-%lu.bin",(unsigned long)i]];need([[NSData dataWithBytes:p length:b.length]writeToURL:[NSURL fileURLWithPath:file] options:NSDataWritingWithoutOverwriting error:nil],@"capture write");[rows addObject:@{@"frame":@(i),@"completed":@YES,@"guard_bytes":@512,@"color_readback":@YES}];}
 NSArray*events=KMScope?KMScope.events:@[];if(KMScope)[KMScope restore];NSDictionary*result=@{@"status":@"PASS",@"mode":KMMode,@"device":d.name,@"registry_id":@(d.registryID),@"actual_apple_renderer":@YES,@"application_modified":@YES,@"framebuffer_only":@NO,@"window_visible":@(w.isVisible),@"window_key":@(w.isKeyWindow),@"cases":rows,@"events":events};NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];need(j!=nil,@"json");fwrite(j.bytes,1,j.length,stdout);putchar('\n');return 0;
 }@catch(NSException*x){fprintf(stderr,"%s: %s\n",x.name.UTF8String,x.reason.UTF8String);return 1;}}}
