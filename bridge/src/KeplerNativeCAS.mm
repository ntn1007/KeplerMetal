// Derived from a frozen qualified transport; source provenance in native-CAS SDK build.
#import "KeplerProgramImport.h"
#import "KeplerGPUIdentity.h"
#import "KeplerDriverProfile.h"
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <cstring>
#include <mutex>
#include <vector>
#include <unistd.h>
#include <atomic>
#include <cstdio>
#include <CommonCrypto/CommonDigest.h>
#include "KeplerConditionalAux.h"

namespace {
struct Section {size_t header,payload,size;uint32_t type;};
struct Context {
 NSData *code;
 KeplerImportConfig config;
 NSMutableArray *events,*payloads;
 bool verified=false;
 uint32_t expectedStage=5;
 size_t prefixBytes=0;
 NSData *additionalVertex=nil;
 KeplerImportConfig vertexConfig={};
 bool vertexVerified=false;
 bool rejected=false;
 unsigned targetImports=0,verifiedImports=0;
};
std::mutex importMutex;
std::atomic<IMP> originalInit{nullptr};
thread_local Context *activeContext=nullptr;
thread_local bool nativeAllocationScopeActive=false;
thread_local NSData *expectedNativeOriginal=nullptr;
thread_local bool keepNativeMetadata=false;
thread_local NSData *certifiedLibraryData=nil,*certifiedNativeMetadata=nil;
thread_local bool certifiedConditionalAux=false;
thread_local id<MTLFunction> certifiedSuppliedFunction=nil;
thread_local MTLComputePipelineDescriptor *approvedPipelineDescriptor=nil;
thread_local MTLPipelineOption certifiedPipelineOptions=MTLPipelineOptionNone;
thread_local MTLComputePipelineReflection **certifiedReflection=nullptr;
thread_local const KeplerLocalMemoryConfig *localMemoryContract=nullptr;
char certifiedInputsKey;
char retainedPayloadKey;
uint32_t u32(const unsigned char*b,size_t offset){uint32_t v;memcpy(&v,b+offset,4);return v;}
uint64_t u64(const unsigned char*b,size_t offset){uint64_t v;memcpy(&v,b+offset,8);return v;}
void put32(unsigned char*b,size_t offset,uint32_t value){memcpy(b+offset,&value,4);}
bool parse(const unsigned char*b,size_t size,std::vector<Section>&table){
 if(!b||size<32||(u32(b,0)!=7&&u32(b,0)!=8&&u32(b,0)!=9)||u32(b,4)!=size)return false;
 size_t offset=8;
 for(unsigned n=0;n<32;n++){
  if(offset>size-16)return false;
  uint64_t next=u64(b,offset);uint32_t type=u32(b,offset+8),bytes=u32(b,offset+12);
  if(bytes>size-offset-16)return false;
  table.push_back({offset,offset+16,bytes,type});
  if(!next){
   size_t end=table.back().payload+table.back().size;
   if(end==size)return true;
   // Observed v8 vertex-only container: a 4-byte literal and zero padding to 8.
   if(((end+7u)&~size_t(7))!=size)return false;
   for(size_t i=end;i<size;i++)if(b[i])return false;
   return true;
  }
  if(next<16ull+bytes||next>size-offset)return false;
  offset+=next;
 }return false;
}
id importInit(id self,SEL selector,const void*input,NSUInteger length,id device){
 Context*c=activeContext;IMP native=originalInit.load(std::memory_order_acquire);
 if(!native)return nil;
 if(!c)return ((id(*)(id,SEL,const void*,NSUInteger,id))native)(self,selector,input,length,device);
 const unsigned char*b=(const unsigned char*)input;std::vector<Section>table;
 bool valid=parse(b,length,table);Section metadata={},code={},aux={};unsigned metadataCount=0,codeCount=0,auxCount=0;
 if(valid&&c->additionalVertex&&table.front().type==1&&table.front().size==4&&u32(b,table.front().payload)==0){
  Context vertex{c->additionalVertex,c->vertexConfig,c->events,c->payloads,false,0,80};activeContext=&vertex;
  id result=nil;
  @try {result=importInit(self,selector,input,length,device);}
  @finally {activeContext=c;c->vertexVerified=vertex.verified&&!vertex.rejected&&vertex.targetImports>0&&vertex.targetImports==vertex.verifiedImports;c->rejected|=vertex.rejected;}
  return result;
 }
 if(valid&&table.front().type==1&&table.front().size==4&&u32(b,table.front().payload)!=c->expectedStage){
  [c->events addObject:@{@"stage":@(u32(b,table.front().payload)),@"code_replaced":@NO}];
  return ((id(*)(id,SEL,const void*,NSUInteger,id))native)(self,selector,input,length,device);
 }
 if(valid)for(const auto&s:table){if(s.type==0x10004){metadata=s;metadataCount++;}if(s.type==0x10005){code=s;codeCount++;}if(s.type==0x10006){aux=s;auxCount++;}}
 valid=valid&&table.front().type==1&&table.front().size==4&&u32(b,table.front().payload)==c->expectedStage;
 valid=valid&&metadataCount==1&&codeCount==1&&metadata.size==232&&code.size>=c->prefixBytes&&(code.size-c->prefixBytes)%64==0;
 valid=valid&&(!u64(b,code.header)||u64(b,code.header)==16+code.size);
 bool expectedMatches=true;
 if(expectedNativeOriginal){expectedMatches=valid&&code.size==expectedNativeOriginal.length&&memcmp(b+code.payload,expectedNativeOriginal.bytes,code.size)==0;valid=valid&&expectedMatches;}
 bool metadataMatches=!certifiedNativeMetadata||(valid&&metadata.size==certifiedNativeMetadata.length&&memcmp(b+metadata.payload,certifiedNativeMetadata.bytes,metadata.size)==0);
 valid=valid&&metadataMatches;
 bool auxMatches=!certifiedConditionalAux||(valid&&KPConditionalAuxMatches(auxCount?b+aux.payload:nullptr,aux.size,auxCount));
 valid=valid&&auxMatches;
 bool localMetadataMatches=true;
 if(localMemoryContract){
  const KeplerLocalMemoryConfig&m=*localMemoryContract;
  localMetadataMatches=valid&&c->expectedStage==5&&!c->prefixBytes&&
   u32(b,metadata.payload)==code.size/8-1&&
   u32(b,metadata.payload+36)==m.carrier_local_bytes*64&&
   u32(b,metadata.payload+44)==0&&
   u32(b,metadata.payload+48)==m.carrier_local_bytes&&
   u32(b,metadata.payload+52)==m.carrier_local_bytes&&
   u32(b,metadata.payload+56)==m.carrier_spill_bytes&&
   u32(b,metadata.payload+140)==m.carrier_control_barriers;
  valid=valid&&localMetadataMatches;
 }
 if(valid)c->targetImports++;
 NSMutableDictionary*event=[NSMutableDictionary dictionaryWithDictionary:@{@"valid_container":@(valid),@"original_bytes":@(length),@"container_version":@(length>=8?u32(b,0):0),@"code_replaced":@NO}];
 if(expectedNativeOriginal)event[@"expected_original_code_identical"]=@(expectedMatches);
 if(certifiedNativeMetadata)event[@"native_metadata_identical_to_certificate"]=@(metadataMatches);
 if(certifiedConditionalAux)event[@"conditional_auxiliary_section_pinned"]=@(auxMatches);
 if(localMemoryContract)event[@"native_local_metadata_verified"]=@(localMetadataMatches);
 const void*passed=input;NSUInteger size=length;NSMutableData*patched=nil;
 if(valid){
  patched=[NSMutableData dataWithBytes:input length:code.payload+c->prefixBytes];[patched appendData:c->code];
  [patched appendBytes:b+code.payload+code.size length:length-code.payload-code.size];
  if(patched.length>UINT32_MAX){c->rejected=true;return nil;}
  unsigned char*bytes=(unsigned char*)patched.mutableBytes;
  put32(bytes,4,(uint32_t)patched.length);put32(bytes,code.header+12,(uint32_t)(c->code.length+c->prefixBytes));
  if(u64(b,code.header)){uint64_t next=16+c->code.length+c->prefixBytes;memcpy(bytes+code.header,&next,8);}
  // Metadata after code moves when the code section changes size.
  size_t metadataOffset=metadata.payload;
  if(metadata.header>code.header)metadataOffset=metadata.payload-code.size+c->prefixBytes+c->code.length;
  if(localMemoryContract){
   uint32_t count=(uint32_t)(c->code.length/8-1);
   put32(bytes,metadataOffset,count);put32(bytes,metadataOffset+28,c->config.registers);
   // The previously qualified SM30 structured-control profile requires this
   // control reservation even when NAK reports no external CRS spill bytes.
   // Its complete meaning is not inferred. Keep the native local allocation
   // word 9 and byte capacities 12/13/14 unchanged; do not reuse the old word9=576.
   put32(bytes,metadataOffset+44,576);
   bool unchanged=true;for(size_t i=0;i<metadata.size;i++)if(!(i<4||(i>=28&&i<32)||(i>=44&&i<48))&&bytes[metadataOffset+i]!=b[metadata.payload+i])unchanged=false;
   event[@"native_metadata_preserved_except_instruction_register_and_control"]=@(unchanged);
   event[@"native_local_allocation_fields_preserved"]=@(u32(bytes,metadataOffset+36)==u32(b,metadata.payload+36)&&u32(bytes,metadataOffset+48)==u32(b,metadata.payload+48)&&u32(bytes,metadataOffset+52)==u32(b,metadata.payload+52)&&u32(bytes,metadataOffset+56)==u32(b,metadata.payload+56));
   event[@"required_scratch_bytes"]=@(localMemoryContract->required_scratch_bytes);
   event[@"carrier_local_bytes"]=@(localMemoryContract->carrier_local_bytes);
   event[@"carrier_spill_bytes"]=@(localMemoryContract->carrier_spill_bytes);
   event[@"original_instruction_count"]=@(u32(b,metadata.payload));event[@"normalized_instruction_count"]=@(count);
   if(!unchanged)c->rejected=true;
  }else if(keepNativeMetadata){
   c->config={u32(b,metadata.payload+28),u32(b,metadata.payload+36),u32(b,metadata.payload+44)};
   if(c->config.registers<1||c->config.registers>63){c->rejected=true;return nil;}
   uint32_t originalCount=u32(b,metadata.payload),newCount=(uint32_t)(c->code.length/8-1);
   if(originalCount!=code.size/8-1){c->rejected=true;return nil;}
   put32(bytes,metadataOffset,newCount);
   event[@"original_instruction_count"]=@(originalCount);event[@"normalized_instruction_count"]=@(newCount);
   bool unchanged=true;for(size_t i=4;i<metadata.size;i++)if(bytes[metadataOffset+i]!=b[metadata.payload+i])unchanged=false;
   event[@"native_metadata_preserved_except_instruction_count"]=@(unchanged);
  }else{
   put32(bytes,metadataOffset+28,c->config.registers);
   put32(bytes,metadataOffset+36,c->config.launch_word_9);
   put32(bytes,metadataOffset+44,c->config.launch_word_11);
  }
  event[@"all_native_metadata_bytes_preserved"]=@(memcmp(bytes+metadataOffset,b+metadata.payload,metadata.size)==0);
  event[@"original_metadata_sha256_scope"]=@"Full metadata compared to the actual incoming native constructor payload, not copied from an offline file";
  bool preserved=true;
  for(size_t i=0;i<metadata.size;i++)if(!(((keepNativeMetadata||localMemoryContract)&&i<4)||(i>=28&&i<32)||(i>=36&&i<40)||(i>=44&&i<48))&&bytes[metadataOffset+i]!=b[metadata.payload+i])preserved=false;
  [c->payloads addObject:patched];passed=patched.bytes;size=patched.length;
  event[@"registers"]=@(c->config.registers);event[@"code_bytes"]=@(c->code.length);
  event[@"launch_words_9_11"]=@[@(u32(bytes,metadataOffset+36)),@(u32(bytes,metadataOffset+44))];
  event[@"code_payload_offset"]=@(code.payload);event[@"stage"]=@(c->expectedStage);event[@"prefix_bytes"]=@(c->prefixBytes);event[@"code_replaced"]=@YES;
  event[@"imported_code_identical"]=@(memcmp(bytes+code.payload+c->prefixBytes,c->code.bytes,c->code.length)==0);
  event[@"original_graphics_header_preserved"]=@(c->prefixBytes==0||memcmp(bytes+code.payload,b+code.payload,c->prefixBytes)==0);
  event[@"metadata_bytes_preserved_except_import_fields"]=@(preserved);
  event[@"code_identity_scope"]=@"constructor input payload, not a readback of resident GPU instructions";
  if(!preserved)c->rejected=true;
 }
 if(!valid)c->rejected=true;
 id result=((id(*)(id,SEL,const void*,NSUInteger,id))native)(self,selector,passed,size,device);
 if(result&&patched){
  Ivar ivar=class_getInstanceVariable(object_getClass(result),"_variant");uintptr_t pointer=0;
  bool ivarQualified=ivar&&ivar_getOffset(ivar)==32&&ivar_getTypeEncoding(ivar)&&ivar_getTypeEncoding(ivar)[0]=='^'&&class_getInstanceSize(object_getClass(result))>=40;
  if(ivarQualified)memcpy(&pointer,(const char*)result+32,8);
  unsigned char variant[128]={};mach_vm_size_t read=0;
  kern_return_t status=pointer?mach_vm_read_overwrite(mach_task_self(),pointer,sizeof variant,(mach_vm_address_t)variant,&read):KERN_INVALID_ADDRESS;
  if(status==KERN_SUCCESS&&read==sizeof variant){
   event[@"decoded_code_bytes"]=@(u64(variant,24));event[@"decoded_registers"]=@(u32(variant,48));event[@"decoded_instruction_count"]=@(u32(variant,44));
   // Expose decoded native allocation without changing it. Preserving imports
   // can compare the actual allocation to a separately observed carrier.
   event[@"decoded_allocation_word_40"]=@(u32(variant,40));event[@"decoded_spill_bytes_56"]=@(u32(variant,56));
   if(keepNativeMetadata&&u32(variant,44)!=c->code.length/8-1)c->rejected=true;
   if(localMemoryContract){
    // Qualified tuples: native local allocation plus the fixed word11=576
    // reservation contributes another 1024 to this decoded allocation word.
    // Observed independently for 0-byte and 128-byte native local frames.
    uint32_t allocation=((localMemoryContract->carrier_local_bytes*64+1023)&~1023u)+1536;
   bool decoded=u32(variant,40)==allocation&&u32(variant,56)==localMemoryContract->carrier_spill_bytes&&u32(variant,44)==c->code.length/8-1;
   event[@"decoded_control_words_32_36"]=@[@(u32(variant,32)),@(u32(variant,36))];
    event[@"decoded_local_allocation_word"]=@(u32(variant,40));event[@"decoded_native_spill_bytes"]=@(u32(variant,56));event[@"decoded_local_contract_verified"]=@(decoded);
    if(!decoded)c->rejected=true;
   }
   bool accepted=u64(variant,24)==c->code.length+c->prefixBytes&&u32(variant,48)==c->config.registers;
   if(accepted){c->verified=true;c->verifiedImports++;}else c->rejected=true;
  }else c->rejected=true;
 }
 if(patched&&memcmp((const unsigned char*)patched.bytes+code.payload+c->prefixBytes,c->code.bytes,c->code.length)){c->rejected=true;event[@"code_input_unchanged_after_constructor"]=@NO;}
 else if(patched)event[@"code_input_unchanged_after_constructor"]=@YES;
 if(patched&&!result)c->rejected=true;
 [c->events addObject:event];return result;
}
void fail(NSError**error,NSString*message){if(error)*error=[NSError errorWithDomain:@"KeplerProgramImport" code:1 userInfo:@{NSLocalizedDescriptionKey:message}];}
bool complete(const Context&c){return c.verified&&!c.rejected&&c.targetImports>0&&c.targetImports==c.verifiedImports;}
const char*qualifiedDriver="/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver";
const char*qualifiedHash="2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054";
bool driverProfile(IMP implementation,NSError**error,NSString**actualHash=nullptr){
 Dl_info image={};
 if(!dladdr((const void*)implementation,&image)||!image.dli_fname||strcmp(image.dli_fname,qualifiedDriver)){fail(error,@"Unexpected constructor implementation image");return false;}
 NSData *driver=[NSData dataWithContentsOfFile:@(qualifiedDriver)];
 if(!driver.length||driver.length>UINT32_MAX){fail(error,@"Cannot validate qualified driver image");return false;}
 unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(driver.bytes,(CC_LONG)driver.length,digest);char hex[65];
 for(unsigned i=0;i<sizeof digest;i++)sprintf(hex+i*2,"%02x",digest[i]);hex[64]=0;
 if(!KPKeplerDriverHashIsQualified([NSString stringWithUTF8String:hex])){fail(error,@"Installed driver hash differs from qualified profile; import prohibited");return false;}
 if(actualHash)*actualHash=[NSString stringWithUTF8String:hex];
 return true;
}
}

