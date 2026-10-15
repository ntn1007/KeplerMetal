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
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;NSString*dir=@(argv[2]);NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSData*bytes=[NSData dataWithContentsOfFile:@(argv[1])];if(![sha(bytes)isEqual:@"c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43"])return 3;
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 4;NSError*error=nil;
 dispatch_data_t payload=dispatch_data_create(bytes.bytes,bytes.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)bytes.length;});id<MTLLibrary>lib=[d newLibraryWithData:payload error:&error];if(!lib)return 5;
 MTLVertexDescriptor*vd=[MTLVertexDescriptor vertexDescriptor];for(unsigned i=0;i<3;i++){vd.attributes[i].format=MTLVertexFormatFloat4;vd.attributes[i].offset=i==1?16:0;vd.attributes[i].bufferIndex=i==2?1:0;}vd.layouts[0].stride=32;vd.layouts[0].stepFunction=MTLVertexStepFunctionPerVertex;vd.layouts[1].stride=16;vd.layouts[1].stepFunction=MTLVertexStepFunctionPerInstance;vd.layouts[1].stepRate=1;
 NSMutableArray *pipes = [NSMutableArray new], *reflections = [NSMutableArray new];
 for (NSString *mode in @[@"smooth", @"flat"]) {
  MTLRenderPipelineDescriptor *p = [MTLRenderPipelineDescriptor new];
  p.vertexFunction = [lib newFunctionWithName:[@"vs_io_" stringByAppendingString:mode]];
  p.fragmentFunction = [lib newFunctionWithName:[@"fs_io_" stringByAppendingString:mode]];
  p.vertexDescriptor = vd;
  p.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
  MTLRenderPipelineReflection *r = nil;
  id<MTLRenderPipelineState> s = [d newRenderPipelineStateWithDescriptor:p
    options:MTLPipelineOptionArgumentInfo | MTLPipelineOptionBufferTypeInfo
    reflection:&r error:&error];
  if (!s) return 6;
  [pipes addObject:s];
  NSMutableArray *args = [NSMutableArray new];
  NSArray *stages = @[r.vertexArguments ?: @[], r.fragmentArguments ?: @[]];
  for (NSUInteger stage = 0; stage < stages.count; ++stage) {
   for (MTLArgument *x in stages[stage]) {
    [args addObject:@{@"stage":stage == 0 ? @"vertex" : @"fragment",
      @"name":x.name, @"index":@(x.index), @"type":@(x.type),
      @"access":@(x.access), @"active":@(x.active)}];
   }
  }
  [reflections addObject:@{@"mode":mode, @"arguments":args}];
 }
 id<MTLBuffer>vertices=[d newBufferWithLength:4096 options:MTLResourceStorageModePrivate],offsets=[d newBufferWithLength:512 options:MTLResourceStorageModePrivate];MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;id<MTLTexture>target=[d newTextureWithDescriptor:td];if(!vertices||!offsets||!target)return 7;
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];MTLRenderPassDescriptor*p=[MTLRenderPassDescriptor renderPassDescriptor];p.colorAttachments[0].texture=target;p.colorAttachments[0].loadAction=MTLLoadActionClear;p.colorAttachments[0].storeAction=MTLStoreActionStore;id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:p];if(!e)return 8;uintptr_t queue=pointerIvar(q,"_queue");NSMutableArray*records=[NSMutableArray new];
 NSArray*names=@[@"set-pipeline-smooth",@"set-vertices",@"set-instances",@"draw-first",@"draw-repeat",@"rebind-vertices",@"draw-rebound",@"set-pipeline-flat",@"draw-flat",@"declare-vertex-resource"];
 for(NSUInteger step=0;step<names.count;step++){NSString*name=names[step];Cursor before=state(e,queue,dir,[name stringByAppendingString:@"-before"]);
 switch(step){case 0:[e setRenderPipelineState:pipes[0]];break;case 1:[e setVertexBuffer:vertices offset:64 atIndex:0];break;case 2:[e setVertexBuffer:offsets offset:128 atIndex:1];break;case 3:case 4:case 6:case 8:[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6 instanceCount:2];break;case 5:[e setVertexBuffer:vertices offset:96 atIndex:0];break;case 7:[e setRenderPipelineState:pipes[1]];break;case 9:if([e respondsToSelector:@selector(useResource:usage:stages:)])[e useResource:vertices usage:MTLResourceUsageRead stages:MTLRenderStageVertex];break;}
 Cursor after=state(e,queue,dir,[name stringByAppendingString:@"-after"]);BOOL comparable=before.push&&before.push==after.push&&before.end==after.end&&after.current>=before.current&&after.current<=before.end;NSData*raw=comparable&&after.current>before.current?readMemory(before.current,after.current-before.current):[NSData data];[records addObject:@{@"step":@(step),@"operation":name,@"before":cursorInfo(before),@"after":cursorInfo(after),@"comparable":@(comparable),@"commands":save(raw,dir,[name stringByAppendingString:@".commands.bin"])}];}
 NSMutableArray*methods=[NSMutableArray new];for(NSString*sel in @[@"setVertexBuffer:offset:atIndex:",@"setFragmentBuffer:offset:atIndex:",@"useResource:usage:stages:",@"useResource:usage:"])[methods addObject:methodInfo(e,sel)];[e endEncoding];NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":sha(driver),@"library_SHA256":sha(bytes),@"records":records,@"pipeline_reflections":reflections,@"methods":methods,@"vertices_GPU_address":@(vertices.gpuAddress),@"instances_GPU_address":@(offsets.gpuAddress),@"GPU_user_submissions":@0,@"committed":@NO,@"native_memory_modified":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
