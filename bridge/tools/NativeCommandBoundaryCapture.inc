// SPDX-License-Identifier: MIT
// MRC own-process constructor observation. Arguments/return pass untouched.
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#include <mach/mach_vm.h>
static NSData *captureRead(uintptr_t address,size_t size) {
    if(!address||!size||size>8*1024*1024||address+size<address)return nil;
    NSMutableData *data=[NSMutableData dataWithLength:size];mach_vm_size_t bytes=0;
    return mach_vm_read_overwrite(mach_task_self(),address,size,(mach_vm_address_t)data.mutableBytes,&bytes)==KERN_SUCCESS&&bytes==size?data:nil;
}
static uint64_t captureWord(NSData *data,size_t at) {
    uint64_t value=0;if(at+8<=data.length)memcpy(&value,(const char*)data.bytes+at,8);return value;
}
static IMP captureOriginal;
static Method captureMethod;
static NSString *captureDirectory;
static NSMutableArray *captureRecords;
static NSString *captureSHA(NSData *data) {
    unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);
    NSMutableString *s=[NSMutableString string];for(unsigned char c:h)[s appendFormat:@"%02x",c];return s;
}
static id captureCompilerOutput(id object,SEL selector,const void *input,NSUInteger size,id device) {
    NSData *snapshot=nil;NSString *file=nil;
    if(input&&size&&size<=8*1024*1024){
        snapshot=[NSData dataWithBytes:input length:size];
        file=[NSString stringWithFormat:@"program-%lu.compiler-output.bin",(unsigned long)captureRecords.count];
    }
    BOOL saved=snapshot&&[snapshot writeToFile:[captureDirectory stringByAppendingPathComponent:file]atomically:YES];
    id result=((id(*)(id,SEL,const void*,NSUInteger,id))captureOriginal)(object,selector,input,size,device);
    NSMutableDictionary *record=[@{@"file":file?:@"",@"bytes":@(size),@"saved":@(saved),
        @"SHA256":snapshot?captureSHA(snapshot):@"",@"constructor_returned_nonnull":@(result!=nil),
        @"inputs_replaced":@NO}mutableCopy];
    // Static evidence on the exact driver profile maps this CPU staging copy
    // to variant+0x8a8, with its byte count at +24. Read only our own object.
    Ivar ivar=result?class_getInstanceVariable(object_getClass(result),"_variant"):nullptr;
    if(result&&[NSStringFromClass(object_getClass(result))isEqual:@"NVMTLFunctionVariant"]&&
       ivar&&ivar_getOffset(ivar)==32&&ivar_getTypeEncoding(ivar)&&ivar_getTypeEncoding(ivar)[0]=='^'&&
       class_getInstanceSize(object_getClass(result))>=40){
        NSData *pointer=captureRead((uintptr_t)result+32,8);
        NSData *fields=captureRead(captureWord(pointer,0),0x8b0);
        uint64_t bytes=captureWord(fields,24);
        NSData *code=captureRead(captureWord(fields,0x8a8),bytes);
        NSString *name=[file stringByReplacingOccurrencesOfString:@".compiler-output.bin" withString:@".post-constructor-code.bin"];
        BOOL codeSaved=code&&[code writeToFile:[captureDirectory stringByAppendingPathComponent:name]atomically:YES];
        record[@"post_constructor_code_file"]=name?:@"";
        record[@"post_constructor_code_bytes"]=@(bytes);
        record[@"post_constructor_code_SHA256"]=code?captureSHA(code):@"";
        record[@"post_constructor_code_saved"]=@(codeSaved);
        record[@"post_constructor_read_scope"]=@"own CPU staging copy; not resident GPU readback";
    }
    [captureRecords addObject:record];return result;
}
static BOOL beginCapture(NSString *directory) {
    NSData *driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
    if(!driver)return NO;NSString *digest=captureSHA(driver);
    if(![@[@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054",
           @"e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645"]containsObject:digest])return NO;
    captureMethod=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));
    if(!captureMethod||strcmp(method_getTypeEncoding(captureMethod),"@40@0:8r^v16Q24@32"))return NO;
    captureDirectory=directory;captureRecords=[NSMutableArray array];
    captureOriginal=method_setImplementation(captureMethod,(IMP)captureCompilerOutput);
    return captureOriginal!=nullptr;
}
static NSDictionary *finishCapture() {
    BOOL observed=method_getImplementation(captureMethod)==(IMP)captureCompilerOutput;
    method_setImplementation(captureMethod,captureOriginal);
    return @{@"records":captureRecords,@"observer_still_installed_before_restore":@(observed),
        @"constructor_restored":@(method_getImplementation(captureMethod)==captureOriginal),
        @"input_arguments_replaced":@NO,@"capture_stage":@"native_constructor_input_not_resident_code"};
}