extern "C" id<MTLComputePipelineState> KPInternalCASCreatePipeline(id<MTLDevice> device,NSURL*carrierLibrary,NSString*function,NSData*sm30Code,KeplerImportConfig config,NSError**error,NSDictionary**evidence){
 if(error)*error=nil;if(evidence)*evidence=nil;
 if(activeContext||nativeAllocationScopeActive){fail(error,@"Nested import context");return nil;}
 sm30Code=[[sm30Code copy]autorelease];
 if(!KPKepler880MIdentity(device)||!sm30Code.length||sm30Code.length%64||sm30Code.length>65536||config.registers<24||config.registers>63){fail(error,@"Unqualified GPU, code size or register contract");return nil;}
 if((config.launch_word_9!=0&&config.launch_word_9!=576)||(config.launch_word_11!=0&&config.launch_word_11!=576)){fail(error,@"Unqualified launch metadata values");return nil;}
 std::lock_guard<std::mutex>lock(importMutex);
 Class cls=objc_getClass("NVMTLFunctionVariant");Method method=class_getInstanceMethod(cls,sel_registerName("initWithCompilerOutput:size:device:"));
 if(!method||strcmp(method_getTypeEncoding(method),"@40@0:8r^v16Q24@32")){fail(error,@"Unexpected NVIDIA constructor ABI");return nil;}
 NSString*actualDriverHash=nil;IMP saved=method_getImplementation(method);if(!driverProfile(saved,error,&actualDriverHash))return nil;
 Context context{sm30Code,config,[NSMutableArray array],[NSMutableArray array],false};
 originalInit.store(saved,std::memory_order_release);activeContext=&context;IMP replaced=method_setImplementation(method,(IMP)importInit);
 if(replaced!=saved){method_setImplementation(method,replaced);activeContext=nullptr;fail(error,@"Constructor changed during import setup");return nil;}
 id<MTLComputePipelineState>pipeline=nil;id<MTLLibrary>library=nil;id<MTLFunction>entry=nil;
 @try {
  if(certifiedSuppliedFunction)entry=[certifiedSuppliedFunction retain];
  else if(certifiedLibraryData){
   NSData *snapshot=certifiedLibraryData;
   dispatch_data_t payload=dispatch_data_create(snapshot.bytes,snapshot.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)snapshot.length;});
   library=[device newLibraryWithData:payload error:error];
   dispatch_release(payload);
  }else library=[device newLibraryWithURL:carrierLibrary error:error];
  if(library)entry=[library newFunctionWithName:function];
  if(entry){
   if(approvedPipelineDescriptor){MTLComputePipelineDescriptor*p=[[approvedPipelineDescriptor copy]autorelease];p.computeFunction=entry;pipeline=[device newComputePipelineStateWithDescriptor:p options:MTLPipelineOptionNone reflection:nullptr error:error];}
   else if(certifiedSuppliedFunction)pipeline=[device newComputePipelineStateWithFunction:entry options:certifiedPipelineOptions reflection:certifiedReflection error:error];
   else pipeline=[device newComputePipelineStateWithFunction:entry error:error];
  }
 } @catch(NSException*exception){fail(error,exception.reason?:@"Pipeline exception");}
 @finally {method_setImplementation(method,saved);activeContext=nullptr;}
 bool constructorRestored=method_getImplementation(method)==saved;
 if(!constructorRestored)context.rejected=true;
 [entry release];[library release];
 if(evidence)*evidence=@{@"device":device.name,@"registry_id":@(device.registryID),@"contract_verified":@(complete(context)),@"constructor_restored":@(constructorRestored),@"target_imports":@(context.targetImports),@"verified_imports":@(context.verifiedImports),@"rejected_import":@(context.rejected),@"driver_sha256":actualDriverHash,@"events":context.events,@"scope":@"constructor payload and decoded metadata validation; GPU execution requires separate dispatch/result checks"};
 if(pipeline&&!complete(context)){[pipeline release];pipeline=nil;fail(error,@"Decoded program contract did not match; dispatch prohibited");}
 if(pipeline)objc_setAssociatedObject(pipeline,&retainedPayloadKey,context.payloads,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
 return pipeline;
}

