// SPDX-License-Identifier: MIT
// Construction-only observation; never pass our ICB to an unadapted selector.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
#include <CommonCrypto/CommonDigest.h>
static NSString *sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
static NSDictionary *method(Class c,SEL s){Method m=class_getInstanceMethod(c,s);Class owner=c;while(owner){unsigned n=0;Method*list=class_copyMethodList(owner,&n);BOOL found=NO;for(unsigned i=0;i<n;i++)found|=method_getName(list[i])==s;free(list);if(found)break;owner=class_getSuperclass(owner);}return @{@"selector":NSStringFromSelector(s),@"present":@(m!=nullptr),@"defining_class":owner?NSStringFromClass(owner):@"",@"encoding":m?@(method_getTypeEncoding(m)):@""};}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;NSData*data=[NSData dataWithContentsOfFile:@(argv[1])];
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}if(!d)return 2;
 Class original=object_getClass(d);id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 KPCPUICBScope*scope=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:data expectedSHA256:sha(data)error:&error];if(!scope){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
 MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>t=[d newTextureWithDescriptor:td];
 MTLRenderPassDescriptor*p=[MTLRenderPassDescriptor renderPassDescriptor];p.colorAttachments[0].texture=t;p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;
 id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>e=[scope renderEncoderWithDescriptor:p commandBuffer:cb error:&error];if(!e)return 4;
 Class dynamic=object_getClass(e),native=class_getSuperclass(dynamic);NSMutableArray*rows=[NSMutableArray new];
 for(NSString*s in @[@"executeCommandsInBuffer:withRange:",@"executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:",@"drawPrimitives:indirectBuffer:indirectBufferOffset:",@"drawIndexedPrimitives:indexType:indexBuffer:indexBufferOffset:indirectBuffer:indirectBufferOffset:"]){SEL sel=NSSelectorFromString(s);Method a=class_getInstanceMethod(dynamic,sel),b=class_getInstanceMethod(native,sel);[rows addObject:@{@"dynamic":method(dynamic,sel),@"native":method(native,sel),@"project_override":@(a&&(!b||method_getImplementation(a)!=method_getImplementation(b)))}];}
 [e endEncoding];BOOL untouched=cb.status==MTLCommandBufferStatusNotEnqueued;[scope restore];BOOL restored=object_getClass(d)==original&&object_getClass(e)==native;
 NSDictionary*out=@{@"status":untouched&&restored?@"PASS_PREPARED_NOT_SUBMITTED":@"FAIL",@"device_identity":KPKepler880MIdentity(d),@"device":d.name,@"registry_id":@(d.registryID),@"library_SHA256":sha(data),@"methods":rows,@"scope_events":scope.events,@"GPU_submissions":@0,@"command_status":@(cb.status),@"classes_restored":@(restored),@"foreign_ICB_sent_to_native_selector":@NO};
 NSData*j=[NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return untouched&&restored?0:5;
}}
