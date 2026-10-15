// Runtime method ownership/ABI inventory only. No ICB created or dispatched.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <mach-o/loader.h>
#include <cstdio>
static NSDictionary*methodInfo(id object,NSString*name){
 SEL selector=NSSelectorFromString(name);Class owner=nil;
 for(Class c=object_getClass(object);c&&!owner;c=class_getSuperclass(c)){
  unsigned n=0;Method*methods=class_copyMethodList(c,&n);
  for(unsigned i=0;i<n;i++)if(method_getName(methods[i])==selector){owner=c;break;}free(methods);
 }
 NSMutableDictionary*r=[@{@"object_class":NSStringFromClass(object_getClass(object)),@"selector":name,
                         @"responds":@([object respondsToSelector:selector]),@"defining_class":owner?NSStringFromClass(owner):@""}mutableCopy];
 if(owner){Method m=class_getInstanceMethod(owner,selector);IMP imp=method_getImplementation(m);Dl_info info={};r[@"encoding"]=@(method_getTypeEncoding(m));
  if(dladdr((void*)imp,&info)){r[@"image"]=info.dli_fname?@(info.dli_fname):@"";r[@"image_offset"]=[NSString stringWithFormat:@"0x%llx",(unsigned long long)((uintptr_t)imp-(uintptr_t)info.dli_fbase)];
   const mach_header_64*h=(const mach_header_64*)info.dli_fbase;if(h->magic==MH_MAGIC_64){const uint8_t*p=(const uint8_t*)(h+1);
    for(unsigned i=0;i<h->ncmds;i++){const load_command*lc=(const load_command*)p;if(lc->cmd==LC_UUID){const uuid_command*u=(const uuid_command*)p;NSMutableString*s=[NSMutableString new];for(unsigned j=0;j<16;j++)[s appendFormat:@"%02x",u->uuid[j]];r[@"image_UUID"]=s;}if(lc->cmdsize<sizeof(load_command))break;p+=lc->cmdsize;}
   }
  }
 }return r;
}
int main(){@autoreleasepool{
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 NSMutableArray*rows=[NSMutableArray new];
 for(NSString*s in @[@"newIndirectCommandBufferWithDescriptor:maxCommandCount:options:",@"newIndirectCommandBufferWithDescriptor:maxCount:options:",@"supportsIndirectCommandBuffers",@"newHeapWithDescriptor:"])[rows addObject:methodInfo(d,s)];
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>compute=[cb computeCommandEncoder];
 for(NSString*s in @[@"executeCommandsInBuffer:withRange:",@"executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:",@"useResource:usage:",@"dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:threadsPerThreadgroup:"])[rows addObject:methodInfo(compute,s)];[compute endEncoding];
 id<MTLBlitCommandEncoder>blit=[cb blitCommandEncoder];for(NSString*s in @[@"resetCommandsInBuffer:withRange:",@"optimizeIndirectCommandBuffer:withRange:",@"copyIndirectCommandBuffer:sourceRange:destination:destinationIndex:"])[rows addObject:methodInfo(blit,s)];[blit endEncoding];
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"methods":rows,@"GPU_dispatch":@NO,@"ICB_created":@NO,@"scope":@"Selectors/IMP image UUID and offset; presence is not working execution; no replacement or global patch"};
 NSData*b=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");return 0;
}}
