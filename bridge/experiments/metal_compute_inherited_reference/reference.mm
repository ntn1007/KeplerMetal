// SPDX-License-Identifier: MIT
// Public Metal reference only. It does not load or modify KeplerMetal.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>

static void require(BOOL ok, NSString *message) {
    if (!ok) { fprintf(stderr, "FAIL: %s\n", message.UTF8String); exit(1); }
}

static void saveBuffer(NSString *dir, NSString *name, id<MTLBuffer> buffer) {
    NSString *path = [dir stringByAppendingPathComponent:name];
    int fd = open(path.fileSystemRepresentation, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0600);
    require(fd >= 0, @"capture file already exists or cannot be opened");
    const unsigned char *data = (const unsigned char *)buffer.contents;
    NSUInteger done = 0;
    while (done < buffer.length) {
        ssize_t n = write(fd, data+done, buffer.length-done);
        require(n > 0, @"capture write failed"); done += (NSUInteger)n;
    }
    require(close(fd) == 0, @"capture close failed");
}

int main(int argc, const char **argv) { @autoreleasepool {
    require(argc == 2, @"provide a fresh existing capture directory");
    NSString *output = [NSString stringWithUTF8String:argv[1]];
    require(output != nil, @"invalid output directory");
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    require(device != nil, @"no Metal device");
    id<MTLCommandQueue> queue = [device newCommandQueue];
    require(queue != nil, @"no command queue");
    NSString *source = @"#include <metal_stdlib>\n"
        "using namespace metal;\n"
        "kernel void a(device uint* out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = 0x1000u + i; }\n"
        "kernel void b(device uint* out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = 0x2000u + i; }\n";
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    require(library != nil, error.localizedDescription ?: @"library failed");
    NSMutableArray<id<MTLComputePipelineState>> *pipelines = [NSMutableArray new];
    for (NSString *name in @[@"a", @"b"]) {
        MTLComputePipelineDescriptor *p = [MTLComputePipelineDescriptor new];
        p.computeFunction = [library newFunctionWithName:name];
        p.supportIndirectCommandBuffers = YES;
        id<MTLComputePipelineState> state = [device newComputePipelineStateWithDescriptor:p options:0 reflection:nil error:&error];
        require(state != nil, error.localizedDescription ?: @"pipeline failed");
        [pipelines addObject:state];
    }
    MTLIndirectCommandBufferDescriptor *desc = [MTLIndirectCommandBufferDescriptor new];
    desc.commandTypes = MTLIndirectCommandTypeConcurrentDispatch;
    desc.inheritPipelineState = YES; desc.inheritBuffers = NO; desc.maxKernelBufferBindCount = 1;
    id<MTLIndirectCommandBuffer> icb = [device newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared];
    require(icb != nil, @"inherited compute ICB unavailable");
    id<MTLBuffer> out = [device newBufferWithLength:64*sizeof(uint32_t) options:MTLResourceStorageModeShared];
    require(out && out.contents, @"shared buffer unavailable");
    id<MTLIndirectComputeCommand> command = [icb indirectComputeCommandAtIndex:0];
    require(command != nil, @"indirect command unavailable");
    [command setKernelBuffer:out offset:0 atIndex:0];
    [command concurrentDispatchThreadgroups:MTLSizeMake(2,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    NSArray<NSNumber *> *order = @[@0,@1,@0];
    NSUInteger checked = 0;
    NSUInteger step = 0;
    for (NSNumber *which in order) {
        for (NSUInteger mode=0; mode<2; mode++) {
            memset(out.contents, 0xa5, out.length);
            id<MTLCommandBuffer> cb = [queue commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            require(cb && enc, @"command buffer/encoder failed");
            [enc setComputePipelineState:pipelines[which.unsignedIntegerValue]];
            if (mode == 0) {
                [enc setBuffer:out offset:0 atIndex:0];
                [enc dispatchThreadgroups:MTLSizeMake(2,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
            } else {
                [enc useResource:out usage:MTLResourceUsageWrite];
                [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];
            }
            [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
            require(cb.status == MTLCommandBufferStatusCompleted, cb.error.localizedDescription ?: @"command failed");
            const uint32_t *values = (const uint32_t *)out.contents;
            uint32_t base = which.unsignedIntegerValue ? 0x2000u : 0x1000u;
            for (uint32_t i=0; i<64; i++) require(values[i] == base+i, @"output mismatch");
            saveBuffer(output, [NSString stringWithFormat:@"%@-%lu.bin", mode ? @"icb" : @"direct", (unsigned long)step], out);
            checked += 64;
        }
        step++;
    }
    memset(out.contents, 0xa5, out.length);
    id<MTLCommandBuffer> control = [queue commandBuffer];
    [control commit]; [control waitUntilCompleted];
    require(control.status == MTLCommandBufferStatusCompleted, @"no-dispatch control failed");
    const uint32_t *values = (const uint32_t *)out.contents;
    for (unsigned i=0; i<64; i++) require(values[i] == 0xa5a5a5a5u, @"no-dispatch buffer changed");
    saveBuffer(output, @"no-dispatch.bin", out);
    NSDictionary *result = @{@"status": @"PASS_NATIVE_REFERENCE", @"device": device.name,
        @"registry_id": @(device.registryID), @"pipeline_order": @[@"a",@"b",@"a"],
        @"direct_runs": @3, @"inherited_icb_runs": @3, @"checked_values": @(checked),
        @"no_dispatch_words": @64, @"reset_tested": @NO, @"kepler_gpu_tested": @NO};
    NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&error];
    require(json != nil, error.localizedDescription ?: @"JSON failed");
    fwrite(json.bytes, 1, json.length, stdout); putchar('\n');
    return 0;
}}
