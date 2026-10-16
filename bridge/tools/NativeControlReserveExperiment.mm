// SPDX-License-Identifier: MIT
// Application-only, pinned native metadata experiment. Compile with MRC.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <cstring>
#include <mutex>
#include <vector>
namespace {
static std::mutex mutex_;static IMP original_;static char retentionKey;
struct State {NSData*metadata;NSString*codeHash;uint32_t reserve;NSMutableArray*events;NSMutableArray*payloads;unsigned calls=0;bool rejected=false;};
static State*active;
static uint32_t u32(const void*p,size_t n){uint32_t x;memcpy(&x,(const char*)p+n,4);return x;}
static uint64_t u64(const void*p,size_t n){uint64_t x;memcpy(&x,(const char*)p+n,8);return x;}
static void put(void*p,size_t n,uint32_t x){memcpy((char*)p+n,&x,4);}
static NSString*sha(NSData*d){unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString string];for(unsigned char b:h)[s appendFormat:@"%02x",b];return s;}
static void error_(NSError**e,NSString*s){if(e)*e=[NSError errorWithDomain:@"KeplerControlReserveExperiment" code:1 userInfo:@{NSLocalizedDescriptionKey:s}];}
static id init_(id self,SEL selector,const void*input,NSUInteger length,id device){
 State*s=active;if(!s)return ((id(*)(id,SEL,const void*,NSUInteger,id))original_)(self,selector,input,length,device);
 s->calls++;size_t metadata=0,code=0,codeSize=0;unsigned nm=0,nc=0;bool valid=input&&length>=24&&length<=8*1024*1024;
 const auto*b=(const unsigned char*)input;size_t offset=8;valid=valid&&(u32(b,0)==7||u32(b,0)==8||u32(b,0)==9)&&u32(b,4)==length;
 for(unsigned i=0;valid&&i<32;i++){
  if(offset>length||length-offset<16){valid=false;break;}uint64_t next=u64(b,offset);uint32_t kind=u32(b,offset+8),size=u32(b,offset+12);
  if(size>length-offset-16){valid=false;break;}if(i==0)valid=kind==1&&size==4&&u32(b,offset+16)==5;
  if(kind==0x10004){metadata=offset+16;nm++;valid=valid&&size==232;}
  if(kind==0x10005){code=offset+16;codeSize=size;nc++;}
  if(!next)break;if(next<16+size||next>length-offset){valid=false;break;}offset+=next;if(i==31)valid=false;
 }
 valid=valid&&nm==1&&nc==1&&codeSize&&codeSize%64==0&&s->metadata.length==232;
 bool parsed=valid,metadataMatch=false,codeMatch=false;NSString*actualCodeHash=@"";NSMutableArray*actualWords=[NSMutableArray array];
 if(parsed){
  metadataMatch=true;
  for(unsigned i=0;i<58;i++){
   uint32_t value=u32(b,metadata+4*i);[actualWords addObject:@(value)];
   // Words2/4 varied across observed native compilations with identical code.
   // Their meaning is unknown. Preserve their actual incoming bytes; never
   // substitute certificate values. Every other word remains pinned here.
   if(i!=2&&i!=4&&value!=u32(s->metadata.bytes,4*i))metadataMatch=false;
  }
  actualCodeHash=sha([NSData dataWithBytes:b+code length:codeSize]);codeMatch=[actualCodeHash isEqual:s->codeHash];
 }
 valid=valid&&metadataMatch&&codeMatch;
 uint32_t oldControl=valid?u32(b,metadata+44):0,frame=valid?u32(b,metadata+48):0,reserve=s->reserve?s->reserve:oldControl;
 valid=valid&&reserve>=oldControl&&reserve<=4096&&(!s->reserve||reserve%512==0)&&frame<=16384&&u32(b,metadata+36)==frame*64+oldControl;
 NSMutableData*data=nil;NSMutableDictionary*event=[NSMutableDictionary dictionaryWithDictionary:@{@"certificate_matches":@(valid),@"requested_reserve":@(s->reserve),@"parsed":@(parsed),@"metadata_match":@(metadataMatch),@"code_match":@(codeMatch),@"actual_code_SHA256":actualCodeHash,@"actual_metadata_words":actualWords,@"metadata_sections":@(nm),@"code_sections":@(nc)}];
 if(valid){
  data=[NSMutableData dataWithBytes:input length:length];put(data.mutableBytes,metadata+36,frame*64+reserve);put(data.mutableBytes,metadata+44,reserve);
  bool same=true;const auto*patched=(const unsigned char*)data.bytes;
  for(size_t i=0;i<length;i++)if(!((i>=metadata+36&&i<metadata+40)||(i>=metadata+44&&i<metadata+48))&&b[i]!=patched[i])same=false;
  event[@"only_metadata_words9_11_changed"]=@(same);event[@"native_code_identical"]=@(memcmp(b+code,patched+code,codeSize)==0);event[@"old_control"]=@(oldControl);event[@"new_control"]=@(reserve);event[@"native_frame"]=@(frame);event[@"native_GPR"]=@(u32(b,metadata+28));event[@"code_bytes"]=@(codeSize);
  valid=valid&&same;[s->payloads addObject:data];
 }
 if(!valid)s->rejected=true;
 id result=((id(*)(id,SEL,const void*,NSUInteger,id))original_)(self,selector,valid?data.bytes:input,length,device);
 if(result&&valid){
  Ivar iv=class_getInstanceVariable(object_getClass(result),"_variant");uintptr_t pointer=0;
  if(iv&&ivar_getOffset(iv)==32)memcpy(&pointer,(const char*)result+32,8);
  unsigned char v[128]={};mach_vm_size_t read=0;kern_return_t status=pointer?mach_vm_read_overwrite(mach_task_self(),pointer,sizeof(v),(mach_vm_address_t)v,&read):KERN_INVALID_ADDRESS;
  uint32_t expected=((frame+15)&~15u)*64+((reserve+511)&~511u)+512;
  bool decoded=status==KERN_SUCCESS&&read==sizeof(v)&&u64(v,24)==codeSize&&u32(v,44)==u32(b,metadata)&&u32(v,48)==u32(b,metadata+28)&&u32(v,56)==u32(b,metadata+56)&&u32(v,40)==expected;
  event[@"decoded_contract_verified"]=@(decoded);event[@"decoded_allocation_word40"]=@(u32(v,40));event[@"expected_allocation_word40"]=@(expected);event[@"decoded_spill_bytes56"]=@(u32(v,56));if(!decoded)s->rejected=true;
 }else s->rejected=true;
 [s->events addObject:event];return result;
}
}
extern "C" id<MTLComputePipelineState> KPExperimentalCreateNativeReservePipeline(
 id<MTLDevice>d,NSURL*library,NSString*function,NSData*certificate,NSString*codeHash,uint32_t reserve,NSError**error,NSDictionary**proof) NS_RETURNS_RETAINED {
 if(error)*error=nil;if(proof)*proof=nil;
 if(!d||![d.name isEqual:@"NVIDIA GeForce GTX 880M"]||certificate.length!=232||codeHash.length!=64||reserve>4096||(reserve&&reserve%512)){error_(error,@"Invalid experiment contract");return nil;}
 const char*path="/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver";
 if(![sha([NSData dataWithContentsOfFile:@(path)])isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"]){error_(error,@"Driver fingerprint mismatch");return nil;}
 std::lock_guard<std::mutex>lock(mutex_);Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));
 if(active||!method||strcmp(method_getTypeEncoding(method),"@40@0:8r^v16Q24@32")){error_(error,@"Unexpected constructor context");return nil;}
 IMP saved=method_getImplementation(method);Dl_info image={};if(!dladdr((void*)saved,&image)||!image.dli_fname||strcmp(image.dli_fname,path)){error_(error,@"Unexpected constructor owner");return nil;}
 State state{certificate,codeHash,reserve,[NSMutableArray array],[NSMutableArray array]};original_=saved;active=&state;
 IMP replaced=method_setImplementation(method,(IMP)init_);if(replaced!=saved){method_setImplementation(method,replaced);active=nullptr;error_(error,@"Concurrent constructor change");return nil;}
 id<MTLComputePipelineState>pso=nil;
 @try {id<MTLLibrary>lib=[d newLibraryWithURL:library error:error];id<MTLFunction>f=[lib newFunctionWithName:function];if(f)pso=[d newComputePipelineStateWithFunction:f error:error];[f release];[lib release];}
 @catch(NSException*e){state.rejected=true;error_(error,e.reason);}
 @finally{method_setImplementation(method,saved);active=nullptr;}
 bool restored=method_getImplementation(method)==saved,verified=pso&&state.calls>0&&!state.rejected&&restored;
 if(proof)*proof=@{@"contract_verified":@(verified),@"constructor_restored":@(restored),@"calls":@(state.calls),@"events":state.events,@"native_program_replaced":@NO,@"system_modified":@NO};
 if(pso&&!verified){[pso release];pso=nil;error_(error,@"Native allocation experiment rejected before dispatch");}
 if(pso)objc_setAssociatedObject(pso,&retentionKey,state.payloads,OBJC_ASSOCIATION_RETAIN_NONATOMIC);return pso;
}
