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
 if(argc!=3&&argc!=4)return 1;BOOL execute=argc==4&&[@(argv[3])isEqual:@"execute"];NSString*dir=@(argv[2]);NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];if(![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;
 NSData*bytes=[NSData dataWithContentsOfFile:@(argv[1])];id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 3;NSError*error=nil;dispatch_data_t payload=dispatch_data_create(bytes.bytes,bytes.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)bytes.length;});id<MTLLibrary>lib=[d newLibraryWithData:payload error:&error];if(!lib)return 4;
 id<MTLCommandQueue>q=[d newCommandQueue];uintptr_t queue=pointerIvar(q,"_queue");NSMutableArray*rows=[NSMutableArray new];
 for(NSString*name in @[@"fs_arg_read",@"fs_arg_nearest",@"fs_arg_linear"]){
  id<MTLFunction>f=[lib newFunctionWithName:name];MTLRenderPipelineDescriptor*p=[MTLRenderPipelineDescriptor new];p.vertexFunction=[lib newFunctionWithName:@"vs_ref"];p.fragmentFunction=f;p.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;MTLRenderPipelineReflection*reflection=nil;id<MTLRenderPipelineState>pipeline=[d newRenderPipelineStateWithDescriptor:p options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:&error];if(!pipeline){fprintf(stderr,"%s\n",error.description.UTF8String);return 5;}
  NSMutableArray*arguments=[NSMutableArray new];for(MTLArgument*a in reflection.fragmentArguments){NSMutableArray*members=[NSMutableArray new];for(MTLStructMember*m in a.bufferStructType.members){NSMutableDictionary*item=[@{@"name":m.name,@"offset":@(m.offset),@"data_type":@(m.dataType),@"argument_index":@(m.argumentIndex)}mutableCopy];if(m.dataType==MTLDataTypePointer){MTLPointerType*t=m.pointerType;item[@"pointer"]=@{@"data_type":@(t.elementType),@"access":@(t.access),@"data_size":@(t.dataSize),@"alignment":@(t.alignment),@"element_is_argument_buffer":@(t.elementIsArgumentBuffer)};}else if(m.dataType==MTLDataTypeTexture){MTLTextureReferenceType*t=m.textureReferenceType;item[@"texture"]=@{@"texture_type":@(t.textureType),@"data_type":@(t.textureDataType),@"access":@(t.access)};}[members addObject:item];}[arguments addObject:@{@"name":a.name,@"index":@(a.index),@"type":@(a.type),@"active":@(a.active),@"access":@(a.access),@"data_type":@(a.bufferDataType),@"data_size":@(a.bufferDataSize),@"alignment":@(a.bufferAlignment),@"members":members}];}
  id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0];if(!ae)return 6;id<MTLBuffer>ab=[d newBufferWithLength:ae.encodedLength+512 options:MTLResourceStorageModeShared],params=[d newBufferWithLength:512 options:MTLResourceStorageModeShared];if(!ab||!params)return 7;memset(ab.contents,0xa5,ab.length);memset(params.contents,0xa5,512);float values[8]={1,1,1,1,0,0,0,0};memcpy((char*)params.contents+256,values,32);
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:64 height:48 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget;id<MTLTexture>input=[d newTextureWithDescriptor:td],target=[d newTextureWithDescriptor:td];MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];sd.minFilter=[name isEqual:@"fs_arg_linear"]?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;sd.magFilter=sd.minFilter;sd.sAddressMode=sd.tAddressMode=MTLSamplerAddressModeClampToEdge;sd.supportArgumentBuffers=YES;id<MTLSamplerState>sampler=[d newSamplerStateWithDescriptor:sd];if(!input||!target||!sampler)return 8;
  [ae setArgumentBuffer:ab offset:256];[ae setTexture:input atIndex:0];[ae setSamplerState:sampler atIndex:1];[ae setBuffer:params offset:256 atIndex:2];save([NSData dataWithBytes:ab.contents length:ab.length],dir,[name stringByAppendingString:@".argument-buffer.bin"]);
  id<MTLCommandBuffer>cb=[q commandBuffer];
  NSMutableData*texels=[NSMutableData dataWithLength:49152];for(NSUInteger y=0;y<48;y++)for(NSUInteger x=0;x<64;x++){float v[4]={float((x*3+y*5)&63)/64,float((x*7+y*11)&63)/64,float((x^y)&31)/32,1};memcpy((char*)texels.mutableBytes+(y*64+x)*16,v,16);}save(texels,dir,[name stringByAppendingString:@".texture-input.bin"]);id<MTLBuffer>stage=[d newBufferWithBytes:texels.bytes length:texels.length options:MTLResourceStorageModeShared];id<MTLBlitCommandEncoder>upload=[cb blitCommandEncoder];[upload copyFromBuffer:stage sourceOffset:0 sourceBytesPerRow:1024 sourceBytesPerImage:49152 sourceSize:MTLSizeMake(64,48,1) toTexture:input destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];[upload endEncoding];
  MTLRenderPassDescriptor*pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=target;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:pass];[e setRenderPipelineState:pipeline];[e setFragmentBuffer:ab offset:256 atIndex:0];[e useResource:input usage:MTLResourceUsageRead stages:MTLRenderStageFragment];[e useResource:params usage:MTLResourceUsageRead stages:MTLRenderStageFragment];NSMutableArray*records=[NSMutableArray new];
  for(NSUInteger j=0;j<3;j++){NSString*label=[NSString stringWithFormat:@"%@-%lu",name,(unsigned long)j];Cursor before=state(e,queue,dir,[label stringByAppendingString:@"-before"]);[e drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:j==2?1:3];Cursor after=state(e,queue,dir,[label stringByAppendingString:@"-after"]);BOOL comparable=before.push&&before.push==after.push&&before.end==after.end&&after.current>=before.current&&after.current<=before.end;NSData*raw=comparable?readMemory(before.current,after.current-before.current):nil;[records addObject:@{@"vertex_count":@(j==2?1:3),@"comparable":@(comparable),@"commands":save(raw,dir,[label stringByAppendingString:@".commands.bin"])}];}
  [e endEncoding];id<MTLBuffer>readback=[d newBufferWithLength:49664 options:MTLResourceStorageModeShared];memset(readback.contents,0xa5,49664);id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];[blit copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:readback destinationOffset:256 destinationBytesPerRow:1024 destinationBytesPerImage:49152];[blit endEncoding];if(execute){[cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return 9;}save([NSData dataWithBytes:readback.contents length:49664],dir,[name stringByAppendingString:@".image.bin"]);[rows addObject:@{@"command_status":@(cb.status),@"name":name,@"fragment_arguments":arguments,@"vertex_argument_count":@(reflection.vertexArguments.count),@"encoded_length":@(ae.encodedLength),@"encoded_alignment":@(ae.alignment),@"argument_encoder_class":NSStringFromClass(object_getClass(ae)),@"records":records}];
 }
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"driver_SHA256":sha(driver),@"library_SHA256":sha(bytes),@"rows":rows,@"GPU_user_submissions":@(execute?3:0),@"committed":@(execute),@"native_memory_modified":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
