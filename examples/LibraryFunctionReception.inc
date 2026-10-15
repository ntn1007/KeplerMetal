// SPDX-License-Identifier: MIT
// Ordinary library/function selection, shared by GTX and native M1 clients.
static NSUInteger receptionLibraryKind=0,receptionFunctionKind=0;
static NSDictionary*receptionFunctionEvidence=nil;
static id<MTLLibrary>receptionLoadLibrary(id<MTLDevice>device,NSString*path,NSError**error){
 if(receptionLibraryKind==0){NSData*bytes=[NSData dataWithContentsOfFile:path];dispatch_data_t data=dispatch_data_create(bytes.bytes,bytes.length,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{(void)bytes.length;});return[device newLibraryWithData:data error:error];}
 if(receptionLibraryKind==1)return[device newLibraryWithURL:[NSURL fileURLWithPath:path]error:error];return[device newLibraryWithFile:path error:error];
}
static id<MTLFunction>receptionLibraryFunction(id<MTLLibrary>library,NSString*name,NSError**error){
 id<MTLFunction>function=nil;MTLFunctionConstantValues*values=[MTLFunctionConstantValues new];if(receptionFunctionKind==3){uint32_t value=123;[values setConstantValue:&value type:MTLDataTypeUInt atIndex:0];}
 MTLFunctionDescriptor*p=[MTLFunctionDescriptor functionDescriptor];p.name=name;if(receptionFunctionKind==5)p.constantValues=values;if(receptionFunctionKind==6)p.specializedName=[@"alias_" stringByAppendingString:name];NSUInteger callbacks=0;
 if(receptionFunctionKind==0)function=[library newFunctionWithName:name];
 else if(receptionFunctionKind<4)function=[library newFunctionWithName:name constantValues:receptionFunctionKind==1?nil:values error:error];
 else if(receptionFunctionKind<7)function=[library newFunctionWithDescriptor:p error:error];
 else{NSLock*lock=[NSLock new];__block id<MTLFunction>reply=nil;__block NSError*failure=nil;__block NSUInteger count=0;dispatch_semaphore_t sem=dispatch_semaphore_create(0);void(^complete)(id<MTLFunction>,NSError*)=^(id<MTLFunction>x,NSError*y){[lock lock];reply=x;failure=y;count++;[lock unlock];dispatch_semaphore_signal(sem);};if(receptionFunctionKind==7)[library newFunctionWithName:name constantValues:values completionHandler:complete];else[library newFunctionWithDescriptor:p completionHandler:complete];p.name=@"mutated-after-request";if(dispatch_semaphore_wait(sem,dispatch_time(DISPATCH_TIME_NOW,10*NSEC_PER_SEC)))return nil;[lock lock];function=reply;if(error)*error=failure;callbacks=count;[lock unlock];if(callbacks!=1)return nil;}
 if(function&&![function.name isEqual:receptionFunctionKind==6?[@"alias_" stringByAppendingString:name]:name])return nil;
 receptionFunctionEvidence=@{@"library_factory":@(receptionLibraryKind),@"function_factory":@(receptionFunctionKind),@"callbacks":@(callbacks),@"source_name":name,@"returned_name":function.name?:@"",@"function_constants":@(function?function.functionConstantsDictionary.count:0)};return function;
}
#if !KP_DATAFLOW_NATIVE
static BOOL receptionRegisterLibrary(KPCPUICBScope*scope,NSString*assets,NSError**error){
 NSData*source=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"producer.metallib"]],*carrier=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"carrier.metallib"]];NSMutableDictionary*programs=[NSMutableDictionary new];for(NSString*name in @[@"basic",@"barrier",@"copy",@"no_seed",@"no_gather",@"no_finish"])programs[[@"encode_dataflow_" stringByAppendingString:name]]=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".sass"]]];
 NSString*pin=@"a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db";
 for(unsigned kind=0;kind<3;kind++){NSMutableData*badSource=[source mutableCopy],*badCarrier=[carrier mutableCopy];NSMutableDictionary*badPrograms=[programs mutableCopy];if(kind==0)((uint8_t*)badSource.mutableBytes)[0]^=1;else if(kind==1)((uint8_t*)badCarrier.mutableBytes)[0]^=1;else{NSMutableData*code=[programs[@"encode_dataflow_basic"]mutableCopy];((uint8_t*)code.mutableBytes)[0]^=1;badPrograms[@"encode_dataflow_basic"]=code;}NSError*failure=nil;NSUInteger before=scope.events.count;if([scope registerCommandIRLibraryData:badSource expectedSHA256:pin carrierData:badCarrier programsByFunction:badPrograms error:&failure]||!failure||scope.events.count!=before)return NO;}
 if(![scope registerCommandIRLibraryData:source expectedSHA256:pin carrierData:carrier programsByFunction:programs error:error])return NO;NSError*duplicate=nil;if([scope registerCommandIRLibraryData:source expectedSHA256:pin carrierData:carrier programsByFunction:programs error:&duplicate]||!duplicate)return NO;return YES;
}
#endif
