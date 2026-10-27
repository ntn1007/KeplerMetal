// Experimental standalone client, using public Metal and Foundation only.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
extern "C" NSDictionary *ordinary_metal_render(id<MTLDevice>,id<MTLCommandQueue>,id<MTLRenderPipelineState>,NSString*,NSString*);
int main(int argc,char **argv){@autoreleasepool{@try{
 if(argc!=4)return 2;NSString *libraryPath=@(argv[1]),*output=@(argv[2]),*mode=@(argv[3]);
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d){fprintf(stderr,"no device\n");return 3;}
 id<MTLCommandQueue>q=[d newCommandQueue];NSError*error=nil;
 id<MTLLibrary>lib=[d newLibraryWithFile:libraryPath error:&error];if(!lib){fprintf(stderr,"library %s\n",error.description.UTF8String);return 4;}
 MTLRenderPipelineDescriptor*p=[MTLRenderPipelineDescriptor new];p.vertexFunction=[lib newFunctionWithName:@"vs_state"];p.fragmentFunction=[lib newFunctionWithName:@"fs_state"];p.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA32Float;
 id<MTLRenderPipelineState>pipeline=[d newRenderPipelineStateWithDescriptor:p error:&error];if(!pipeline){fprintf(stderr,"pipeline %s\n",error.description.UTF8String);return 5;}
 NSDictionary*result=ordinary_metal_render(d,q,pipeline,output,mode);
 NSDictionary*report=@{@"device":d.name?:@"",@"registry_id":@(d.registryID),@"device_class":NSStringFromClass(object_getClass(d)),@"queue_class":NSStringFromClass(object_getClass(q)),@"client":result};
 NSData*data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];if(!data)return 6;fwrite(data.bytes,1,data.length,stdout);puts("");return [result[@"status"]isEqual:@"PASS"]?0:7;
 }@catch(NSException*e){fprintf(stderr,"exception %s: %s\n",e.name.UTF8String,e.reason.UTF8String);return 8;}}}
