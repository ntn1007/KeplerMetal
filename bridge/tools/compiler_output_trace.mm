// Observe the installed driver's legitimate constructor in this process only.
// Preserve all arguments and the original return value. No GPU program patched.
// Compiled without ARC to preserve the init method's original ownership ABI.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <cstdio>
#include <cstring>

static IMP originalInit;
static NSString *destination;
static NSMutableArray *captures;
static unsigned serial;
static id observedInit(id self,SEL selector,const void *bytes,NSUInteger length,id device) {
    NSString *stem=[NSString stringWithFormat:@"program-%u",serial++];
    NSString *path=[destination stringByAppendingPathComponent:[stem stringByAppendingString:@".compiler-output.bin"]];
    NSMutableDictionary *record=[NSMutableDictionary dictionaryWithDictionary:@{
        @"class":@(class_getName(object_getClass(self))),@"input_bytes":@(length),@"file":path,
        @"scope":@"unmodified compiler output used by our own pipeline creation"}];
    if(bytes && length && length<=8*1024*1024){
        FILE *file=fopen(path.fileSystemRepresentation,"wb");
        if(file){size_t written=fwrite(bytes,1,length,file);int closed=fclose(file);record[@"saved"]=@(written==length && !closed);}
    }
    id result=((id(*)(id,SEL,const void*,NSUInteger,id))originalInit)(self,selector,bytes,length,device);
    if(result){
        Ivar ivar=class_getInstanceVariable(object_getClass(result),"_variant");
        if(ivar){
            const char *encoding=ivar_getTypeEncoding(ivar);uintptr_t pointer=0;
            memcpy(&pointer,(const char*)result+ivar_getOffset(ivar),sizeof(pointer));
            record[@"variant_encoding"]=@(encoding);record[@"variant_pointer"]=@(pointer);
            @try {
                NSUInteger size=0,alignment=0;
                if(encoding[0]=='^')NSGetSizeAndAlignment(encoding+1,&size,&alignment);
                record[@"variant_bytes"]=@(size);record[@"variant_alignment"]=@(alignment);
                if(pointer && size && size<=64*1024){
                    NSMutableData *data=[NSMutableData dataWithLength:size];mach_vm_size_t read=0;
                    kern_return_t status=mach_vm_read_overwrite(mach_task_self(),pointer,size,(mach_vm_address_t)data.mutableBytes,&read);
                    record[@"read_status"]=@(status);
                    if(status==KERN_SUCCESS && read==size){
                        NSString *variantPath=[destination stringByAppendingPathComponent:[stem stringByAppendingString:@".variant.bin"]];
                        record[@"variant_file"]=variantPath;record[@"variant_saved"]=@([data writeToFile:variantPath atomically:YES]);
                    }
                }
            } @catch(NSException *exception){record[@"layout_error"]=exception.reason ?: exception.name;}
        }
    }
    [captures addObject:record];return result;
}
int main(int argc,char **argv){@autoreleasepool{
    if(argc<3||argc>5)return 1;bool tessellation=argc>=4&&!strcmp(argv[3],"tessellation"),vertexIO=argc>=4&&!strcmp(argv[3],"vertex-io"),stencil=argc>=4&&!strcmp(argv[3],"stencil"),state=argc>=4&&!strcmp(argv[3],"render-state"),render=tessellation||vertexIO||stencil||state||(argc>=4&&!strcmp(argv[3],"render"));destination=@(argv[2]);captures=[NSMutableArray array];
    [[NSFileManager defaultManager] createDirectoryAtPath:destination withIntermediateDirectories:YES attributes:nil error:nil];
    id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 2;
    Class cls=objc_getClass("NVMTLFunctionVariant");SEL selector=sel_registerName("initWithCompilerOutput:size:device:");
    Method method=class_getInstanceMethod(cls,selector);
    if(!method||strcmp(method_getTypeEncoding(method),"@40@0:8r^v16Q24@32")){fprintf(stderr,"Unexpected constructor ABI\n");return 3;}
    originalInit=method_setImplementation(method,(IMP)observedInit);
    NSError *error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
    id pipeline=nil;
    if(library){if(render){
        MTLRenderPipelineDescriptor*descriptor=[MTLRenderPipelineDescriptor new];
        descriptor.vertexFunction=[library newFunctionWithName:stencil?@"vs_half":(state?@"vs_state":@"vs_ref")];
        descriptor.fragmentFunction=stencil?nil:[library newFunctionWithName:argc==5?@(argv[4]):(state?@"fs_state":@"fs_const")];
        descriptor.colorAttachments[0].pixelFormat=stencil||state?MTLPixelFormatRGBA32Float:MTLPixelFormatRGBA8Unorm;
        if(tessellation){bool capture=argc==5&&!strcmp(argv[4],"capture");descriptor.vertexFunction=[library newFunctionWithName:capture?@"tess_capture":@"tess_triangle"];descriptor.fragmentFunction=capture?nil:[library newFunctionWithName:@"tess_fragment"];descriptor.rasterizationEnabled=!capture;descriptor.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;descriptor.maxTessellationFactor=64;descriptor.tessellationPartitionMode=MTLTessellationPartitionModeInteger;descriptor.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionConstant;descriptor.tessellationOutputWindingOrder=MTLWindingCounterClockwise;}
        if(vertexIO){
            NSString*mode=argc==5?@(argv[4]):@"smooth";
            descriptor.vertexFunction=[library newFunctionWithName:[@"vs_io_" stringByAppendingString:mode]];
            descriptor.fragmentFunction=[library newFunctionWithName:[@"fs_io_" stringByAppendingString:mode]];
            descriptor.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
            MTLVertexDescriptor*input=[MTLVertexDescriptor vertexDescriptor];
            for(unsigned i=0;i<3;i++){input.attributes[i].format=MTLVertexFormatFloat4;input.attributes[i].offset=i==1?16:0;input.attributes[i].bufferIndex=i==2?1:0;}
            input.layouts[0].stride=32;input.layouts[0].stepFunction=MTLVertexStepFunctionPerVertex;
            input.layouts[1].stride=16;input.layouts[1].stepFunction=MTLVertexStepFunctionPerInstance;
            descriptor.vertexDescriptor=input;
        }
        if(stencil){descriptor.colorAttachments[0].writeMask=MTLColorWriteMaskNone;descriptor.depthAttachmentPixelFormat=descriptor.stencilAttachmentPixelFormat=MTLPixelFormatDepth32Float_Stencil8;}
        pipeline=[device newRenderPipelineStateWithDescriptor:descriptor error:&error];}
      else pipeline=[device newComputePipelineStateWithFunction:[library newFunctionWithName:argc==5&&!strcmp(argv[3],"compute")?@(argv[4]):@"add_buffers"] error:&error];}
    method_setImplementation(method,originalInit);
    NSDictionary *result=@{@"device":device.name,@"pipeline_created":@(pipeline!=nil),@"captures":captures,
                           @"error":error.description ?: @"",@"gpu_dispatch":@NO,
                           @"scope":@"temporary observation inside own process; original constructor inputs/outputs unchanged"};
    NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    if(json)fwrite(json.bytes,1,json.length,stdout);putchar('\n');return pipeline?0:4;
}}
