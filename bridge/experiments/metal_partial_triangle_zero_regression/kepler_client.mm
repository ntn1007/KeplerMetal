// Public-Metal client for a pinned, opt-in Kepler rendering scope.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstring>

static void require(BOOL ok, NSString *why) { if (!ok) @throw [NSException exceptionWithName:@"EmptyDrawFailure" reason:why userInfo:nil]; }

int main(int argc, char **argv) { @autoreleasepool { @try {
    require(argc == 4, @"usage: client library auto|direct output-directory");
    NSString *mode = @(argv[2]);
    require([mode isEqual:@"auto"] || [mode isEqual:@"direct"], @"invalid mode");
    BOOL autoMode = [mode isEqual:@"auto"];
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    require(d != nil && [d.name isEqual:@"NVIDIA GeForce GTX 880M"], @"device differs");
    id<MTLCommandQueue> q = [d newCommandQueue];
    NSError *error = nil;
    id<MTLLibrary> lib = [d newLibraryWithFile:@(argv[1]) error:&error];
    require(lib != nil, error.description ?: @"library unavailable");
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [lib newFunctionWithName:@"vs_state"];
    pd.fragmentFunction = [lib newFunctionWithName:@"fs_state"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    id<MTLRenderPipelineState> pipeline = [d newRenderPipelineStateWithDescriptor:pd error:&error];
    require(pipeline != nil, error.description ?: @"pipeline unavailable");
    uint16_t data[] = {0,1,2};
    id<MTLBuffer> indices = [d newBufferWithBytes:data length:sizeof(data) options:MTLResourceStorageModeShared];
    require(indices != nil, @"index buffer unavailable");
    MTLIndirectCommandBufferDescriptor *desc = [MTLIndirectCommandBufferDescriptor new];
    desc.commandTypes = MTLIndirectCommandTypeDraw | MTLIndirectCommandTypeDrawIndexed;
    desc.inheritPipelineState = NO; desc.inheritBuffers = NO;
    id<MTLIndirectCommandBuffer> commands = autoMode ? [d newIndirectCommandBufferWithDescriptor:desc maxCommandCount:1 options:MTLResourceStorageModeShared] : nil;
    require(!autoMode || commands != nil, @"project ICB unavailable");
    NSUInteger rejected = 0;
    if (autoMode) {
        id<MTLIndirectRenderCommand> c = [commands indirectRenderCommandAtIndex:0];
        @try { [c drawPrimitives:MTLPrimitiveTypePoint vertexStart:0 vertexCount:0 instanceCount:1 baseInstance:0]; } @catch(NSException *e) { if ([e.name isEqual:@"KeplerCPUICBUnsupported"] && [e.reason isEqual:@"Direct render geometry outside supported profile"]) rejected++; }
        @try { [c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:4 instanceCount:1 baseInstance:0]; } @catch(NSException *e) { if ([e.name isEqual:@"KeplerCPUICBUnsupported"] && [e.reason isEqual:@"Direct render geometry outside supported profile"]) rejected++; }
        @try { [c drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:0 indexType:MTLIndexTypeUInt16 indexBuffer:indices indexBufferOffset:1 instanceCount:1 baseVertex:0 baseInstance:0]; } @catch(NSException *e) { if ([e.name isEqual:@"KeplerCPUICBUnsupported"] && [e.reason isEqual:@"Indexed render geometry outside supported profile"]) rejected++; }
        require(rejected==3,@"unqualified geometry or resource accepted");
    }
    NSArray *kinds = @[@"normal", @"zero_count", @"zero_instances", @"indexed_normal", @"indexed_zero_count", @"indexed_zero_instances", @"normal_after_reset"];
    NSMutableArray *rows = [NSMutableArray new];
    for (NSString *kind in kinds) {
        BOOL indexed = [kind hasPrefix:@"indexed"];
        NSUInteger count = [kind hasSuffix:@"zero_count"] ? 0 : 3;
        NSUInteger instances = [kind hasSuffix:@"zero_instances"] ? 0 : 1;
        if (autoMode) {
            [commands resetWithRange:NSMakeRange(0,1)];
            id<MTLIndirectRenderCommand> c = [commands indirectRenderCommandAtIndex:0];
            [c setRenderPipelineState:pipeline];
            if (indexed) [c drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:count indexType:MTLIndexTypeUInt16 indexBuffer:indices indexBufferOffset:0 instanceCount:instances baseVertex:0 baseInstance:0];
            else [c drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:count instanceCount:instances baseInstance:0];
        }
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];
        td.storageMode = MTLStorageModePrivate; td.usage = MTLTextureUsageRenderTarget;
        id<MTLTexture> texture = [d newTextureWithDescriptor:td];
        id<MTLBuffer> output = [d newBufferWithLength:64*48*16+512 options:MTLResourceStorageModeShared];
        require(texture && output, @"resource allocation failed");
        memset(output.contents, 0xa5, output.length);
        MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
        pass.colorAttachments[0].texture=texture; pass.colorAttachments[0].loadAction=MTLLoadActionClear;
        pass.colorAttachments[0].storeAction=MTLStoreActionStore; pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> encoder = [cb renderCommandEncoderWithDescriptor:pass];
        require(cb && encoder, @"render encoder unavailable");
        [encoder setRenderPipelineState:pipeline];
        if (autoMode) [encoder executeCommandsInBuffer:commands withRange:NSMakeRange(0,1)];
        else if (indexed) [encoder drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:count indexType:MTLIndexTypeUInt16 indexBuffer:indices indexBufferOffset:0 instanceCount:instances baseVertex:0 baseInstance:0];
        else [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:count instanceCount:instances baseInstance:0];
        [encoder endEncoding];
        id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
        [blit copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:output destinationOffset:256 destinationBytesPerRow:64*16 destinationBytesPerImage:64*48*16];
        [blit endEncoding]; [cb commit]; [cb waitUntilCompleted];
        require(cb.status==MTLCommandBufferStatusCompleted, cb.error.description ?: @"GPU failed");
        const uint8_t *bytes=(const uint8_t *)output.contents;
        for (NSUInteger i=0;i<256;i++) require(bytes[i]==0xa5 && bytes[output.length-1-i]==0xa5,@"guard differs");
        const float *pixels=(const float *)(bytes+256);
        BOOL empty=[kind containsString:@"zero_"];
        const float color[]={.75f,.125f,.25f,1.f};
        for (NSUInteger i=0;i<64*48*4;i++) require(pixels[i]==(empty?0.f:color[i%4]), @"CPU pixel oracle differs");
        NSString *path=[@(argv[3]) stringByAppendingPathComponent:[kind stringByAppendingString:@".bin"]];
        require(![[NSFileManager defaultManager] fileExistsAtPath:path], @"output file already exists");
        NSData *capture=[NSData dataWithBytes:bytes length:output.length];
        require([capture writeToURL:[NSURL fileURLWithPath:path] options:NSDataWritingWithoutOverwriting error:&error], error.description ?: @"cannot save output");
        [rows addObject:@{@"case":kind,@"empty":@(empty),@"checked_channels":@(64*48*4),@"guard_bytes":@512,@"completed":@YES}];
    }
    NSDictionary *report=@{@"status":@"PASS",@"device":d.name,@"registry_id":@(d.registryID),@"device_class":NSStringFromClass(object_getClass(d)),@"mode":mode,@"rejections":@(rejected),@"cases":rows};
    NSData *json=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];
    require(json!=nil,error.description?:@"JSON failed");fwrite(json.bytes,1,json.length,stdout);putchar('\n');return 0;
} @catch(NSException *e) { fprintf(stderr,"%s: %s\n",e.name.UTF8String,e.reason.UTF8String);return 1; } } }
