// SPDX-License-Identifier: MIT
// Target-extent contract checks; no command buffer is committed.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <CommonCrypto/CommonDigest.h>
#import "KeplerCPUICB.h"
#import "KeplerGPUIdentity.h"
static NSString *digest(NSData *d){if(!d)return nil;unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char x:h)[s appendFormat:@"%02x",x];return s;}
static void need(BOOL v,NSString *s){if(!v)@throw [NSException exceptionWithName:@"ExtentContractFailure" reason:s userInfo:nil];}
int main(int argc,const char **argv){@autoreleasepool{@try{
 need(argc==6,@"usage carrier release release-manifest old old-manifest");NSData*c=[NSData dataWithContentsOfFile:@(argv[1])],*newlib=[NSData dataWithContentsOfFile:@(argv[2])],*newm=[NSData dataWithContentsOfFile:@(argv[3])],*oldlib=[NSData dataWithContentsOfFile:@(argv[4])],*oldm=[NSData dataWithContentsOfFile:@(argv[5])];
 NSString *ch=@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7",*nh=@"04d8d8ae6a4485d3be0262e971c365cfff1d5bb04f88f24cdbdfa0ffdee6afa2",*nm=@"b5798a3c5129c4cec893c487cbc9211a439deaedd14a1c3a4857114a949e0ace",*oh=@"adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf",*om=@"6930ed313d2e1b1e836f189afb2db7c0286f10afb9c867ec3fe9659390e16732";
 need([digest(c)isEqual:ch]&&[digest(newlib)isEqual:nh]&&[digest(newm)isEqual:nm]&&[digest(oldlib)isEqual:oh]&&[digest(oldm)isEqual:om],@"asset identities");NSArray<id<MTLDevice>>*ds=MTLCopyAllDevices();need(ds.count==1&&KPKepler880MIdentity(ds[0]),@"GPU identity");id<MTLDevice>d=ds[0];Class native=object_getClass(d);NSMutableArray *rows=[NSMutableArray new];
 for(int profile=0;profile<2;profile++){@autoreleasepool{
  id<MTLCommandQueue>q=[d newCommandQueue];NSError *err=nil;KPCPUICBScope*s=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:c expectedSHA256:ch error:&err];need(s!=nil,err.description?:@"scope");need([s registerRenderVertexLibraryData:profile?oldlib:newlib expectedSHA256:profile?oh:nh manifestData:profile?oldm:newm expectedManifestSHA256:profile?om:nm error:&err],err.description?:@"register");
  NSArray *cases=profile?@[@[@64,@48,@80,@YES],@[@800,@600,@80,@NO]]:@[@[@64,@48,@80,@YES],@[@800,@600,@80,@YES],@[@801,@600,@80,@NO],@[@800,@599,@80,@NO],@[@800,@601,@80,@NO],@[@960,@540,@80,@NO],@[@800,@600,@125,@NO]];
  for(NSArray *item in cases){@autoreleasepool{
   NSUInteger w=[item[0]unsignedIntegerValue],h=[item[1]unsignedIntegerValue];MTLPixelFormat f=(MTLPixelFormat)[item[2]unsignedIntegerValue];BOOL expected=[item[3]boolValue];MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:f width:w height:h mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>texture=[d newTextureWithDescriptor:td];need(texture!=nil,@"texture");MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=texture;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;id<MTLCommandBuffer>cb=[q commandBuffer];err=nil;id<MTLRenderCommandEncoder>encoder=[s renderEncoderWithDescriptor:pass commandBuffer:cb error:&err];need((encoder!=nil)==expected&&cb.status==MTLCommandBufferStatusNotEnqueued,@"extent verdict or command state");if(encoder)[encoder endEncoding];else need([err.localizedDescription isEqual:@"Render pass outside registered native target profiles"],@"unexpected refusal");[rows addObject:@{@"profile":profile?@"old":@"release",@"width":@(w),@"height":@(h),@"format":@(f),@"accepted":@(expected)}];
  }}
  [s restore];need(object_getClass(d)==native,@"device restore");
 }}
 NSDictionary *out=@{@"status":@"PASS",@"device":d.name,@"cases":rows,@"command_buffers_committed":@0,@"GPU_execution_proved":@NO,@"device_restored":@YES};NSData*j=[NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);putchar('\n');return 0;
 }@catch(NSException*e){fprintf(stderr,"%s: %s\n",e.name.UTF8String,e.reason.UTF8String);return 1;}}}
