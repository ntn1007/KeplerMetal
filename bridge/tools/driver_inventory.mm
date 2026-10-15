// Introspect objects in our own process. No private methods are invoked.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <cstring>
#include <cstdio>

static NSDictionary *location(const void *address) {
    Dl_info info = {};
    if (!dladdr(address, &info)) return @{};
    return @{ @"image": info.dli_fname ? @(info.dli_fname) : @"",
              @"offset_from_image_base": @((uintptr_t)address-(uintptr_t)info.dli_fbase) };
}
static NSDictionary *classInfo(Class cls) {
    unsigned count=0; Method *methods=class_copyMethodList(cls,&count);
    NSMutableArray *methodInfo=[NSMutableArray array];
    for(unsigned i=0;i<count;i++)
        [methodInfo addObject:@{@"selector":@(sel_getName(method_getName(methods[i]))),
                                @"encoding":@(method_getTypeEncoding(methods[i])),
                                @"implementation":location((const void*)method_getImplementation(methods[i]))}];
    free(methods);Ivar*ivars=class_copyIvarList(cls,&count);
    NSMutableArray *ivarInfo=[NSMutableArray array];
    for(unsigned i=0;i<count;i++)
        [ivarInfo addObject:@{@"name":@(ivar_getName(ivars[i])),@"encoding":@(ivar_getTypeEncoding(ivars[i])),
                             @"offset":@(ivar_getOffset(ivars[i]))}];
    free(ivars);
    return @{@"name":@(class_getName(cls)),@"image":class_getImageName(cls)?@(class_getImageName(cls)):@"",
             @"instance_bytes":@(class_getInstanceSize(cls)),@"methods":methodInfo,@"ivars":ivarInfo};
}
static NSDictionary *objectInfo(id object) {
    if(!object)return @{};
    Class actual=object_getClass(object);size_t bytes=class_getInstanceSize(actual);
    const unsigned char *raw=(const unsigned char*)(__bridge const void*)object;
    NSMutableArray *ivarsOut=[NSMutableArray array];
    for(Class cls=actual;cls;cls=class_getSuperclass(cls)) {
        unsigned count=0;Ivar*ivars=class_copyIvarList(cls,&count);
        for(unsigned i=0;i<count;i++){
            ptrdiff_t offset=ivar_getOffset(ivars[i]);uint64_t value=0;
            if(offset<0||(size_t)offset>=bytes)continue;
            memcpy(&value,raw+offset,MIN(size_t(8),bytes-size_t(offset)));
            NSMutableDictionary *row=[@{@"owner":@(class_getName(cls)),@"name":@(ivar_getName(ivars[i])),
                @"encoding":@(ivar_getTypeEncoding(ivars[i])),@"offset":@(offset),@"raw_u64":@(value)} mutableCopy];
            if(ivar_getTypeEncoding(ivars[i])[0]=='@'){
                id child=object_getIvar(object,ivars[i]);
                if(child)row[@"object_class"]=@(class_getName(object_getClass(child)));
            }
            [ivarsOut addObject:row];
        }
        free(ivars);
    }
    return @{@"class":@(class_getName(actual)),@"ivars":ivarsOut};
}
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=2)return 1;
    fprintf(stderr,"phase device\n");fflush(stderr);
    id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
    NSError*error=nil;id<MTLLibrary>lib=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
    if(!lib){fprintf(stderr,"%s\n",error.description.UTF8String);return 3;}
    id<MTLFunction>function=[lib newFunctionWithName:@"add_buffers"];
    fprintf(stderr,"phase pipeline\n");fflush(stderr);
    id<MTLComputePipelineState>pipeline=[device newComputePipelineStateWithFunction:function error:&error];
    if(!pipeline)return 4;
    id<MTLBuffer>buffer=[device newBufferWithLength:4096 options:MTLResourceStorageModeShared];
    id<MTLCommandQueue>queue=[device newCommandQueue];
    fprintf(stderr,"phase classes\n");fflush(stderr);
    NSMutableArray *classes=[NSMutableArray array];unsigned count=0;Class *all=objc_copyClassList(&count);
    for(unsigned i=0;i<count;i++){
        const char*name=class_getName(all[i]);const char*image=class_getImageName(all[i]);
        if((image&&strstr(image,"GeForceMTLDriver"))||strncmp(name,"MTLIOAccel",10)==0)
            [classes addObject:classInfo(all[i])];
    }
    free(all);
    fprintf(stderr,"phase buffer ivars\n");fflush(stderr);
    NSMutableDictionary*bufferInfo=[objectInfo(buffer) mutableCopy];
    bufferInfo[@"responds_gpuAddress"]=@([buffer respondsToSelector:@selector(gpuAddress)]);
    if([buffer respondsToSelector:@selector(gpuAddress)]){
      @try { bufferInfo[@"public_gpu_address"]=@(buffer.gpuAddress); }
      @catch(NSException*exception){bufferInfo[@"gpu_address_error"]=exception.reason ?: exception.name;}
    }
    fprintf(stderr,"phase other object ivars\n");fflush(stderr);
    NSDictionary *result=@{@"device":device.name,@"classes":classes,
       @"objects":@{@"device":objectInfo(device),@"function":objectInfo(function),@"pipeline":objectInfo(pipeline),
                     @"buffer":bufferInfo,@"queue":objectInfo(queue)},
       @"scope":@"read-only introspection of our own installed-driver objects, no private invocation or GPU packet"};
    NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&error];
    if(!json)return 5;fwrite(json.bytes,1,json.length,stdout);putchar('\n');return 0;
}}
