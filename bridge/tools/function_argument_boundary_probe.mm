#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]),*mode=@(argv[3]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 NSMutableDictionary*r=[@{@"mode":mode,@"stage":@"library",@"GPU_dispatch":@NO,@"committed":@NO}mutableCopy];
 @try{
  NSError*e=nil;NSData*data=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"producer.metallib"]];dispatch_data_t bytes=dispatch_data_create(data.bytes,data.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)data.length;});id<MTLLibrary>lib=[d newLibraryWithData:bytes error:&e];r[@"library_created"]=@(lib!=nil);
  if(!lib){r[@"status"]=@"NIL_LIBRARY";r[@"error"]=e.description?:@"";}
  else{r[@"library_class"]=NSStringFromClass(object_getClass(lib));r[@"stage"]=@"function";id<MTLFunction>f=[lib newFunctionWithName:@"encode_dataflow_basic"];r[@"function_created"]=@(f!=nil);
   if(!f)r[@"status"]=@"NIL_FUNCTION";
   else{r[@"function_class"]=NSStringFromClass(object_getClass(f));r[@"function_name"]=f.name;
    if([mode isEqual:@"encoder"]){r[@"stage"]=@"function_argument_encoder";id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0];r[@"encoder_created"]=@(ae!=nil);if(ae){r[@"encoder_class"]=NSStringFromClass(object_getClass(ae));r[@"encoded_length"]=@(ae.encodedLength);r[@"alignment"]=@(ae.alignment);}r[@"status"]=@"OBSERVED_CPU_ONLY";}
    else if([mode isEqual:@"pipeline"]){r[@"stage"]=@"native_pipeline";id<MTLComputePipelineState>p=[d newComputePipelineStateWithFunction:f error:&e];r[@"pipeline_created"]=@(p!=nil);r[@"error"]=e.description?:@"";if(p){r[@"pipeline_class"]=NSStringFromClass(object_getClass(p));r[@"thread_execution_width"]=@(p.threadExecutionWidth);}r[@"status"]=@"OBSERVED_CPU_ONLY";}
    else return 1;
   }
  }
 }@catch(NSException*x){r[@"status"]=@"EXCEPTION";r[@"exception_name"]=x.name;r[@"exception_reason"]=x.reason?:@"";}
 NSDictionary*result=@{@"device":d.name,@"registry_id":@(d.registryID),@"mode":mode,@"runs":@[r],@"system_modified":@NO,@"GPU_execution":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
