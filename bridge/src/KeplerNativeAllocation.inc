// SPDX-License-Identifier: MIT
// Included by KeplerNativeCAS.mm; MRC, common importMutex and ABI parser.
#import "KeplerNativeAllocation.h"
#include <cmath>

namespace kpNativeAllocation {
struct State {
    NSData *metadata;
    NSString *codeHash;
    uint32_t codeBytes, reserve;
    NSMutableArray *events, *payloads;
    unsigned calls=0;
    bool rejected=false;
};
static thread_local State *current=nullptr;
static std::atomic<IMP> original{nullptr};
static std::atomic<uint64_t> passthroughCalls{0};
static char retainedInputsKey;

static bool number(id value, uint32_t &out) {
    if(![value isKindOfClass:NSNumber.class] ||
       CFGetTypeID((CFTypeRef)value)==CFBooleanGetTypeID())return false;
    double d=[value doubleValue];
    if(!std::isfinite(d)||d<0||d>UINT32_MAX||d!=std::floor(d))return false;
    out=(uint32_t)[value unsignedLongLongValue];return true;
}

static bool codeDigest(id value) {
    if(![value isKindOfClass:NSString.class]||[value length]!=64)return false;
    NSCharacterSet *invalid=[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"]invertedSet];
    return [value rangeOfCharacterFromSet:invalid].location==NSNotFound;
}

static id initialize(id self, SEL selector, const void *input, NSUInteger length, id device) {
    IMP native=original.load(std::memory_order_acquire);
    if(!native)return nil;
    State *s=current;
    if(!s) {
        passthroughCalls.fetch_add(1,std::memory_order_relaxed);
        return ((id(*)(id,SEL,const void*,NSUInteger,id))native)(self,selector,input,length,device);
    }
    s->calls++;
    NSData *snapshot=(input&&length<=8*1024*1024)?[NSData dataWithBytes:input length:length]:nil;
    const auto *b=(const unsigned char*)snapshot.bytes;
    std::vector<Section> sections;
    bool valid=snapshot&&parse(b,length,sections);
    Section metadata={},code={};unsigned nm=0,nc=0;
    if(valid) {
        valid=sections.front().type==1&&sections.front().size==4&&
              u32(b,sections.front().payload)==5;
        for(const auto &section:sections) {
            if(section.type==0x10004){metadata=section;nm++;}
            if(section.type==0x10005){code=section;nc++;}
        }
    }
    valid=valid&&nm==1&&nc==1&&metadata.size==232&&code.size==s->codeBytes&&
          code.size&&code.size%64==0;
    const bool parsed=valid;
    bool metadataMatch=valid,codeMatch=false;
    NSMutableArray *words=[NSMutableArray array];NSString *actualHash=@"";
    if(valid) {
        for(unsigned i=0;i<58;i++) {
            uint32_t value=u32(b,metadata.payload+4*i);[words addObject:@(value)];
            // Unknown variable words are preserved, never filled from a pin.
            if(i!=2&&i!=4&&value!=u32((const unsigned char*)s->metadata.bytes,4*i))metadataMatch=false;
        }
        actualHash=kpCASDigest([snapshot subdataWithRange:NSMakeRange(code.payload,code.size)]);
        codeMatch=[actualHash isEqual:s->codeHash];
    }
    valid=valid&&metadataMatch&&codeMatch;
    uint32_t oldControl=valid?u32(b,metadata.payload+44):0;
    uint32_t frame=valid?u32(b,metadata.payload+48):0;
    valid=valid&&s->reserve==4096&&oldControl<=s->reserve&&frame<=4656&&
          u32(b,metadata.payload+36)==frame*64+oldControl&&
          u32(b,metadata.payload+52)==frame&&u32(b,metadata.payload+56)<=frame&&
          u32(b,metadata.payload)==code.size/8-1;
    NSMutableDictionary *event=[NSMutableDictionary dictionaryWithDictionary:@{
        @"parsed":@(parsed),@"certificate_matches":@(valid),@"metadata_match":@(metadataMatch),
        @"code_match":@(codeMatch),@"actual_code_SHA256":actualHash,@"actual_metadata_words":words,
        @"metadata_sections":@(nm),@"code_sections":@(nc),@"requested_reserve":@(s->reserve)}];
    NSMutableData *patched=nil;NSString *passedHash=@"";
    if(valid) {
        patched=[NSMutableData dataWithData:snapshot];auto *bytes=(unsigned char*)patched.mutableBytes;
        put32(bytes,metadata.payload+36,frame*64+s->reserve);
        put32(bytes,metadata.payload+44,s->reserve);
        bool same=true;
        for(size_t i=0;i<length;i++)
            if(!((i>=metadata.payload+36&&i<metadata.payload+40)||
                 (i>=metadata.payload+44&&i<metadata.payload+48))&&b[i]!=bytes[i])same=false;
        bool sameCode=memcmp(b+code.payload,bytes+code.payload,code.size)==0;
        event[@"only_metadata_words9_11_changed"]=@(same);
        event[@"native_code_identical"]=@(sameCode);
        event[@"old_control"]=@(oldControl);event[@"new_control"]=@(s->reserve);
        event[@"native_frame"]=@(frame);event[@"native_GPR"]=@(u32(b,metadata.payload+28));
        event[@"code_bytes"]=@(code.size);
        valid=valid&&same&&sameCode;passedHash=kpCASDigest(patched);[s->payloads addObject:patched];
    }
    if(!valid)s->rejected=true;
    // A refused contract always passes the untouched native input to the driver.
    id result=((id(*)(id,SEL,const void*,NSUInteger,id))native)(self,selector,
                  valid?patched.bytes:input,length,device);
    if(result&&valid) {
        NSString *postCode=kpCASDigest([patched subdataWithRange:NSMakeRange(code.payload,code.size)]);
        bool sameCode=[postCode isEqual:s->codeHash],samePayload=[kpCASDigest(patched)isEqual:passedHash];
        event[@"native_code_identical_after_constructor"]=@(sameCode);
        event[@"post_constructor_code_SHA256"]=postCode;
        event[@"payload_unchanged_after_constructor"]=@(samePayload);
        event[@"patched_payload_SHA256"]=passedHash;event[@"input_snapshot_SHA256"]=kpCASDigest(snapshot);
        Ivar ivar=class_getInstanceVariable(object_getClass(result),"_variant");uintptr_t pointer=0;
        bool layout=ivar&&ivar_getOffset(ivar)==32&&ivar_getTypeEncoding(ivar)&&
                    ivar_getTypeEncoding(ivar)[0]=='^'&&class_getInstanceSize(object_getClass(result))>=40;
        if(layout)memcpy(&pointer,(const char*)result+32,8);
        unsigned char v[128]={};mach_vm_size_t read=0;
        kern_return_t status=pointer?mach_vm_read_overwrite(mach_task_self(),pointer,sizeof(v),(mach_vm_address_t)v,&read):KERN_INVALID_ADDRESS;
        uint32_t allocation=((frame+15)&~15u)*64+4096+512;
        bool decoded=status==KERN_SUCCESS&&read==sizeof(v)&&u64(v,24)==code.size&&
                     u32(v,44)==u32(b,metadata.payload)&&u32(v,48)==u32(b,metadata.payload+28)&&
                     u32(v,56)==u32(b,metadata.payload+56)&&u32(v,40)==allocation;
        event[@"decoded_contract_verified"]=@(decoded);
        event[@"decoded_allocation_word40"]=@(u32(v,40));event[@"expected_allocation_word40"]=@(allocation);
        event[@"decoded_spill_bytes56"]=@(u32(v,56));
        if(!sameCode||!samePayload||!decoded)s->rejected=true;
    }else s->rejected=true;
    [s->events addObject:event];return result;
}
}

extern "C" id<MTLComputePipelineState> KPCreateCertifiedNativeAllocationPipeline(
 id<MTLDevice>device,NSData*libraryData,NSString*expectedLibrarySHA256,
 NSData*certificateData,NSString*expectedCertificateSHA256,NSError**error,NSDictionary**evidence) {
    if(error)*error=nil;if(evidence)*evidence=@{@"gate_accepted":@NO,@"constructor_entered":@NO};
    if(!device||![device.name isEqual:@"NVIDIA GeForce GTX 880M"]||device.registryID!=4294968458||
       ![libraryData isKindOfClass:NSData.class]||!libraryData.length||libraryData.length>64*1024*1024||
       ![certificateData isKindOfClass:NSData.class]||!certificateData.length||certificateData.length>1024*1024) {
        fail(error,@"Unqualified native allocation input/device");return nil;
    }
    // Concrete immutable copies, not caller-controlled NSData subclasses.
    NSData *library=[NSData dataWithBytes:libraryData.bytes length:libraryData.length];
    NSData *certificate=[NSData dataWithBytes:certificateData.bytes length:certificateData.length];
    if(!kpCASHash(library,expectedLibrarySHA256)||!kpCASHash(certificate,expectedCertificateSHA256)) {
        fail(error,@"Native allocation input fingerprint differs");return nil;
    }
    id<MTLComputePipelineState>pipeline=nil;id<MTLLibrary>nativeLibrary=nil;id<MTLFunction>function=nil;
    @try {
        id parsed=[NSJSONSerialization JSONObjectWithData:certificate options:0 error:error];
        if(![parsed isKindOfClass:NSDictionary.class]){fail(error,@"Native allocation certificate object required");return nil;}
        NSDictionary *cert=parsed;uint32_t schema=0,reserve=0,codeBytes=0;
        NSArray *words=cert[@"metadata_words"];NSString *name=cert[@"function"],*codeHash=cert[@"native_code_sha256"];
        bool valid=kpNativeAllocation::number(cert[@"schema"],schema)&&schema==1&&
            [cert[@"intent"]isEqual:@"native_control_reservation"]&&
            [name isKindOfClass:NSString.class]&&name.length&&name.length<=255&&
            [cert[@"driver_sha256"]isEqual:@(qualifiedHash)]&&kpCASHash(library,cert[@"library_sha256"])&&
            [words isKindOfClass:NSArray.class]&&words.count==58&&kpNativeAllocation::codeDigest(codeHash)&&
            kpNativeAllocation::number(cert[@"code_bytes"],codeBytes)&&codeBytes>=64&&codeBytes<=104000&&codeBytes%64==0&&
            kpNativeAllocation::number(cert[@"control_reserve"],reserve)&&reserve==4096;
        uint32_t w[58]={};
        if(valid)for(unsigned i=0;i<58;i++)if(!kpNativeAllocation::number(words[i],w[i]))valid=false;
        valid=valid&&w[0]==codeBytes/8-1&&w[7]>=1&&w[7]<=63&&w[12]<=4656&&
              w[12]==w[13]&&w[14]<=w[12]&&w[11]<=4096&&w[9]==64*w[12]+w[11];
        if(!valid){fail(error,@"Native allocation schema/profile refused");return nil;}
        if(nativeAllocationScopeActive||activeContext||expectedNativeOriginal||keepNativeMetadata||
           certifiedLibraryData||certifiedNativeMetadata||certifiedSuppliedFunction||certifiedReflection||
           certifiedPipelineOptions!=MTLPipelineOptionNone||
           approvedPipelineDescriptor||localMemoryContract||kpNativeAllocation::current) {
            fail(error,@"Nested native allocation/import scope refused");return nil;
        }
        NSData *metadata=[NSData dataWithBytes:w length:sizeof(w)];
        std::lock_guard<std::mutex>lock(importMutex);
        Method method=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));
        if(!method||strcmp(method_getTypeEncoding(method),"@40@0:8r^v16Q24@32")) {
            fail(error,@"Unexpected native allocation constructor ABI");return nil;
        }
        IMP saved=method_getImplementation(method);if(!driverProfile(saved,error))return nil;
        kpNativeAllocation::State state{metadata,codeHash,codeBytes,reserve,[NSMutableArray array],[NSMutableArray array]};
        uint64_t beforePassthrough=kpNativeAllocation::passthroughCalls.load(std::memory_order_relaxed);
        kpNativeAllocation::original.store(saved,std::memory_order_release);
        kpNativeAllocation::current=&state;nativeAllocationScopeActive=true;
        IMP previous=method_setImplementation(method,(IMP)kpNativeAllocation::initialize);
        if(previous!=saved) {
            method_setImplementation(method,previous);kpNativeAllocation::current=nullptr;nativeAllocationScopeActive=false;
            fail(error,@"Native allocation constructor changed during setup");return nil;
        }
        @try {
            dispatch_data_t payload=dispatch_data_create(library.bytes,library.length,
                dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)library.length;});
            nativeLibrary=[device newLibraryWithData:payload error:error];dispatch_release(payload);
            if(nativeLibrary)function=[nativeLibrary newFunctionWithName:name];
            if(function)pipeline=[device newComputePipelineStateWithFunction:function error:error];
        }@catch(NSException*exception) {
            state.rejected=true;fail(error,exception.reason?:@"Native allocation pipeline exception");
        }@finally {
            method_setImplementation(method,saved);kpNativeAllocation::current=nullptr;nativeAllocationScopeActive=false;
        }
        bool restored=method_getImplementation(method)==saved;
        bool verified=pipeline&&state.calls==1&&!state.rejected&&restored;
        if(evidence)*evidence=@{@"gate_accepted":@YES,@"constructor_entered":@(state.calls>0),
            @"contract_verified":@(verified),@"constructor_restored":@(restored),@"calls":@(state.calls),
            @"events":state.events,@"native_program_replaced":@NO,@"system_modified":@NO,
            @"immutable_library_data":@YES,@"inputs_snapshotted":@YES,@"shares_import_mutex":@YES,
            @"thread_local_scope":@YES,@"function":name,@"library_SHA256":kpCASDigest(library),
            @"unrelated_constructor_passthrough_calls":@(kpNativeAllocation::passthroughCalls.load(std::memory_order_relaxed)-beforePassthrough),
            @"certificate_SHA256":kpCASDigest(certificate)};
        if(!verified) {
            if(pipeline){[pipeline release];pipeline=nil;}
            if(!error||!*error)fail(error,@"Native allocation contract failed or constructor callback missing; dispatch prohibited");
        }
        if(pipeline)objc_setAssociatedObject(pipeline,&kpNativeAllocation::retainedInputsKey,
            @[library,certificate,state.payloads],OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }@catch(NSException*exception) {
        if(pipeline){[pipeline release];pipeline=nil;}
        fail(error,exception.reason?:@"Invalid native allocation certificate");
    }@finally {
        [function release];[nativeLibrary release];
    }
    return pipeline;
}
