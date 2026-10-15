// Reuse the exact public-render probe helpers; its renamed entry is not called.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerCPUICB.h"
#define main KPUnusedPublicRenderProbeEntry
#include "cpu_icb_render_probe.mm"
#undef main
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=4)return 1;BOOL execute=[@(argv[3])isEqual:@"execute"];NSString*dir=@(argv[2]);NSData*bytes=[NSData dataWithContentsOfFile:@(argv[1])];id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
    Class original=object_getClass(d),encoderOriginal=nil;id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLTexture>t=texture(d);id<MTLBuffer>rb=[d newBufferWithLength:49664 options:MTLResourceStorageModeShared];if(!t||!rb)return 3;memset(rb.contents,0xa5,rb.length);
    __weak KPCPUICBScope*weakScope=nil;__weak id<MTLIndirectCommandBuffer>weakICB=nil;__weak id<MTLBuffer>weak16=nil,weak32=nil;id<MTLRenderCommandEncoder>e=nil;NSArray*events=nil;
    @autoreleasepool{
        NSError*error=nil;KPCPUICBScope*s=[KPCPUICBScope installRenderingOnDevice:d queue:q libraryData:bytes expectedSHA256:@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7" error:&error];if(!s)return 4;
        id<MTLBuffer>a=[d newBufferWithLength:128 options:MTLResourceStorageModePrivate],z=[d newBufferWithLength:192 options:MTLResourceStorageModePrivate];if(!a||!z||!indices(q,a,z,NO,dir,@"lifetime"))return 5;
        id<MTLIndirectCommandBuffer>b=[d newIndirectCommandBufferWithDescriptor:descriptor() maxCommandCount:4 options:MTLResourceStorageModeShared];if(!b)return 6;bind(b,s,a,z,YES);e=[s renderEncoderWithDescriptor:pass(t) commandBuffer:cb error:&error];if(!e)return 7;encoderOriginal=class_getSuperclass(object_getClass(e));[e setScissorRect:MTLScissorRect{9,30,21,11}];[e executeCommandsInBuffer:b withRange:NSMakeRange(1,2)];events=[s.events copy];NSDictionary*ev=s.events.lastObject[@"evidence"];
        save(memory([ev[@"stream_base_address"]unsignedLongLongValue],[ev[@"stream_bytes"]unsignedIntegerValue]),dir,@"lifetime.commands.bin");save([[NSData alloc]initWithBase64EncodedString:ev[@"native_state_prefix_base64"] options:0],dir,@"lifetime.prefix.bin");weakScope=s;weakICB=b;weak16=a;weak32=z;
    }
    BOOL released=weakScope==nil&&weakICB==nil,held=weak16!=nil&&weak32!=nil,restored=object_getClass(d)==original&&object_getClass(e)==encoderOriginal;if(!released||!held||!restored)return 8;
    [e endEncoding];save([NSData dataWithBytes:rb.contents length:rb.length],dir,@"lifetime.before.bin");id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:rb destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[blit endEncoding];NSUInteger bad=0,colored=0;
    if(execute){if(!done(cb))return 9;const float*px=(const float*)((const char*)rb.contents+256);for(NSUInteger y=0;y<48;y++)for(NSUInteger x=0;x<64;x++){BOOL p=x>=9&&x<30&&y>=30&&y<41;colored+=p;float expected[]={p?.75f:0,p?.125f:0,p?.25f:0,p?1.f:0};for(unsigned k=0;k<4;k++)bad+=px[(y*64+x)*4+k]!=expected[k];}for(NSUInteger k=0;k<rb.length;k++)if(k<256||k>=rb.length-256)bad+=((const unsigned char*)rb.contents)[k]!=0xa5;}
    save([NSData dataWithBytes:rb.contents length:rb.length],dir,@"lifetime.after.bin");NSDictionary*r=@{@"mode":execute?@"execute":@"prepare",@"registry_id":@(d.registryID),@"library_SHA256":sha(bytes),@"events":events,@"scope_and_ICB_released_before_commit":@(released),@"private_indices_alive_before_commit":@(held),@"device_encoder_classes_restored":@(restored),@"committed":@(execute),@"command_status":@(cb.status),@"colored_pixels":@(colored),@"mismatches":@(bad),@"passed":@(!bad),@"system_modified":@NO,@"full_ICB_contract":@NO,@"integration_level":@1};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return bad?10:0;
}}