// Opt-in native allocation preservation. Uses the same serialization and
// constructor restoration as CAS/approved imports; the legacy ABI is unchanged.
extern "C" id<MTLComputePipelineState> KPCreateLocalMemoryPipeline(
 id<MTLDevice>device,NSData*library,NSString*function,NSData*code,
 KeplerLocalMemoryConfig config,NSError**error,NSDictionary**evidence){
 if(error)*error=nil;if(evidence)*evidence=nil;
 if(![library isKindOfClass:NSData.class]||!library.length||library.length>UINT32_MAX||
    ![code isKindOfClass:NSData.class]||!code.length||code.length%64||code.length>65536||
    config.registers<24||config.registers>63||config.required_scratch_bytes>config.carrier_local_bytes||
    activeContext||nativeAllocationScopeActive||expectedNativeOriginal||keepNativeMetadata||certifiedLibraryData||certifiedNativeMetadata||
    certifiedSuppliedFunction||certifiedReflection||approvedPipelineDescriptor||localMemoryContract){fail(error,@"Invalid local-memory import or nested context");return nil;}
 uint32_t bytes=0,spill=0,barriers=0;
 if([function isEqual:@"local_control"]){}
 else if([function isEqual:@"local32"])bytes=128;
 else if([function isEqual:@"local256"])bytes=1024;
 else if([function isEqual:@"local1024"])bytes=4096;
 else if([function isEqual:@"local2048"])bytes=8192;
 else if([function isEqual:@"local4096"])bytes=16384;
 else if([function isEqual:@"pressure96"]){bytes=224;spill=224;barriers=1;}
 else{fail(error,@"Native local-memory carrier function is not qualified");return nil;}
 if(config.carrier_local_bytes!=bytes||config.carrier_spill_bytes!=spill||config.carrier_control_barriers!=barriers){fail(error,@"Native local-memory profile differs");return nil;}
 NSData*snapshot=[[NSData alloc]initWithBytes:library.bytes length:library.length];
 unsigned char digest[32];CC_SHA256(snapshot.bytes,(CC_LONG)snapshot.length,digest);char hex[65];for(unsigned i=0;i<32;i++)sprintf(hex+i*2,"%02x",digest[i]);hex[64]=0;
 if(strcmp(hex,bytes>4096?"62a49cf2ea3a3e4daec94cb7cf6c35abb2828101b74c47a8ea6d16d042137424":"bb052086f1a0f8ce1a2cad8da00c74926ac47abe0d0b95d3b1f66cf24f4d3d5d")){[snapshot release];fail(error,@"Native local-memory library fingerprint differs");return nil;}
 id<MTLComputePipelineState>pipeline=nil;
 @try{certifiedLibraryData=snapshot;localMemoryContract=&config;pipeline=KPInternalCASCreatePipeline(device,nil,function,code,{config.registers,0,0},error,evidence);}
 @finally{localMemoryContract=nullptr;certifiedLibraryData=nil;[snapshot release];}
 return pipeline;
}

