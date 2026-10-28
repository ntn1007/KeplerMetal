// SPDX-License-Identifier: MIT
// Observe owned, uncommitted Metal encoding. Never commit or submit commands.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import "KeplerGPUIdentity.h"
#import "KeplerDriverProfile.h"
#include <CommonCrypto/CommonDigest.h>
#include "ICBTextureNativeMetadata.inc"

extern "C" id<MTLComputePipelineState> KPCertifiedConditionalCASPipeline(
 id<MTLDevice>,NSURL*,NSString*,NSData*,NSData*,NSError**,NSDictionary**);

int main(int argc,char**argv){@autoreleasepool{
 if(argc!=6)return 1;
 NSString*libraryPath=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
 if(![@[@"native",@"repaired"] containsObject:mode])return 1;
 NSData*libraryBytes=[NSData dataWithContentsOfFile:libraryPath];
 NSString*libraryHash=sha(libraryBytes),*driver=sha([NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"]);
 if(![libraryHash isEqual:@"811e53236f858247d59ae1540efb1a74160c0e566522faadd9fa82ad60de8640"]||
    ![driver isEqual:@"e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645"]||!KPKeplerDriverHashIsQualified(driver))return 2;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(KPKepler880MIdentity(x)){if(d)return 2;d=x;}if(!d)return 2;
 NSError*error=nil;NSDictionary*proof=nil;id<MTLComputePipelineState>p=nil;
 if([mode isEqual:@"native"]){
  id<MTLLibrary>l=[d newLibraryWithURL:[NSURL fileURLWithPath:libraryPath] error:&error];
  id<MTLFunction>f=[l newFunctionWithName:@"divergence_case"];if(f)p=[d newComputePipelineStateWithFunction:f error:&error];
  [f release];[l release];
 }else{
  NSData*original=[NSData dataWithContentsOfFile:@(argv[4])],*replacement=[NSData dataWithContentsOfFile:@(argv[5])];
  p=KPCertifiedConditionalCASPipeline(d,[NSURL fileURLWithPath:libraryPath],@"divergence_case",original,replacement,&error,&proof);
 }
 if(!p){emit(@{@"failure":@"pipeline",@"error":error.description?:@"",@"import":proof?:@{}});return 3;}
 NSData*v=variant(p);if(v.length!=128||!u32(v,48)||u32(v,48)>63)return 4;
 id<MTLBuffer>output=[d newBufferWithLength:4096 options:MTLResourceStorageModePrivate];
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
 if(!output||!q||!cb||!e)return 5;
 struct{uint32_t seed,local,pattern,variant;}params={0x1234,33,2,1};
 [e setComputePipelineState:p];[e setBytes:&params length:sizeof(params) atIndex:0];[e setBuffer:output offset:64 atIndex:1];
 Cursor before=cursor(e);[e dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(33,1,1)];Cursor after=cursor(e);
 NSData*commands=before.valid&&after.valid&&before.push==after.push&&after.current>before.current&&
  after.current<=before.end&&after.current-before.current<=65536?readMemory(before.current,after.current-before.current):nil;
 [e endEncoding];if(!commands||cb.status!=MTLCommandBufferStatusNotEnqueued)return 6;
 if(![commands writeToFile:[out stringByAppendingPathComponent:@"commands.bin"] atomically:YES]||
    ![v writeToFile:[out stringByAppendingPathComponent:@"variant.bin"] atomically:YES])return 7;
 emit(@{@"status":@"PREPARED_NOT_SUBMITTED",@"mode":mode,@"device":d.name,@"registry_id":@(d.registryID),
   @"driver_SHA256":driver,@"library_SHA256":libraryHash,@"command_SHA256":sha(commands),@"command_bytes":@(commands.length),
   @"variant_SHA256":sha(v),@"variant_bytes":@(v.length),@"command_status":@(cb.status),
   @"GPU_submissions":@0,@"GPU_execution_proved":@NO,@"import":proof?:@{}});
 [output release];[q release];[p release];return 0;
}}
