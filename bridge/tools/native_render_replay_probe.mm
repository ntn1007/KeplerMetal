#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import "KeplerNativeRenderDraws.h"
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>

static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString new];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
static NSData*readMemory(uintptr_t p,size_t n){if(!n)return [NSData data];if(!p||n>4096)return nil;NSMutableData*d=[NSMutableData dataWithLength:n];mach_vm_size_t size=0;return mach_vm_read_overwrite(mach_task_self(),p,n,(mach_vm_address_t)d.mutableBytes,&size)==KERN_SUCCESS&&size==n?d:nil;}
static NSDictionary*save(NSData*d,NSString*dir,NSString*name){NSString*p=[dir stringByAppendingPathComponent:name];BOOL ok=d&&[d writeToFile:p atomically:YES];return @{@"file":p,@"bytes":@(d.length),@"SHA256":d?sha(d):@"",@"saved":@(ok)};}
static MTLScissorRect rectangles[3]={{3,4,13,9},{25,8,11,17},{9,30,21,11}};
static id<MTLTexture>target(id<MTLDevice>d){MTLTextureDescriptor*t=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];t.storageMode=MTLStorageModePrivate;t.usage=MTLTextureUsageRenderTarget;return[d newTextureWithDescriptor:t];}
static BOOL fillIndices(id<MTLCommandQueue>q,id<MTLBuffer>a,id<MTLBuffer>b,NSString*dir,NSString*label){
    id<MTLBuffer>sa=[q.device newBufferWithLength:a.length options:MTLResourceStorageModeShared],sb=[q.device newBufferWithLength:b.length options:MTLResourceStorageModeShared];if(!sa||!sb)return NO;
    memset(sa.contents,0xa5,sa.length);memset(sb.contents,0xa5,sb.length);uint16_t i16[]={0,1,2};uint32_t i32[]={0,1,2};memcpy((char*)sa.contents+64,i16,sizeof i16);memcpy((char*)sb.contents+96,i32,sizeof i32);
    id<MTLBuffer>ra=[q.device newBufferWithLength:a.length options:MTLResourceStorageModeShared],rb=[q.device newBufferWithLength:b.length options:MTLResourceStorageModeShared];if(!ra||!rb)return NO;memset(ra.contents,0xcc,ra.length);memset(rb.contents,0xcc,rb.length);
    id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>e=[cb blitCommandEncoder];[e copyFromBuffer:sa sourceOffset:0 toBuffer:a destinationOffset:0 size:sa.length];[e copyFromBuffer:sb sourceOffset:0 toBuffer:b destinationOffset:0 size:sb.length];[e copyFromBuffer:a sourceOffset:0 toBuffer:ra destinationOffset:0 size:a.length];[e copyFromBuffer:b sourceOffset:0 toBuffer:rb destinationOffset:0 size:b.length];[e endEncoding];[cb commit];[cb waitUntilCompleted];
    save([NSData dataWithBytes:ra.contents length:ra.length],dir,[label stringByAppendingString:@".indices16.bin"]);save([NSData dataWithBytes:rb.contents length:rb.length],dir,[label stringByAppendingString:@".indices32.bin"]);
    return cb.status==MTLCommandBufferStatusCompleted&&!memcmp(sa.contents,ra.contents,a.length)&&!memcmp(sb.contents,rb.contents,b.length);
}
static BOOL patchIndices(id<MTLCommandQueue>q,id<MTLBuffer>indices,BOOL wide,NSString*dir){
    NSUInteger n=wide?12:6,offset=wide?96:64;id<MTLBuffer>s=[q.device newBufferWithLength:n options:MTLResourceStorageModeShared],r=[q.device newBufferWithLength:indices.length options:MTLResourceStorageModeShared];if(!s||!r)return NO;
    memset(s.contents,0,n);if(wide){uint32_t one=1;for(unsigned i=0;i<3;i++)memcpy((char*)s.contents+4*i,&one,4);}memset(r.contents,0xcc,r.length);
    id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLBlitCommandEncoder>e=[cb blitCommandEncoder];[e copyFromBuffer:s sourceOffset:0 toBuffer:indices destinationOffset:offset size:n];[e copyFromBuffer:indices sourceOffset:0 toBuffer:r destinationOffset:0 size:r.length];[e endEncoding];[cb commit];[cb waitUntilCompleted];save([NSData dataWithBytes:r.contents length:r.length],dir,wide?@"degenerate.indices32.bin":@"degenerate.indices16.bin");return cb.status==MTLCommandBufferStatusCompleted;
}
static NSArray<KPRecordedNativeRenderDraw*>*makeRecords(KPNativeRenderDrawBatch*batch,id<MTLCommandQueue>q,id<MTLBuffer>i16,id<MTLBuffer>i32,NSError**error){
    id<MTLTexture>dummy=target(q.device);MTLRenderPassDescriptor*p=[MTLRenderPassDescriptor renderPassDescriptor];p.colorAttachments[0].texture=dummy;p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:p];NSMutableArray*r=[NSMutableArray new];
    for(NSUInteger j=0;j<3;j++){KPRecordedNativeRenderDraw*x=[batch recordOnEncoder:e kind:j indexBuffer:j==1?i16:j==2?i32:nil offset:j==1?64:j==2?96:0 instances:j==2?2:1 scissor:rectangles[j] error:error];if(!x){[e endEncoding];return nil;}[r addObject:x];}
    [e endEncoding];return r;
}
static BOOL nativeControl(KPNativeRenderDrawBatch*b,id<MTLCommandBuffer>cb,id<MTLTexture>t,id<MTLBuffer>i16,id<MTLBuffer>i32){
    MTLRenderPassDescriptor*p=[MTLRenderPassDescriptor renderPassDescriptor];p.colorAttachments[0].texture=t;p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;p.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
    id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:p];[e setRenderPipelineState:b.pipeline];
    for(NSUInteger j=0;j<3;j++){[e setScissorRect:rectangles[j]];if(j)[e drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:j==1?MTLIndexTypeUInt16:MTLIndexTypeUInt32 indexBuffer:j==1?i16:i32 indexBufferOffset:j==1?64:96 instanceCount:j==2?2:1];else[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];}
    [e endEncoding];return e!=nil;
}
int main(int argc,char**argv){@autoreleasepool{
    if(argc!=4)return 1;NSString*dir=@(argv[2]);BOOL execute=[@(argv[3])isEqual:@"execute"];
    NSData*library=[NSData dataWithContentsOfFile:@(argv[1])];id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
    id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;KPNativeRenderDrawBatch*batch=[[KPNativeRenderDrawBatch alloc]initWithQueue:q libraryData:library error:&error];if(!batch)return 3;
    id<MTLBuffer>i16=[d newBufferWithLength:128 options:MTLResourceStorageModePrivate],i32=[d newBufferWithLength:192 options:MTLResourceStorageModePrivate];if(!i16||!i32||!fillIndices(q,i16,i32,dir,@"initial"))return 4;
    NSArray<KPRecordedNativeRenderDraw*>*records=makeRecords(batch,q,i16,i32,&error);if(records.count!=3){fprintf(stderr,"%s\n",error.description.UTF8String);return 5;}
    NSMutableArray*recordEvidence=[NSMutableArray new];for(NSUInteger j=0;j<3;j++)[recordEvidence addObject:@{@"record":records[j].evidence,@"raw":save(records[j].commands,dir,[NSString stringWithFormat:@"record-%lu.commands.bin",(unsigned long)j])}];
    // Invalid range is refused before creating a render encoder or editing words.
    id<MTLCommandBuffer>invalid=[q commandBuffer];BOOL rejected=![batch encodeRecords:records selected:[NSIndexSet indexSetWithIndex:3] toCommandBuffer:invalid target:target(d) evidence:nil error:&error];if(!rejected)return 6;
    NSMutableArray*runs=[NSMutableArray new];BOOL passed=YES;
    for(NSUInteger trial=0;trial<(execute?8:1);trial++){@autoreleasepool{
        if((trial==6&&!patchIndices(q,i16,NO,dir))||(trial==7&&!patchIndices(q,i32,YES,dir)))return 8;
        id<MTLTexture>t=target(d);id<MTLBuffer>readback=[d newBufferWithLength:64*48*16+512 options:MTLResourceStorageModeShared];if(!t||!readback)return 7;memset(readback.contents,0xa5,readback.length);
        id<MTLCommandBuffer>cb=[q commandBuffer];NSDictionary*ev=nil;NSIndexSet*selected=trial==2?[NSIndexSet indexSetWithIndexesInRange:NSMakeRange(0,1)]:trial==3?[NSIndexSet indexSetWithIndex:1]:trial==4?[NSIndexSet indexSet]:[NSIndexSet indexSetWithIndexesInRange:NSMakeRange(0,3)];
        if(trial==2){NSMutableIndexSet*s=[selected mutableCopy];[s addIndex:2];selected=s;}
        BOOL ok=YES;__weak KPNativeRenderDrawBatch*weakBatch=nil;__weak KPRecordedNativeRenderDraw*weakRecord=nil;__weak id<MTLBuffer>weakIndex=nil;
        if(execute&&trial==0)ok=nativeControl(batch,cb,t,i16,i32);
        else if(trial==5){@autoreleasepool{
            KPNativeRenderDrawBatch*owned=[[KPNativeRenderDrawBatch alloc]initWithQueue:q libraryData:library error:&error];id<MTLBuffer>a=[d newBufferWithLength:128 options:MTLResourceStorageModePrivate],b=[d newBufferWithLength:192 options:MTLResourceStorageModePrivate];if(!owned||!a||!b||!fillIndices(q,a,b,dir,@"lifetime"))return 8;
            NSArray*ownedRecords=makeRecords(owned,q,a,b,&error);if(ownedRecords.count!=3)return 8;
            ok=[owned encodeRecords:ownedRecords selected:selected toCommandBuffer:cb target:t evidence:&ev error:&error];weakBatch=owned;weakRecord=ownedRecords[1];weakIndex=a;
        }}
        else ok=[batch encodeRecords:records selected:selected toCommandBuffer:cb target:t evidence:&ev error:&error];
        if(!ok){fprintf(stderr,"%s\n",error.description.UTF8String);return 9;}
        BOOL held=trial!=5||(weakBatch!=nil&&weakRecord!=nil&&weakIndex!=nil);if(!held)return 10;
        NSDictionary*stream=ev?save(readMemory([ev[@"stream_base_address"]unsignedLongLongValue],[ev[@"stream_bytes"]unsignedIntegerValue]),dir,[NSString stringWithFormat:@"trial-%lu.commands.bin",(unsigned long)trial]):@{};
        NSDictionary*before=save([NSData dataWithBytes:readback.contents length:readback.length],dir,[NSString stringWithFormat:@"trial-%lu.before.bin",(unsigned long)trial]);
        id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:readback destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[blit endEncoding];
        NSUInteger errors=0,colored=0;if(execute){[cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return 11;
            const float*px=(const float*)((const char*)readback.contents+256);for(NSUInteger y=0;y<48;y++)for(NSUInteger x=0;x<64;x++){BOOL covered=NO;for(NSUInteger j=selected.firstIndex;j!=NSNotFound;j=[selected indexGreaterThanIndex:j]){if(j==1&&trial>=6||j==2&&trial>=7)continue;auto r=rectangles[j];if(x>=r.x&&x<r.x+r.width&&y>=r.y&&y<r.y+r.height)covered=YES;}if(covered)colored++;float expect[]={covered?.75f:0,covered?.125f:0,covered?.25f:0,covered?1.f:0};for(unsigned k=0;k<4;k++)if(px[(y*64+x)*4+k]!=expect[k])errors++;}
            for(NSUInteger k=0;k<readback.length;k++)if((k<256||k>=readback.length-256)&&((const unsigned char*)readback.contents)[k]!=0xa5)errors++;
        }
        NSDictionary*after=save([NSData dataWithBytes:readback.contents length:readback.length],dir,[NSString stringWithFormat:@"trial-%lu.after.bin",(unsigned long)trial]);passed&=!errors;
        NSMutableArray*selection=[NSMutableArray new];for(NSUInteger j=selected.firstIndex;j!=NSNotFound;j=[selected indexGreaterThanIndex:j])[selection addObject:@(j)];
        [runs addObject:@{@"trial":@(trial),@"native_control":@(execute&&trial==0),@"selected":selection,@"committed":@(execute),@"command_status":@(cb.status),@"colored_pixels":@(colored),@"mismatches":@(errors),@"evidence":ev?:@{},@"stream":stream,@"before":before,@"after":after,@"caller_release_lifetime":@(trial==5),@"weak_batch_record_private_index_alive_before_commit":@(held)}];
    }}
    NSDictionary*r=@{@"mode":execute?@"execute":@"prepare",@"passed":@(passed),@"device":d.name,@"registry_id":@(d.registryID),@"library_SHA256":sha(library),@"records":recordEvidence,@"runs":runs,@"range_rejection":@(rejected),@"GPU_user_render_command_buffers":@(execute?8:0),@"GPU_index_upload_command_buffers":@(execute?4:1),@"recording_buffers_committed":@NO,@"native_shader_code_patched":@NO,@"system_modified":@NO,@"render_ICB_implemented":@NO,@"GPU_resident_ICB":@NO,@"performance_benchmark":@NO,@"integration_level":@1};NSData*json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");return passed?0:12;
}}
