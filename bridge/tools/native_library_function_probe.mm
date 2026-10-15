// SPDX-License-Identifier: MIT
// Native library/function factories only; no pipeline or command submission.
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstdio>
#include <pthread.h>
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d)return 2;NSMutableArray*runs=[NSMutableArray new];
 for(NSArray*pair in @[@[@"producer.metallib",@"encode_dataflow_basic"],@[@"consumer.metallib",@"dependency_seed"]]){
  NSError*loadError=nil;id<MTLLibrary>library=[d newLibraryWithURL:[NSURL fileURLWithPath:[@(argv[1])stringByAppendingPathComponent:pair[0]]]error:&loadError];if(!library)return 3;
  for(unsigned kind=0;kind<10;kind++){
   NSError*error=nil;id<MTLFunction>f=nil;NSString*exception=nil;NSUInteger callbacks=0;BOOL offThread=NO;
   MTLFunctionConstantValues*c=[MTLFunctionConstantValues new];if(kind==3){uint32_t value=123;[c setConstantValue:&value type:MTLDataTypeUInt atIndex:0];}
   MTLFunctionDescriptor*p=[MTLFunctionDescriptor functionDescriptor];p.name=pair[1];if(kind==5)p.constantValues=c;if(kind==6)p.specializedName=@"probe_alias";if(kind==7)p.options=MTLFunctionOptionCompileToBinary;
   @try{
    if(kind==0)f=[library newFunctionWithName:pair[1]];
    else if(kind<4)f=[library newFunctionWithName:pair[1]constantValues:kind==1?nil:c error:&error];
    else if(kind<8)f=[library newFunctionWithDescriptor:p error:&error];
    else{
     __block id<MTLFunction>reply=nil;__block NSError*failure=nil;__block NSUInteger count=0;__block BOOL other=NO;pthread_t caller=pthread_self();NSLock*lock=[NSLock new];dispatch_semaphore_t sem=dispatch_semaphore_create(0);
     void(^complete)(id<MTLFunction>,NSError*)=^(id<MTLFunction>x,NSError*y){[lock lock];reply=x;failure=y;count++;other=!pthread_equal(caller,pthread_self());[lock unlock];dispatch_semaphore_signal(sem);};
     if(kind==8)[library newFunctionWithName:pair[1]constantValues:c completionHandler:complete];else[library newFunctionWithDescriptor:p completionHandler:complete];
     if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return 4;[lock lock];f=reply;error=failure;callbacks=count;offThread=other;[lock unlock];
    }
   }@catch(NSException*x){exception=x.reason?:x.name;}
   [runs addObject:@{@"library":pair[0],@"library_class":NSStringFromClass(object_getClass(library)),@"library_instance_bytes":@(class_getInstanceSize(object_getClass(library))),@"requested":pair[1],@"kind":@(kind),@"created":@(f!=nil),@"name":f.name?:@"",@"function_class":f?NSStringFromClass(object_getClass(f)):@"",@"function_instance_bytes":@(f?class_getInstanceSize(object_getClass(f)):0),@"constants_dictionary_available":@(f&&[f respondsToSelector:@selector(functionConstantsDictionary)]),@"function_constants":@(f&&[f respondsToSelector:@selector(functionConstantsDictionary)]?f.functionConstantsDictionary.count:0),@"function_type":@(f?f.functionType:0),@"callbacks":@(callbacks),@"off_thread":@(offThread),@"error":error.description?:@"",@"exception":exception?:@""}];
  }
 }
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"runs":runs,@"experimental_runtime":@NO,@"user_GPU_command_buffers":@0,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
