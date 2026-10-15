// Read-only layouts in our process. Never commit a command buffer or call a private method.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <mach/mach_vm.h>
#include <cstring>
#include <cstdio>
static NSDictionary *method(Class c,NSString *name){
 Method m=class_getInstanceMethod(c,NSSelectorFromString(name));if(!m)return @{@"selector":name,@"present":@NO};
 IMP imp=method_getImplementation(m);Dl_info info={};NSMutableDictionary*r=[@{@"selector":name,@"present":@YES,@"encoding":@(method_getTypeEncoding(m))}mutableCopy];
 if(dladdr((const void*)imp,&info)){r[@"image"]=@(info.dli_fname);r[@"image_offset"]=[NSString stringWithFormat:@"0x%llx",(unsigned long long)((uintptr_t)imp-(uintptr_t)info.dli_fbase)];}return r;
}
static NSDictionary *layout(id object,Class c,NSString *directory,NSString *name){
 NSMutableArray*rows=[NSMutableArray new];
 for(Class owner=c;owner&&owner!=[NSObject class];owner=class_getSuperclass(owner)){
  unsigned n=0;Ivar*vars=class_copyIvarList(owner,&n);
  for(unsigned i=0;i<n;i++){
   Ivar v=vars[i];const char*type=ivar_getTypeEncoding(v);ptrdiff_t off=ivar_getOffset(v);NSString*ivarName=@(ivar_getName(v));
   NSMutableDictionary*r=[@{@"name":ivarName,@"owner":NSStringFromClass(owner),@"offset":@(off),@"type":@(type)}mutableCopy];
   if(object&&off>=0&&(size_t)off+8<=class_getInstanceSize(c)&&type[0]=='^'){
    uintptr_t pointer=0;memcpy(&pointer,(const char*)(__bridge const void*)object+off,8);r[@"pointer"]=@(pointer);
    if(pointer){NSMutableData*prefix=[NSMutableData dataWithLength:256];mach_vm_size_t actual=0;kern_return_t status=mach_vm_read_overwrite(mach_task_self(),pointer,prefix.length,(mach_vm_address_t)prefix.mutableBytes,&actual);r[@"read_status"]=@(status);
     if(status==KERN_SUCCESS&&actual==prefix.length){NSString*p=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"%@-%@.prefix.bin",name,ivarName]];r[@"prefix_file"]=p;r[@"saved"]=@([prefix writeToFile:p atomically:YES]);}
    }
   }[rows addObject:r];
  }free(vars);
 }
 return @{@"class":NSStringFromClass(c),@"instance_bytes":@(class_getInstanceSize(c)),@"ivars":rows};
}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;NSString*dir=@(argv[1]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
 Class function=objc_getClass("NVMTLFunctionVariant");if(!function)return 3;
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"GPU_dispatch":@NO,@"committed":@NO,
  @"function":layout(nil,function,dir,@"function"),@"constructor":method(function,@"initWithCompilerOutput:size:device:"),
  @"encoder":layout(e,object_getClass(e),dir,@"encoder"),
  @"methods":@[method(object_getClass(e),@"dispatchThreadgroups:threadsPerThreadgroup:"),method(object_getClass(e),@"dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:threadsPerThreadgroup:")],
  @"scope":@"Loaded own-process objects and pointer prefixes read with mach_vm_read. No submission, private method invocation, mutation, or command-stream replay."};
 [e endEncoding];NSData*b=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");return 0;
}}
