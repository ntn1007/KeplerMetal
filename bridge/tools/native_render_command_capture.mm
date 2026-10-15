// Passive capture of this process's uncommitted native render command encoder.
// No command-memory writes, injection, private method calls, or GPU submissions.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <cstring>
#include <cstdint>

static NSData *readMemory(uintptr_t p, size_t n) {
    if (!p || !n || n > 65536 || p + n < p) return nil;
    NSMutableData *d = [NSMutableData dataWithLength:n]; mach_vm_size_t actual = 0;
    return mach_vm_read_overwrite(mach_task_self(), p, n,
        (mach_vm_address_t)d.mutableBytes, &actual) == KERN_SUCCESS && actual == n ? d : nil;
}
static uint64_t word(NSData *d, size_t offset) {
    uint64_t v = 0; if (offset + 8 <= d.length) memcpy(&v, (const char *)d.bytes + offset, 8); return v;
}
static NSString *sha(NSData *d) {
    if (!d) return @"";
    unsigned char digest[32]; CC_SHA256(d.bytes, (CC_LONG)d.length, digest);
    NSMutableString *r = [NSMutableString new]; for (unsigned char b : digest) [r appendFormat:@"%02x", b]; return r;
}
static NSDictionary *save(NSData *d, NSString *dir, NSString *name) {
    NSString *p = [dir stringByAppendingPathComponent:name];
    BOOL saved = d && [d writeToFile:p atomically:YES];
    return @{@"file":p, @"bytes":@(d.length), @"saved":@(saved), @"SHA256":sha(d)};
}
static uintptr_t pointerIvar(id obj, const char *name) {
    Ivar v = class_getInstanceVariable(object_getClass(obj), name);
    if (!v || ivar_getTypeEncoding(v)[0] != '^') return 0;
    ptrdiff_t off = ivar_getOffset(v); size_t n = class_getInstanceSize(object_getClass(obj));
    if (off < 0 || (size_t)off + 8 > n) return 0;
    uintptr_t p = 0; memcpy(&p, (const char *)(__bridge const void *)obj + off, 8); return p;
}
static NSDictionary *layout(id obj, NSString *dir, NSString *label) {
    Class cls = object_getClass(obj); NSMutableArray *rows = [NSMutableArray new];
    for (Class owner = cls; owner && owner != [NSObject class]; owner = class_getSuperclass(owner)) {
        unsigned count = 0; Ivar *vars = class_copyIvarList(owner, &count);
        for (unsigned i = 0; i < count; ++i) {
            Ivar v = vars[i]; const char *type = ivar_getTypeEncoding(v);
            NSMutableDictionary *row = [@{@"owner":NSStringFromClass(owner),
                @"name":@(ivar_getName(v)), @"type":@(type), @"offset":@(ivar_getOffset(v))} mutableCopy];
            if (type[0] == '^') {
                uintptr_t p = pointerIvar(obj, ivar_getName(v)); row[@"address"] = @(p);
                if (p && [@[@"m_renderer", @"m_render", @"m_graphics", @"_queue"] containsObject:row[@"name"]])
                    row[@"prefix"] = save(readMemory(p, 256), dir,
                        [NSString stringWithFormat:@"%@-%@.bin", label, row[@"name"]]);
            }
            [rows addObject:row];
        }
        free(vars);
    }
    return @{@"class":NSStringFromClass(cls), @"instance_bytes":@(class_getInstanceSize(cls)), @"ivars":rows};
}
static NSDictionary *methodInfo(id obj, NSString *selector) {
    Method m = class_getInstanceMethod(object_getClass(obj), NSSelectorFromString(selector));
    if (!m) return @{@"selector":selector, @"implemented":@NO};
    IMP p = method_getImplementation(m); Dl_info d = {};
    BOOL found = dladdr((void *)p, &d) != 0;
    return @{@"selector":selector, @"implemented":@YES, @"implementation":@((uintptr_t)p),
        @"image":found && d.dli_fname ? @(d.dli_fname) : @"",
        @"image_offset":@(found ? (uintptr_t)p - (uintptr_t)d.dli_fbase : 0)};
}
struct Cursor { uintptr_t context, push, current, end, queue; size_t pushOffset; };
static Cursor state(id enc, uintptr_t queue, NSString *dir, NSString *label) {
    Cursor c = {}; c.context = pointerIvar(enc, "m_renderer");
    if (!c.context) c.context = pointerIvar(enc, "m_render");
    if (!c.context) c.context = pointerIvar(enc, "m_graphics");
    NSData *prefix = readMemory(c.context, 256);
    if (prefix) save(prefix, dir, [label stringByAppendingString:@".context.bin"]);
    // The runtime encoding and the preceding frozen capture identify the
    // common prefix: device+8, queue+16, command buffer+24, PushBuffer+32.
    // Only read this observed field; never search arbitrary live allocations.
    if (!queue || prefix.length != 256 || word(prefix, 16) != queue) return c;
    uintptr_t candidate = word(prefix, 32); NSData *p = readMemory(candidate, 192);
    if (p) save(p, dir, [label stringByAppendingString:@".push.bin"]);
    uintptr_t begin = word(p, 0), end = word(p, 136);
    if (begin && end > begin && end - begin <= 1048576 && readMemory(begin, 4)) {
        c.push = candidate; c.current = begin; c.end = end; c.queue = queue; c.pushOffset = 32;
    }
    return c;
}
static NSDictionary *cursorInfo(Cursor c) {
    return @{@"context":@(c.context), @"push":@(c.push), @"current":@(c.current),
        @"end":@(c.end), @"queue":@(c.queue), @"push_field_offset":@(c.pushOffset)};
}
int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 3) return 1; NSString *dir = @(argv[2]);
    NSData *driver = [NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
    if (![sha(driver) isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"]) return 2;
    NSData *bytes = [NSData dataWithContentsOfFile:@(argv[1])];
    if (![sha(bytes) isEqual:@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7"]) return 3;
    id<MTLDevice> device = nil;
    for (id<MTLDevice> candidate in MTLCopyAllDevices()) if (candidate.registryID == 4294968458) device = candidate;
    if (!device) return 4; NSError *error = nil;
    dispatch_data_t payload = dispatch_data_create(bytes.bytes, bytes.length,
        dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0), ^{ (void)bytes.length; });
    id<MTLLibrary> library = [device newLibraryWithData:payload error:&error]; if (!library) return 5;
    NSMutableArray *pipelines = [NSMutableArray new];
    for (NSString *vertex in @[@"vs_state", @"vs_half"]) {
        MTLRenderPipelineDescriptor *desc = [MTLRenderPipelineDescriptor new];
        desc.vertexFunction = [library newFunctionWithName:vertex];
        desc.fragmentFunction = [library newFunctionWithName:@"fs_state"];
        desc.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        id<MTLRenderPipelineState> pso = [device newRenderPipelineStateWithDescriptor:desc error:&error];
        if (!pso) return 6; [pipelines addObject:pso];
    }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];
    td.storageMode = MTLStorageModePrivate; td.usage = MTLTextureUsageRenderTarget;
    id<MTLTexture> target = [device newTextureWithDescriptor:td];
    id<MTLBuffer> indices = [device newBufferWithLength:128 options:MTLResourceStorageModeShared];
    if (!target || !indices) return 7; uint16_t tri[] = {0, 1, 2}; memcpy((char *)indices.contents + 64, tri, sizeof tri);
    id<MTLCommandQueue> queue = [device newCommandQueue]; if (!queue) return 8;
    uintptr_t queueCpp = pointerIvar(queue, "_queue");
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
    pass.colorAttachments[0].texture = target; pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass]; if (!enc) return 9;
    NSDictionary *encoderLayout = layout(enc, dir, @"encoder"), *queueLayout = layout(queue, dir, @"queue");
    NSMutableArray *methods = [NSMutableArray new];
    for (NSString *selector in @[@"drawPrimitives:vertexStart:vertexCount:",
        @"drawIndexedPrimitives:indexCount:indexType:indexBuffer:indexBufferOffset:",
        @"executeCommandsInBuffer:withRange:", @"setRenderPipelineState:", @"endEncoding"])
        [methods addObject:methodInfo(enc, selector)];
    NSMutableArray *records = [NSMutableArray new];
    [enc setRenderPipelineState:pipelines[0]];
    for (unsigned step = 0; step < 6; ++step) {
        if (step == 2) [enc setRenderPipelineState:pipelines[1]];
        if (step == 3) [enc setScissorRect:MTLScissorRect{1,1,62,46}];
        NSString *label = [NSString stringWithFormat:@"draw-%u", step];
        Cursor before = state(enc, queueCpp, dir, [label stringByAppendingString:@"-before"]);
        if (step < 4) [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        else [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt16
            indexBuffer:indices indexBufferOffset:64 instanceCount:step == 4 ? 1 : 2];
        Cursor after = state(enc, queueCpp, dir, [label stringByAppendingString:@"-after"]);
        BOOL comparable = before.push && before.push == after.push && before.end == after.end &&
            after.current >= before.current && after.current <= before.end && after.current - before.current <= 65536;
        NSData *delta = comparable && after.current > before.current ? readMemory(before.current, after.current - before.current) : nil;
        NSDictionary *saved = save(delta, dir, [label stringByAppendingString:@".commands.bin"]);
        [records addObject:@{@"step":@(step), @"indexed":@(step >= 4),
            @"instances":@(step == 5 ? 2 : 1), @"vertex_function":step >= 2 ? @"vs_half" : @"vs_state",
            @"before":cursorInfo(before), @"after":cursorInfo(after), @"range_comparable":@(comparable), @"command_capture":saved}];
    }
    [enc endEncoding];
    NSDictionary *result = @{@"device":device.name, @"registry_id":@(device.registryID),
        @"driver_SHA256":sha(driver), @"library_SHA256":sha(bytes), @"encoder_layout":encoderLayout,
        @"queue_layout":queueLayout, @"methods":methods, @"records":records,
        @"index_buffer_GPU_address":@(indices.gpuAddress), @"index_buffer_offset":@64,
        @"committed":@NO, @"GPU_user_submissions":@0, @"native_memory_modified":@NO, @"system_modified":@NO,
        @"scope":@"Passive own-process render packets; no replay, no ICB implementation or GPU qualification"};
    NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(json.bytes, 1, json.length, stdout); puts(""); return 0;
} }