// Internal shared import entry for approved non-CAS SDK programs. The same
// importMutex and restoration path serialize this with certified CAS imports.
// Immutable library bytes avoid reopening a mutable carrier path during import.
extern "C" id<MTLComputePipelineState> KPInternalCreateApprovedSM30Pipeline(
 id<MTLDevice>device,NSData*library,NSString*function,NSData*code,
 KeplerImportConfig config,NSError**error,NSDictionary**evidence){
 if(error)*error=nil;if(evidence)*evidence=nil;
 if(activeContext||nativeAllocationScopeActive||!library.length||library.length>UINT32_MAX||expectedNativeOriginal||keepNativeMetadata||
    certifiedLibraryData||certifiedNativeMetadata||certifiedSuppliedFunction||certifiedReflection||approvedPipelineDescriptor){
  fail(error,@"Missing carrier or nested import context");return nil;
 }
 NSData*snapshot=[library copy];id<MTLComputePipelineState>pipeline=nil;
 @try {certifiedLibraryData=snapshot;pipeline=KPInternalCASCreatePipeline(device,nil,function,code,config,error,evidence);}
 @finally {certifiedLibraryData=nil;[snapshot release];}
 return pipeline;
}

// Descriptor variant for approved command producers. Snapshot both inputs;
// constructor serialization/restoration remains in the existing MRC transport.
extern "C" id<MTLComputePipelineState> KPInternalCreateApprovedSM30PipelineWithDescriptor(
 id<MTLDevice>device,NSData*library,NSString*function,NSData*code,
 KeplerImportConfig config,MTLComputePipelineDescriptor*descriptor,NSError**error,NSDictionary**evidence){
 if(error)*error=nil;if(evidence)*evidence=nil;
 if(activeContext||nativeAllocationScopeActive||!library.length||library.length>UINT32_MAX||!descriptor||expectedNativeOriginal||keepNativeMetadata||
    certifiedLibraryData||certifiedNativeMetadata||certifiedSuppliedFunction||certifiedReflection||approvedPipelineDescriptor){fail(error,@"Missing descriptor/carrier or nested import context");return nil;}
 NSData*snapshot=[library copy];MTLComputePipelineDescriptor*settings=[descriptor copy];id<MTLComputePipelineState>pipeline=nil;
 @try{certifiedLibraryData=snapshot;approvedPipelineDescriptor=settings;pipeline=KPInternalCASCreatePipeline(device,nil,function,code,config,error,evidence);}
 @finally{approvedPipelineDescriptor=nil;certifiedLibraryData=nil;[settings release];[snapshot release];}
 return pipeline;
}

