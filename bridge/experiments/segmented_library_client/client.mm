// SPDX-License-Identifier: MIT
// Independent, explicitly selected public-Metal test client; no project API.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdint>
#include <cstring>

struct Arguments { uint32_t seed, n, local, groups, variant; };
static_assert(sizeof(Arguments) == 20, "shader ABI");

int main(int argc, char **argv) {
 @autoreleasepool { @try {
  if (argc != 4) return 1;
  NSString *file = @(argv[1]), *directory = @(argv[2]), *mode = @(argv[3]);
  if (![mode isEqual:@"run"] && ![mode isEqual:@"construct"]) return 1;
  NSData *input = [NSData dataWithContentsOfFile:file];
  if (!input || input.length < 3) return 2;
  // Distinct owned backing allocations ensure that dispatch_data_apply can
  // witness a real segmented input, not merely three contiguous subranges.
  NSMutableArray<NSData *> *owners = [NSMutableArray new];
  dispatch_data_t combined = dispatch_data_empty;
  NSUInteger position = 0;
  for (NSUInteger k = 0; k < 3; ++k) {
   NSUInteger length = k == 2 ? input.length - position : input.length / 3;
   NSData *piece = [[NSData alloc] initWithBytes:(const uint8_t *)input.bytes + position length:length];
   if (!piece || !piece.length) return 3;
   [owners addObject:piece];
   dispatch_data_t part = dispatch_data_create(piece.bytes, piece.length,
        dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{ (void)piece.length; });
   if (!part) return 4;
   combined = dispatch_data_create_concat(combined, part);
   position += length;
  }
  __block NSUInteger segments = 0, bytesSeen = 0;
  dispatch_data_apply(combined, ^bool(dispatch_data_t region, size_t offset, const void *buffer, size_t size) {
   (void)region; (void)offset; (void)buffer; ++segments; bytesSeen += size; return true;
  });
  if (segments < 2 || bytesSeen != input.length) return 5;
  id<MTLDevice> device = MTLCreateSystemDefaultDevice();
  if (!device || ![device.name isEqual:@"NVIDIA GeForce GTX 880M"]) return 6;
  NSError *error = nil;
  id<MTLLibrary> library = [device newLibraryWithData:combined error:&error];
  if (!library) { fprintf(stderr, "library creation failed\n"); return 7; }
  id<MTLFunction> function = [library newFunctionWithName:@"sdk_cas_noise"];
  id<MTLComputePipelineState> pipeline = function ? [device newComputePipelineStateWithFunction:function error:&error] : nil;
  if (!pipeline || pipeline.maxTotalThreadsPerThreadgroup < 1024) return 8;
  NSMutableArray *runs = [NSMutableArray new];
  if ([mode isEqual:@"run"]) {
   id<MTLCommandQueue> queue = [device newCommandQueue];
   if (!queue) return 9;
   for (NSNumber *width in @[@33, @128, @1024]) for (uint32_t variant = 0; variant < 2; ++variant) for (uint32_t iteration = 0; iteration < 3; ++iteration) {
    @autoreleasepool {
     uint32_t local = width.unsignedIntValue; Arguments p = {0x2468u + 53u * iteration, local * 3, local, 3, variant};
     NSUInteger nbytes = (NSUInteger)p.n * 16 + 128;
     id<MTLBuffer> out = [device newBufferWithLength:nbytes options:MTLResourceStorageModeShared];
     id<MTLBuffer> unused = [device newBufferWithLength:(NSUInteger)p.n*4 options:MTLResourceStorageModeShared];
     if (!out || !unused || !out.contents) return 10;
     memset(out.contents, 0xa5, nbytes);
     id<MTLCommandBuffer> cb = [queue commandBuffer];
     id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
     if (!cb || !enc) return 11;
     [enc setComputePipelineState:pipeline]; [enc setBytes:&p length:sizeof p atIndex:0];
     [enc setBuffer:out offset:64 atIndex:1]; [enc setBuffer:unused offset:0 atIndex:3];
     [enc dispatchThreadgroups:MTLSizeMake(3,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];
     [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
     if (cb.status != MTLCommandBufferStatusCompleted) return 12;
     NSString *name = [NSString stringWithFormat:@"case-%u-%u-%u.bin", local, variant, iteration];
     if (![[NSData dataWithBytes:out.contents length:nbytes] writeToFile:[directory stringByAppendingPathComponent:name] atomically:YES]) return 13;
     [runs addObject:@{@"local":@(local), @"groups":@3, @"variant":@(variant), @"iteration":@(iteration), @"seed":@(p.seed), @"file":name, @"command_status":@(cb.status)}];
    }
   }
  }
  NSDictionary *report = @{@"mode":mode, @"device":device.name, @"registry_id":@(device.registryID), @"segments":@(segments), @"library_bytes":@(bytesSeen), @"runs":runs};
  NSData *json = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];
  if (!json) return 14; fwrite(json.bytes,1,json.length,stdout); puts(""); return 0;
 } @catch (NSException *e) { fprintf(stderr,"exception %s\n",e.name.UTF8String); return 15; } }
}
