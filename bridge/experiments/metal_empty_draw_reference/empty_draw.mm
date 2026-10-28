// Public Metal reference for zero-sized and ordinary draws. No Kepler hooks.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>

static void need(BOOL condition, NSString *message) {
    if (!condition) @throw [NSException exceptionWithName:@"ReferenceFailure" reason:message userInfo:nil];
}

static NSDictionary *run(id<MTLDevice> device, id<MTLCommandQueue> queue,
                         id<MTLRenderPipelineState> pipeline, NSString *kind,
                         BOOL indirect) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget;
    td.storageMode = MTLStorageModeShared;
    id<MTLTexture> texture = [device newTextureWithDescriptor:td];
    need(texture != nil, @"shared render texture allocation failed");
    uint16_t indexData[] = {0, 1, 2};
    id<MTLBuffer> indices = [device newBufferWithBytes:indexData length:sizeof(indexData) options:MTLResourceStorageModeShared];
    need(indices != nil, @"index buffer allocation failed");
    BOOL indexed = [kind hasPrefix:@"indexed"];
    NSUInteger count = [kind hasSuffix:@"zero_count"] ? 0 : 3;
    NSUInteger instances = [kind hasSuffix:@"zero_instances"] ? 0 : 1;
    id<MTLIndirectCommandBuffer> icb = nil;
    if (indirect) {
        MTLIndirectCommandBufferDescriptor *d = [MTLIndirectCommandBufferDescriptor new];
        d.commandTypes = indexed ? MTLIndirectCommandTypeDrawIndexed : MTLIndirectCommandTypeDraw;
        d.inheritPipelineState = NO;
        d.inheritBuffers = NO;
        icb = [device newIndirectCommandBufferWithDescriptor:d maxCommandCount:1 options:MTLResourceStorageModeShared];
        need(icb != nil, @"native ICB unavailable");
        id<MTLIndirectRenderCommand> command = [icb indirectRenderCommandAtIndex:0];
        [command reset];
        [command setRenderPipelineState:pipeline];
        if (indexed) [command drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:count indexType:MTLIndexTypeUInt16 indexBuffer:indices indexBufferOffset:0 instanceCount:instances baseVertex:0 baseInstance:0];
        else [command drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:count instanceCount:instances baseInstance:0];
    }
    MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
    pass.colorAttachments[0].texture = texture;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> encoder = [cb renderCommandEncoderWithDescriptor:pass];
    need(cb && encoder, @"encoder unavailable");
    [encoder setRenderPipelineState:pipeline];
    if (indirect) {
        [encoder useResource:indices usage:MTLResourceUsageRead];
        [encoder executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];
    } else if (indexed) {
        [encoder drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:count indexType:MTLIndexTypeUInt16 indexBuffer:indices indexBufferOffset:0 instanceCount:instances baseVertex:0 baseInstance:0];
    } else {
        [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:count instanceCount:instances baseInstance:0];
    }
    [encoder endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    need(cb.status == MTLCommandBufferStatusCompleted, cb.error.description ?: @"command failed");
    uint8_t pixels[16*16*4] = {};
    [texture getBytes:pixels bytesPerRow:16*4 fromRegion:MTLRegionMake2D(0,0,16,16) mipmapLevel:0];
    NSUInteger red = 0, black = 0, other = 0;
    for (NSUInteger i=0; i<256; i++) {
        const uint8_t *p = pixels + i*4;
        if (p[0] == 255 && p[1] == 0 && p[2] == 0 && p[3] == 255) red++;
        else if (p[0] == 0 && p[1] == 0 && p[2] == 0 && p[3] == 255) black++;
        else other++;
    }
    return @{@"red":@(red), @"black":@(black), @"other":@(other), @"completed":@YES};
}

int main(int argc, char **argv) { @autoreleasepool { @try {
    need(argc == 2, @"usage: empty_draw direct|icb");
    NSString *mode = @(argv[1]);
    need([mode isEqual:@"direct"] || [mode isEqual:@"icb"], @"invalid mode");
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    need(device != nil, @"no Metal device");
    id<MTLCommandQueue> queue = [device newCommandQueue];
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\nvertex float4 vs(uint i [[vertex_id]]) { float2 v[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(v[i],0,1); }\nfragment float4 fs() { return float4(1,0,0,1); }\n";
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    need(library != nil, error.description ?: @"library unavailable");
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [library newFunctionWithName:@"vs"];
    pd.fragmentFunction = [library newFunctionWithName:@"fs"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    pd.supportIndirectCommandBuffers = [mode isEqual:@"icb"];
    id<MTLRenderPipelineState> pipeline = [device newRenderPipelineStateWithDescriptor:pd error:&error];
    need(pipeline != nil, error.description ?: @"pipeline unavailable");
    NSMutableDictionary *results = [NSMutableDictionary new];
    for (NSString *kind in @[@"direct_normal", @"direct_zero_count", @"direct_zero_instances", @"indexed_normal", @"indexed_zero_count", @"indexed_zero_instances"])
        results[kind] = run(device, queue, pipeline, kind, [mode isEqual:@"icb"]);
    NSDictionary *report = @{@"device":device.name, @"registry_id":@(device.registryID), @"mode":mode, @"results":results};
    NSData *json = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];
    need(json != nil, error.description ?: @"JSON failure");
    fwrite(json.bytes, 1, json.length, stdout); putchar('\n');
    for (NSString *kind in results) {
        NSDictionary *row = results[kind];
        BOOL empty = [kind containsString:@"zero_"];
        need([row[@"other"] unsignedIntegerValue] == 0 && [row[@"red"] unsignedIntegerValue] == (empty ? 0 : 256) &&
             [row[@"black"] unsignedIntegerValue] == (empty ? 256 : 0), @"pixel oracle differs");
    }
    return 0;
} @catch (NSException *exception) { fprintf(stderr, "%s: %s\n", exception.name.UTF8String, exception.reason.UTF8String); return 1; } } }