static id<MTLRenderPipelineState> createGraphicsStage(id<MTLDevice>device,MTLRenderPipelineDescriptor*descriptor,NSData*code,KeplerImportConfig config,uint32_t stage,NSError**error,NSDictionary**evidence,NSData*vertex=nil,KeplerImportConfig vertexConfig={}){
 if(error)*error=nil;if(evidence)*evidence=nil;
 if(activeContext||nativeAllocationScopeActive){fail(error,@"Nested graphics import context");return nil;}
 code=[[code copy]autorelease];vertex=[[vertex copy]autorelease];
 if(!KPKepler880MIdentity(device)||!code.length||code.length%64||code.length>65536||config.registers<1||config.registers>63){fail(error,@"Unqualified render GPU, code or register contract");return nil;}
 if(config.launch_word_9||config.launch_word_11){fail(error,@"Graphics control-stack metadata not yet qualified");return nil;}
 if(vertex&&(!vertex.length||vertex.length%64||vertex.length>65536||vertexConfig.registers<1||vertexConfig.registers>63||vertexConfig.launch_word_9||vertexConfig.launch_word_11)){fail(error,@"Unqualified additional vertex contract");return nil;}
 std::lock_guard<std::mutex>lock(importMutex);
 Class cls=objc_getClass("NVMTLFunctionVariant");Method method=class_getInstanceMethod(cls,sel_registerName("initWithCompilerOutput:size:device:"));
 if(!method||strcmp(method_getTypeEncoding(method),"@40@0:8r^v16Q24@32")){fail(error,@"Unexpected NVIDIA graphics constructor ABI");return nil;}
 NSString*actualDriverHash=nil;IMP saved=method_getImplementation(method);if(!driverProfile(saved,error,&actualDriverHash))return nil;
 Context context{code,config,[NSMutableArray array],[NSMutableArray array],false,stage,80};
 context.additionalVertex=vertex;context.vertexConfig=vertexConfig;
 originalInit.store(saved,std::memory_order_release);activeContext=&context;IMP replaced=method_setImplementation(method,(IMP)importInit);
 if(replaced!=saved){method_setImplementation(method,replaced);activeContext=nullptr;fail(error,@"Graphics constructor changed during import setup");return nil;}
 id<MTLRenderPipelineState>pipeline=nil;
 @try {pipeline=[device newRenderPipelineStateWithDescriptor:descriptor error:error];}
 @catch(NSException*exception){fail(error,exception.reason?:@"Render pipeline exception");}
 @finally {method_setImplementation(method,saved);activeContext=nullptr;}
 bool constructorRestored=method_getImplementation(method)==saved;
 if(!constructorRestored)context.rejected=true;
 bool verified=complete(context)&&(!vertex||context.vertexVerified)&&constructorRestored;
 if(evidence)*evidence=@{@"device":device.name,@"registry_id":@(device.registryID),@"driver_sha256":actualDriverHash,@"contract_verified":@(verified),@"constructor_restored":@(constructorRestored),@"events":context.events,@"scope":vertex?@"own-process vertex and fragment import; native headers and installed driver transport preserved":(stage==2?@"own-process tessellation evaluation import; native tessellator/header/fragment preserved":(stage==0?@"own-process vertex import; native fragment/header transport preserved":@"own-process fragment import; native vertex/header transport preserved"))};
 if(pipeline&&!verified){[pipeline release];pipeline=nil;fail(error,@"Decoded graphics contract mismatch; draw prohibited");}
 if(pipeline)objc_setAssociatedObject(pipeline,&retainedPayloadKey,context.payloads,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
 return pipeline;
}
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateRenderPipeline(id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*c,KeplerImportConfig f,NSError**e,NSDictionary**v){return createGraphicsStage(d,p,c,f,4,e,v);}
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateVertexPipeline(id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*c,KeplerImportConfig f,NSError**e,NSDictionary**v){return createGraphicsStage(d,p,c,f,0,e,v);}
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateTessellationPipeline(id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*c,KeplerImportConfig f,NSError**e,NSDictionary**v){if(p.vertexFunction.patchType==MTLPatchTypeNone){fail(e,@"Post-tessellation patch function required");return nil;}return createGraphicsStage(d,p,c,f,2,e,v);}
extern "C" id<MTLRenderPipelineState> KPInternalCASCreateGraphicsPipeline(id<MTLDevice>d,MTLRenderPipelineDescriptor*p,NSData*vc,KeplerImportConfig vf,NSData*fc,KeplerImportConfig ff,NSError**e,NSDictionary**v){return createGraphicsStage(d,p,fc,ff,4,e,v,vc,vf);}

extern "C" id<MTLBuffer> KPInternalCASCreateHostBuffer(id<MTLDevice>device,const void*initialBytes,NSUInteger length,bool noCopy){
 if(!device||!length)return nil;
 if(!noCopy){
  id<MTLBuffer>buffer=[device newBufferWithLength:length options:MTLResourceStorageModeManaged];
  if(buffer&&initialBytes){memcpy(buffer.contents,initialBytes,length);[buffer didModifyRange:NSMakeRange(0,length)];}
  return buffer;
 }
 size_t page=(size_t)sysconf(_SC_PAGESIZE);
 if(length>SIZE_MAX-(page-1))return nil;
 size_t rounded=(length+page-1)/page*page;void*pointer=nullptr;
 if(posix_memalign(&pointer,page,rounded))return nil;
 if(initialBytes)memcpy(pointer,initialBytes,length);
 id<MTLBuffer>buffer=[device newBufferWithBytesNoCopy:pointer length:rounded options:MTLResourceStorageModeShared deallocator:^(void*p,NSUInteger bytes){(void)bytes;free(p);}];
 if(!buffer){free(pointer);return nil;}
 if(buffer.contents!=pointer||buffer.storageMode!=MTLStorageModeShared){[buffer release];return nil;}
 return buffer;
}

extern "C" id<MTLComputePipelineState> KPInternalCASCreatePinnedNativeCASPipeline(
 id<MTLDevice>device,NSURL*library,NSString*function,NSData*originalCode,NSData*newCode,
 KeplerImportConfig config,NSError**error,NSDictionary**evidence){
 if(activeContext||nativeAllocationScopeActive||expectedNativeOriginal||!originalCode.length){fail(error,@"Missing or nested native input contract");return nil;}
 expectedNativeOriginal=originalCode;
 @try{return KPInternalCASCreatePipeline(device,library,function,newCode,config,error,evidence);}
 @finally{expectedNativeOriginal=nullptr;}
}

extern "C" id<MTLComputePipelineState> KPInternalCASCreatePreservingNativeCASPipeline(
 id<MTLDevice>d,NSURL*l,NSString*f,NSData*original,NSData*replacement,NSError**error,NSDictionary**proof){
 if(activeContext||nativeAllocationScopeActive||keepNativeMetadata){fail(error,@"Nested native preservation context");return nil;}
 keepNativeMetadata=true;
 @try{return KPInternalCASCreatePinnedNativeCASPipeline(d,l,f,original,replacement,{24,576,576},error,proof);}
 @finally{keepNativeMetadata=false;}
}

#include "KeplerNativeCASAdapter.inc"
#include "KeplerNativeAllocation.inc"
