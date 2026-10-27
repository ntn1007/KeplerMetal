// SPDX-License-Identifier: MIT
// Opt-in bootstrap for exactly one signed client and one certified library.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import <CommonCrypto/CommonDigest.h>
#import "KeplerNativeCAS.h"
#import "KeplerGPUIdentity.h"
#include <mutex>
#include <cstdlib>
#include <cstdio>
#ifndef KM_CAS_APP_HASH
#error Expected signed client SHA-256
#endif
#ifndef KM_CAS_LIBRARY_HASH
#error Expected library SHA-256
#endif
#ifndef KM_CAS_MANIFEST_HASH
#error Expected manifest SHA-256
#endif
static NSString *const appHash=@KM_CAS_APP_HASH,*const libraryHash=@KM_CAS_LIBRARY_HASH,*const manifestHash=@KM_CAS_MANIFEST_HASH;
static id<MTLDevice> selected;static NSDictionary *selectedIdentity;static NSData *librarySnapshot;static NSDictionary *profiles;static NSMutableArray *events;static char functionTag;static thread_local bool internalCreate=false;
static NSString *hash(NSData*d){if(!d||d.length>64*1024*1024)return nil;unsigned char v[32];CC_SHA256(d.bytes,(CC_LONG)d.length,v);NSMutableString*s=[NSMutableString string];for(unsigned i=0;i<32;i++)[s appendFormat:@"%02x",v[i]];return s;}
static void emit(void){@autoreleasepool{const char*p=getenv("KM_CAS_EVENT_PATH");if(!p||!events)return;NSDictionary*r=@{@"identity":selectedIdentity?:@{},@"events":events,@"system_modified":@NO};NSData*d=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];if(d)[d writeToFile:@(p) atomically:YES];}}
static id<MTLFunction> taggedFunction(id self,SEL cmd,NSString*name) NS_RETURNS_RETAINED;
static id<MTLFunction> taggedFunction(id self,SEL cmd,NSString*name){Class parent=class_getSuperclass(object_getClass(self));Method m=class_getInstanceMethod(parent,cmd);typedef id<MTLFunction>(*Fn)(id,SEL,NSString*) __attribute__((ns_returns_retained));id<MTLFunction>f=((Fn)method_getImplementation(m))(self,cmd,name);if(f&&profiles[name])objc_setAssociatedObject(f,&functionTag,name,OBJC_ASSOCIATION_RETAIN_NONATOMIC);return f;}
static id<MTLLibrary> scopedLibrary(id self,SEL cmd,NSURL*url,NSError**error) NS_RETURNS_RETAINED;
static id<MTLLibrary> scopedLibrary(id self,SEL cmd,NSURL*url,NSError**error){
 Class parent=class_getSuperclass(object_getClass(self));Method m=class_getInstanceMethod(parent,cmd);typedef id<MTLLibrary>(*Fn)(id,SEL,NSURL*,NSError**) __attribute__((ns_returns_retained));
 NSData*snapshot=url.isFileURL?[NSData dataWithContentsOfURL:url]:nil;
 if(self!=selected||![hash(snapshot)isEqual:libraryHash]||![snapshot isEqual:librarySnapshot]){fprintf(stderr,"KM_CAS library unapproved\n");return ((Fn)method_getImplementation(m))(self,cmd,url,error);}
 SEL ds=@selector(newLibraryWithData:error:);Method dm=class_getInstanceMethod(parent,ds);typedef id<MTLLibrary>(*DataFn)(id,SEL,dispatch_data_t,NSError**) __attribute__((ns_returns_retained));
 dispatch_data_t payload=dispatch_data_create(snapshot.bytes,snapshot.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)snapshot.length;});id<MTLLibrary>lib=((DataFn)method_getImplementation(dm))(self,ds,payload,error);if(!lib)return nil;
 Class original=object_getClass(lib);Method fm=class_getInstanceMethod(original,@selector(newFunctionWithName:));NSString*n=[@"KMCASLibrary_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@""]];Class dyn=objc_allocateClassPair(original,n.UTF8String,0);
 if(!dyn||!fm||!class_addMethod(dyn,@selector(newFunctionWithName:),(IMP)taggedFunction,method_getTypeEncoding(fm))){if(dyn)objc_disposeClassPair(dyn);return nil;}objc_registerClassPair(dyn);if(class_getInstanceSize(dyn)!=class_getInstanceSize(original))return nil;object_setClass(lib,dyn);fprintf(stderr,"KM_CAS library approved\n");return lib;
}
static id<MTLComputePipelineState> scopedPipeline(id self,SEL cmd,id<MTLFunction>function,NSError**error) NS_RETURNS_RETAINED;
static id<MTLComputePipelineState> scopedPipeline(id self,SEL cmd,id<MTLFunction>function,NSError**error){
 Class parent=class_getSuperclass(object_getClass(self));Method m=class_getInstanceMethod(parent,cmd);typedef id<MTLComputePipelineState>(*Fn)(id,SEL,id<MTLFunction>,NSError**) __attribute__((ns_returns_retained));
 NSString*name=objc_getAssociatedObject(function,&functionTag);NSDictionary*profile=name?profiles[name]:nil;
 if(self!=selected||internalCreate||!profile||![profile[@"candidate"]boolValue]){if(profile&&![profile[@"candidate"]boolValue])fprintf(stderr,"KM_CAS native control %s\n",name.UTF8String);return ((Fn)method_getImplementation(m))(self,cmd,function,error);}
 internalCreate=true;NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=nil;
 @try{pipeline=KPCreateCertifiedNativeCASPipeline(selected,librarySnapshot,libraryHash,profile[@"certificate"],profile[@"certificate_SHA256"],error,&proof);}
 @finally{internalCreate=false;}
 if(!pipeline||![proof[@"gate_accepted"]boolValue]||![proof[@"constructor_restored"]boolValue]||![proof[@"native_import"][@"contract_verified"]boolValue]){fprintf(stderr,"KM_CAS repair refused %s\n",name.UTF8String);return nil;}
 [events addObject:@{@"function":name,@"proof":proof}];fprintf(stderr,"KM_CAS repaired %s\n",name.UTF8String);return pipeline;
}
static bool add(Class c,Class parent,SEL selector,IMP imp){Method m=class_getInstanceMethod(parent,selector);return m&&class_addMethod(c,selector,imp,method_getTypeEncoding(m));}
static id<MTLDevice> replacement(void) NS_RETURNS_RETAINED;
static id<MTLDevice> replacement(void){@autoreleasepool{
 static std::mutex mutex;static thread_local bool entered=false;static bool failed=false;if(entered)return nil;struct Guard{bool&v;Guard(bool&x):v(x){v=true;}~Guard(){v=false;}}guard(entered);std::lock_guard<std::mutex>lock(mutex);if(selected)return selected;if(failed)return nil;failed=true;
 uint32_t len=0;_NSGetExecutablePath(nullptr,&len);if(!len||len>8192)return nil;char*path=(char*)calloc(len,1);if(!path)return nil;int ok=_NSGetExecutablePath(path,&len);NSData*app=ok==0?[NSData dataWithContentsOfFile:@(path)]:nil;free(path);
 const char*dir=getenv("KM_CAS_ASSET_PATH");NSString*root=dir?@(dir):nil;NSData*manifestData=root?[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:@"client-manifest.json"]]:nil;NSData*lib=root?[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:@"cas_client.metallib"]]:nil;
 if(![hash(app)isEqual:appHash]||![hash(manifestData)isEqual:manifestHash]||![hash(lib)isEqual:libraryHash]){fprintf(stderr,"KM_CAS identity refused\n");return nil;}
 NSDictionary*manifest=[NSJSONSerialization JSONObjectWithData:manifestData options:0 error:nil];NSArray*rows=manifest[@"profiles"];if(![rows isKindOfClass:NSArray.class]||rows.count!=5||![manifest[@"library_SHA256"]isEqual:libraryHash])return nil;
 NSMutableDictionary*p=[NSMutableDictionary new];NSSet*allowed=[NSSet setWithArray:@[@"sdk_cas_expected",@"sdk_cas_slot",@"sdk_cas_noise",@"sdk_cas_swizzle",@"sdk_keep_comparand"]];
 for(NSDictionary*r in rows){NSString*n=r[@"function"],*file=r[@"certificate"],*digest=r[@"certificate_SHA256"];if(![allowed containsObject:n]||p[n]||![file isKindOfClass:NSString.class]||![file.lastPathComponent isEqual:file])return nil;NSData*c=[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:file]];if(![hash(c)isEqual:digest]){fprintf(stderr,"KM_CAS certificate refused\n");return nil;}NSDictionary*parsed=[NSJSONSerialization JSONObjectWithData:c options:0 error:nil];BOOL candidate=[r[@"candidate"]boolValue];if(candidate!=[parsed[@"candidate"]boolValue]||(candidate&&![parsed[@"decoder_reproduced_listing"]boolValue]))return nil;p[n]=@{@"candidate":@(candidate),@"certificate":c,@"certificate_SHA256":digest};}
 if(p.count!=5)return nil;id<MTLDevice>d=nil;NSDictionary*identity=nil;for(id<MTLDevice>x in MTLCopyAllDevices()){NSDictionary*i=KPKepler880MIdentity(x);if(i){if(d)return nil;d=x;identity=i;}}if(!d)return nil;
 Class original=object_getClass(d);NSString*n=[@"KMCASDevice_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@""]];Class dyn=objc_allocateClassPair(original,n.UTF8String,0);if(!dyn)return nil;
 if(!add(dyn,original,@selector(newLibraryWithURL:error:),(IMP)scopedLibrary)||!add(dyn,original,@selector(newComputePipelineStateWithFunction:error:),(IMP)scopedPipeline)){objc_disposeClassPair(dyn);return nil;}objc_registerClassPair(dyn);if(class_getInstanceSize(dyn)!=class_getInstanceSize(original))return nil;
 librarySnapshot=[lib copy];profiles=[p copy];events=[NSMutableArray new];selectedIdentity=identity;selected=d;object_setClass(d,dyn);atexit(emit);fprintf(stderr,"KM_CAS enabled\n");return d;
}}
__attribute__((used)) static struct{const void*replacement;const void*replacee;} interpose[] __attribute__((section("__DATA,__interpose")))={{(const void*)replacement,(const void*)MTLCreateSystemDefaultDevice}};
