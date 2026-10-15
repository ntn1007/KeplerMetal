// SPDX-License-Identifier: MIT
// Count only our own factory, never replace any Apple/NVIDIA class method.
static IMP libraryInputOriginal=nullptr;
static NSUInteger libraryInputImports=0;
static id<MTLComputePipelineState>countedLibraryInputFactory(id self,SEL sel,id<MTLDevice>d,NSData*carrier,NSData*program,NSError**error,NSDictionary**proof) NS_RETURNS_RETAINED;
static id<MTLComputePipelineState>countedLibraryInputFactory(id self,SEL sel,id<MTLDevice>d,NSData*carrier,NSData*program,NSError**error,NSDictionary**proof){libraryInputImports++;typedef id<MTLComputePipelineState>(*F)(id,SEL,id<MTLDevice>,NSData*,NSData*,NSError**,NSDictionary**)__attribute__((ns_returns_retained));return((F)libraryInputOriginal)(self,sel,d,carrier,program,error,proof);}
static BOOL registerLibraryInputsProbe(KPCPUICBScope*s,NSData*source,NSData*carrier,NSDictionary*programs,NSMutableArray*runs,NSError**error){
 Method method=class_getClassMethod(NSClassFromString(@"KPCommandIRProducerFactory"),@selector(newPipelineForDevice:carrier:program:error:evidence:));if(!method)return NO;libraryInputImports=0;libraryInputOriginal=method_setImplementation(method,(IMP)countedLibraryInputFactory);BOOL result=NO;NSString*pin=hash(source);
 @try{
  for(unsigned test=0;test<5;test++){
   NSMutableData*badSource=[source mutableCopy],*badCarrier=[carrier mutableCopy];NSMutableDictionary*bad=[programs mutableCopy];if(test==0)((uint8_t*)badSource.mutableBytes)[0]^=1;else if(test==1)((uint8_t*)badCarrier.mutableBytes)[0]^=1;else if(test==2){NSMutableData*code=[programs[@"encode_dataflow_basic"]mutableCopy];((uint8_t*)code.mutableBytes)[0]^=1;bad[@"encode_dataflow_basic"]=code;}else if(test==3)[bad removeObjectForKey:@"encode_dataflow_basic"];else bad[@"not_registered"]=programs[@"encode_dataflow_basic"];
   NSError*failure=nil;NSUInteger before=s.events.count;BOOL refused=![s registerCommandIRLibraryData:badSource expectedSHA256:pin carrierData:badCarrier programsByFunction:bad error:&failure]&&failure&&libraryInputImports==0&&s.events.count==before;
   [runs addObject:@{@"kind":@"library_registration_rejection",@"case":@(test),@"PASS":@(refused),@"native_imports":@(libraryInputImports),@"user_kernel_submitted":@NO}];if(!refused)return NO;
  }
  NSMutableData*sourceCopy=[source mutableCopy],*carrierCopy=[carrier mutableCopy];NSMutableDictionary*copies=[NSMutableDictionary new];for(NSString*name in programs)copies[name]=[programs[name]mutableCopy];
  result=[s registerCommandIRLibraryData:sourceCopy expectedSHA256:pin carrierData:carrierCopy programsByFunction:copies error:error];if(!result||libraryInputImports!=6)return NO;
  ((uint8_t*)sourceCopy.mutableBytes)[0]^=1;((uint8_t*)carrierCopy.mutableBytes)[0]^=1;for(NSMutableData*code in copies.allValues)((uint8_t*)code.mutableBytes)[0]^=1;
  NSError*duplicate=nil;BOOL refused=![s registerCommandIRLibraryData:source expectedSHA256:pin carrierData:carrier programsByFunction:programs error:&duplicate]&&duplicate&&libraryInputImports==6;
  [runs addObject:@{@"kind":@"library_registration_inputs_copied",@"PASS":@(refused),@"native_imports":@(libraryInputImports),@"all_caller_inputs_mutated_after_registration":@YES,@"duplicate_refused_without_import":@(refused),@"user_kernel_submitted":@NO}];result=refused;
 }@finally{method_setImplementation(method,libraryInputOriginal);}
 BOOL restored=method_getImplementation(method)==libraryInputOriginal;[runs addObject:@{@"kind":@"library_registration_factory_restored",@"PASS":@(restored),@"user_kernel_submitted":@NO}];return result&&restored;
}
