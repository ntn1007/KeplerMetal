// SPDX-License-Identifier: MIT
// Native library/function objects, with immutable registered producer profiles.
@interface KPIRLibraryLink : NSObject
@property(nonatomic,weak) KPCPUICBScope*scope;
@property(nonatomic) Class originalClass;
@property(nonatomic,copy) NSDictionary*registration;
@end
@implementation KPIRLibraryLink
@end
@interface KPAdaptedIRLibrary : NSObject
@property(nonatomic,weak) id<MTLLibrary>library;
@property(nonatomic) Class originalClass;
@end
@implementation KPAdaptedIRLibrary
@end
namespace {
char IRLibraryKey;
std::map<uintptr_t,Class>IRLibraryClasses;
Class originalIRLibrary(id object){KPIRLibraryLink*link=objc_getAssociatedObject(object,&IRLibraryKey);return link.originalClass?:objc_getClass("_MTLLibrary");}
Class originalIRDevice(id object){KPCPUICBScope*s=scopeFor(object);return s.originalDeviceClass?:objc_getClass("NVMTLDevice");}
void libraryEvent(__unsafe_unretained KPCPUICBScope*s,NSDictionary*row){NSMutableArray*events=s.eventRows;@synchronized(events){[events addObject:row];}}
NSDictionary*IRLibraryProfile(KPIRLibraryLink*link,NSString*name){return [name isKindOfClass:NSString.class]?link.registration[@"functions"][name]:nil;}
BOOL functionDescriptorSupported(MTLFunctionDescriptor*d,NSError**error){
 @try{if(d.options||([d respondsToSelector:@selector(binaryArchives)]&&d.binaryArchives.count))return fail(error,@"Function binary/archive options are outside the registered producer contract");}
 @catch(NSException*x){return fail(error,x.reason?:@"Function descriptor unavailable");}return YES;
}
id<MTLFunction>attachRegisteredLibraryFunction(KPCPUICBScope*s,id<MTLFunction>function,NSDictionary*registration,NSDictionary*profile,SEL selector,NSError**error){
 if(!function||!profile||!s)return function;
 @synchronized(s.factoryLock){
  if(s.restored)return function;
  BOOL lowered=[registration[@"native_source_lowering"]boolValue],tagged=[registration[@"reusable_contexts"]boolValue];
  if(!adoptNativeIRFunction(s,function,registration[@"source_SHA256"],0,YES,error,lowered,tagged))return nil;
  KPIRFunctionLink*link=objc_getAssociatedObject(function,&IRFunctionKey);
  if(!link||![link.schema isEqual:profile[@"schema"]]||function.functionConstantsDictionary.count){fail(error,@"Returned native function metadata differs from the registered source");return nil;}
  if(lowered){
   if(link.nativeRootPipeline||link.nativeProducerCarrier||link.nativeProducerProgram){fail(error,@"Native source function already owns an imported producer");return nil;}
   // Keep producerLink() empty: all six PSO factories must take their native path.
  }else{
   if(link.nativeRootPipeline&&link.nativeRootPipeline!=profile[@"pipeline"]){fail(error,@"Function already has a different producer pipeline");return nil;}
   link.nativeProducerCarrier=registration[@"carrier"];link.nativeProducerProgram=profile[@"program"];link.nativeRootPipeline=profile[@"pipeline"];link.nativeProducerProfile=profile[@"profile"];
  }
  libraryEvent(s,@{@"operation":@"automatic_IRv2_function",@"selector":NSStringFromSelector(selector),@"source_function":profile[@"profile"][@"function"],@"returned_function":function.name,@"library_SHA256":registration[@"source_SHA256"],@"native_function":@YES,@"native_source_lowering":@(lowered),@"generation_tagged_root":@(tagged),@"pipeline_imports_during_lookup":@0});return function;
 }
}
id<MTLFunction>IRLibraryFunction(id,SEL,NSString*) NS_RETURNS_RETAINED;
id<MTLFunction>IRLibraryFunction(id self,SEL selector,NSString*name){
 KPIRLibraryLink*link=objc_getAssociatedObject(self,&IRLibraryKey);KPCPUICBScope*s=link.scope;NSString*copy=[name copy];NSDictionary*profile=IRLibraryProfile(link,copy);
 typedef id<MTLFunction>(*F)(id,SEL,NSString*)__attribute__((ns_returns_retained));id<MTLFunction>f=((F)class_getMethodImplementation(originalIRLibrary(self),selector))(self,selector,copy);NSError*error=nil;return attachRegisteredLibraryFunction(s,f,link.registration,profile,selector,&error);
}
id<MTLFunction>IRLibraryConstants(id,SEL,NSString*,MTLFunctionConstantValues*,NSError**) NS_RETURNS_RETAINED;
id<MTLFunction>IRLibraryConstants(id self,SEL selector,NSString*name,MTLFunctionConstantValues*values,NSError**error){
 KPIRLibraryLink*link=objc_getAssociatedObject(self,&IRLibraryKey);KPCPUICBScope*s=link.scope;NSString*copy=[name copy];MTLFunctionConstantValues*snapshot=[values copy];NSDictionary*profile=IRLibraryProfile(link,copy);
 typedef id<MTLFunction>(*F)(id,SEL,NSString*,MTLFunctionConstantValues*,NSError**)__attribute__((ns_returns_retained));id<MTLFunction>f=((F)class_getMethodImplementation(originalIRLibrary(self),selector))(self,selector,copy,snapshot,error);return attachRegisteredLibraryFunction(s,f,link.registration,profile,selector,error);
}
id<MTLFunction>IRLibraryDescriptor(id,SEL,MTLFunctionDescriptor*,NSError**) NS_RETURNS_RETAINED;
id<MTLFunction>IRLibraryDescriptor(id self,SEL selector,MTLFunctionDescriptor*descriptor,NSError**error){
 if(error)*error=nil;MTLFunctionDescriptor*snapshot=[descriptor copy];KPIRLibraryLink*link=objc_getAssociatedObject(self,&IRLibraryKey);KPCPUICBScope*s=link.scope;NSDictionary*profile=IRLibraryProfile(link,snapshot.name);
 if(profile&&s&&!s.restored&&!functionDescriptorSupported(snapshot,error))return nil;
 typedef id<MTLFunction>(*F)(id,SEL,MTLFunctionDescriptor*,NSError**)__attribute__((ns_returns_retained));id<MTLFunction>f=((F)class_getMethodImplementation(originalIRLibrary(self),selector))(self,selector,snapshot,error);return attachRegisteredLibraryFunction(s,f,link.registration,profile,selector,error);
}
void IRLibraryConstantsAsync(id self,SEL selector,NSString*name,MTLFunctionConstantValues*values,void(^completion)(id<MTLFunction>,NSError*)){
 KPIRLibraryLink*link=objc_getAssociatedObject(self,&IRLibraryKey);__weak KPCPUICBScope*weak=link.scope;NSString*copy=[name copy];MTLFunctionConstantValues*snapshot=[values copy];NSDictionary*registration=link.registration,*profile=IRLibraryProfile(link,copy);
 typedef void(*F)(id,SEL,NSString*,MTLFunctionConstantValues*,void(^)(id<MTLFunction>,NSError*));((F)class_getMethodImplementation(originalIRLibrary(self),selector))(self,selector,copy,snapshot,^(id<MTLFunction>f,NSError*error){KPCPUICBScope*s=weak;id<MTLFunction>result=error?f:attachRegisteredLibraryFunction(s,f,registration,profile,selector,&error);s=nil;if(completion)completion(result,error);});
}
void IRLibraryDescriptorAsync(id self,SEL selector,MTLFunctionDescriptor*descriptor,void(^completion)(id<MTLFunction>,NSError*)){
 MTLFunctionDescriptor*snapshot=[descriptor copy];KPIRLibraryLink*link=objc_getAssociatedObject(self,&IRLibraryKey);__weak KPCPUICBScope*weak=link.scope;NSDictionary*registration=link.registration,*profile=IRLibraryProfile(link,snapshot.name);NSError*error=nil;
 if(profile&&weak&&!weak.restored&&!functionDescriptorSupported(snapshot,&error)){if(completion)dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{completion(nil,error);});return;}
 typedef void(*F)(id,SEL,MTLFunctionDescriptor*,void(^)(id<MTLFunction>,NSError*));((F)class_getMethodImplementation(originalIRLibrary(self),selector))(self,selector,snapshot,^(id<MTLFunction>f,NSError*failure){KPCPUICBScope*s=weak;id<MTLFunction>result=failure?f:attachRegisteredLibraryFunction(s,f,registration,profile,selector,&failure);s=nil;if(completion)completion(result,failure);});
}
id<MTLLibrary>adaptRegisteredIRLibrary(KPCPUICBScope*s,id<MTLLibrary>library,NSDictionary*registration,SEL selector,NSError**error){
 if(!library||!s||!registration)return library;
 @synchronized(s.factoryLock){
  if(s.restored)return library;
  KPIRLibraryLink*old=objc_getAssociatedObject(library,&IRLibraryKey);if(old){if(old.scope==s&&[old.registration[@"source_SHA256"]isEqual:registration[@"source_SHA256"]])return library;fail(error,@"Library belongs to a different producer registration");return nil;}
  Class original=object_getClass(library),dynamic=nil;if(original!=objc_getClass("_MTLLibrary")||class_getInstanceSize(original)!=64||library.device!=s.device){fail(error,@"Native library profile differs");return nil;}
  {std::lock_guard<std::mutex>lock(installMutex);dynamic=scopedClass(IRLibraryClasses,original,@"KPIRLibrary_",@selector(newFunctionWithName:),(IMP)IRLibraryFunction,error);
   const SEL selectors[]={@selector(newFunctionWithName:constantValues:error:),@selector(newFunctionWithDescriptor:error:),@selector(newFunctionWithName:constantValues:completionHandler:),@selector(newFunctionWithDescriptor:completionHandler:)};const IMP functions[]={(IMP)IRLibraryConstants,(IMP)IRLibraryDescriptor,(IMP)IRLibraryConstantsAsync,(IMP)IRLibraryDescriptorAsync};for(unsigned i=0;i<4&&dynamic;i++)if(!installRenderOverride(dynamic,original,selectors[i],functions[i]))dynamic=nil;}
  if(!dynamic){fail(error,@"Cannot install library-local function factories");return nil;}
  KPIRLibraryLink*link=[KPIRLibraryLink new];link.scope=s;link.originalClass=original;link.registration=registration;objc_setAssociatedObject(library,&IRLibraryKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);object_setClass(library,dynamic);
  if(!s.adaptedIRLibraries)s.adaptedIRLibraries=[NSMutableArray new];KPAdaptedIRLibrary*record=[KPAdaptedIRLibrary new];record.library=library;record.originalClass=original;[s.adaptedIRLibraries addObject:record];libraryEvent(s,@{@"operation":@"automatic_IRv2_library",@"selector":NSStringFromSelector(selector),@"source_SHA256":registration[@"source_SHA256"],@"native_library":@YES,@"native_creation_from_immutable_snapshot":@YES});return library;
 }
}
NSDictionary*registrationForBytes(KPCPUICBScope*s,NSData*bytes){if(!s||!bytes)return nil;@synchronized(s.factoryLock){return s.restored?nil:s.registeredIRLibraries[hash(bytes)];}}
BOOL registeredLibraryLength(KPCPUICBScope*s,NSUInteger length){if(!length)return NO;@synchronized(s.factoryLock){if(s.restored)return NO;for(NSDictionary*p in s.registeredIRLibraries.allValues)if([p[@"source_bytes"]length]==length)return YES;return NO;}}
NSData*registeredPathSnapshot(KPCPUICBScope*s,NSString*path){
 if(!s||!path.length)return nil;NSDictionary*attributes=[NSFileManager.defaultManager attributesOfItemAtPath:path error:nil];NSUInteger size=[attributes[NSFileSize]unsignedIntegerValue];if(!registeredLibraryLength(s,size))return nil;
 NSFileHandle*file=[NSFileHandle fileHandleForReadingAtPath:path];if(!file)return nil;NSData*data=nil;@try{data=[file readDataOfLength:size+1];}@finally{[file closeFile];}return data.length==size?[NSData dataWithBytes:data.bytes length:data.length]:nil;
}
id<MTLLibrary>nativeLibrarySnapshot(id device,Class original,NSData*bytes,NSError**error) NS_RETURNS_RETAINED;
id<MTLLibrary>nativeLibrarySnapshot(id device,Class original,NSData*bytes,NSError**error){
 dispatch_data_t payload=dispatch_data_create(bytes.bytes,bytes.length,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{(void)bytes.length;});typedef id<MTLLibrary>(*F)(id,SEL,dispatch_data_t,NSError**)__attribute__((ns_returns_retained));return((F)class_getMethodImplementation(original,@selector(newLibraryWithData:error:)))(device,@selector(newLibraryWithData:error:),payload,error);
}
id<MTLLibrary>IRDeviceLibraryData(id,SEL,dispatch_data_t,NSError**) NS_RETURNS_RETAINED;
id<MTLLibrary>IRDeviceLibraryData(id self,SEL selector,dispatch_data_t data,NSError**error){
 KPCPUICBScope*s=scopeFor(self);Class original=originalIRDevice(self);NSData*bytes=nil;if(data&&registeredLibraryLength(s,dispatch_data_get_size(data))){const void*pointer=nullptr;size_t size=0;dispatch_data_t mapped=dispatch_data_create_map(data,&pointer,&size);if(mapped&&pointer)bytes=[NSData dataWithBytes:pointer length:size];}NSDictionary*registration=registrationForBytes(s,bytes);
 typedef id<MTLLibrary>(*F)(id,SEL,dispatch_data_t,NSError**)__attribute__((ns_returns_retained));id<MTLLibrary>library=registration?nativeLibrarySnapshot(self,original,bytes,error):((F)class_getMethodImplementation(original,selector))(self,selector,data,error);return adaptRegisteredIRLibrary(s,library,registration,selector,error);
}
id<MTLLibrary>IRDeviceLibraryURL(id,SEL,NSURL*,NSError**) NS_RETURNS_RETAINED;
id<MTLLibrary>IRDeviceLibraryURL(id self,SEL selector,NSURL*url,NSError**error){
 KPCPUICBScope*s=scopeFor(self);Class original=originalIRDevice(self);NSData*bytes=url.isFileURL?registeredPathSnapshot(s,url.path):nil;NSDictionary*registration=registrationForBytes(s,bytes);typedef id<MTLLibrary>(*F)(id,SEL,NSURL*,NSError**)__attribute__((ns_returns_retained));id<MTLLibrary>library=registration?nativeLibrarySnapshot(self,original,bytes,error):((F)class_getMethodImplementation(original,selector))(self,selector,url,error);return adaptRegisteredIRLibrary(s,library,registration,selector,error);
}
id<MTLLibrary>IRDeviceLibraryFile(id,SEL,NSString*,NSError**) NS_RETURNS_RETAINED;
id<MTLLibrary>IRDeviceLibraryFile(id self,SEL selector,NSString*path,NSError**error){
 KPCPUICBScope*s=scopeFor(self);Class original=originalIRDevice(self);NSData*bytes=registeredPathSnapshot(s,path);NSDictionary*registration=registrationForBytes(s,bytes);typedef id<MTLLibrary>(*F)(id,SEL,NSString*,NSError**)__attribute__((ns_returns_retained));id<MTLLibrary>library=registration?nativeLibrarySnapshot(self,original,bytes,error):((F)class_getMethodImplementation(original,selector))(self,selector,path,error);return adaptRegisteredIRLibrary(s,library,registration,selector,error);
}
BOOL installIRLibraryFactories(KPCPUICBScope*s,NSError**error){
 std::lock_guard<std::mutex>lock(installMutex);Class dynamic=object_getClass(s.device),original=s.originalDeviceClass;
 const SEL selectors[]={@selector(newLibraryWithData:error:),@selector(newLibraryWithURL:error:),@selector(newLibraryWithFile:error:),@selector(newComputePipelineStateWithFunction:error:),@selector(newComputePipelineStateWithFunction:options:reflection:error:),@selector(newComputePipelineStateWithDescriptor:options:reflection:error:),@selector(newComputePipelineStateWithFunction:completionHandler:),@selector(newComputePipelineStateWithFunction:options:completionHandler:),@selector(newComputePipelineStateWithDescriptor:options:completionHandler:)};
 const IMP functions[]={(IMP)IRDeviceLibraryData,(IMP)IRDeviceLibraryURL,(IMP)IRDeviceLibraryFile,(IMP)registeredProducerPipeline,(IMP)producerFunctionOptions,(IMP)producerDescriptor,(IMP)producerFunctionAsync,(IMP)producerFunctionAsyncOptions,(IMP)producerDescriptorAsync};
 for(unsigned i=0;i<9;i++)if(!installRenderOverride(dynamic,original,selectors[i],functions[i]))return fail(error,@"Cannot install device-local library/pipeline factories");return YES;
}
void restoreIRLibraries(__unsafe_unretained KPCPUICBScope*s){NSUInteger count=0;for(KPAdaptedIRLibrary*r in s.adaptedIRLibraries){id library=r.library;if(library){object_setClass(library,r.originalClass);objc_setAssociatedObject(library,&IRLibraryKey,nil,OBJC_ASSOCIATION_ASSIGN);count++;}}[s.adaptedIRLibraries removeAllObjects];[s.registeredIRLibraries removeAllObjects];if(count)libraryEvent(s,@{@"operation":@"restore_IRv2_libraries",@"live_libraries_restored":@(count)});}
}
