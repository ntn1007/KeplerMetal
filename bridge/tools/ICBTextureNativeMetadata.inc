// SPDX-License-Identifier: MIT
// Existing own-process ABI reader, frozen for the argument-resource probe.
#include <mach/mach_vm.h>
#include <cstring>
static NSData *readMemory(uintptr_t address,size_t bytes) {
 if(!address||!bytes||bytes>65536||address+bytes<address)return nil;
 NSMutableData*data=[NSMutableData dataWithLength:bytes];mach_vm_size_t read=0;
 return mach_vm_read_overwrite(mach_task_self(),address,bytes,(mach_vm_address_t)data.mutableBytes,&read)==KERN_SUCCESS&&read==bytes?data:nil;
}
static uint32_t u32(NSData*d,size_t at){uint32_t v=0;if(at+4<=d.length)memcpy(&v,(const char*)d.bytes+at,4);return v;}
static uint64_t u64(NSData*d,size_t at){uint64_t v=0;if(at+8<=d.length)memcpy(&v,(const char*)d.bytes+at,8);return v;}
static NSString*sha(NSData*d){if(!d)return @"";unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString string];for(unsigned char x:h)[s appendFormat:@"%02x",x];return s;}
static id json(NSData*d){return d?[NSJSONSerialization JSONObjectWithData:d options:0 error:nil]:nil;}
static void emit(NSDictionary*d){NSData*j=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");}
struct Cursor{uintptr_t implementation=0,push=0,current=0,end=0;bool valid=false;};
static Cursor cursor(id<MTLComputeCommandEncoder>encoder) {
 Cursor c;Ivar field=class_getInstanceVariable(object_getClass(encoder),"m_compute");
 if(!field||ivar_getOffset(field)!=120||class_getInstanceSize(object_getClass(encoder))!=128||!ivar_getTypeEncoding(field)||ivar_getTypeEncoding(field)[0]!='^')return c;
 memcpy(&c.implementation,(const char*)(__bridge const void*)encoder+120,8);
 NSData*impl=readMemory(c.implementation,64);if(impl.length!=64)return c;
 c.push=u64(impl,32);NSData*push=readMemory(c.push,144);if(push.length!=144)return c;
 c.current=u64(push,0);c.end=u64(push,136);c.valid=c.current&&c.current<=c.end&&c.end-c.current<=1024*1024;return c;
}
static NSDictionary*info(Cursor c){return @{@"implementation":@(c.implementation),@"push":@(c.push),@"current":@(c.current),@"end":@(c.end),@"valid":@(c.valid)};}
static NSData *variant(id<MTLComputePipelineState>pipeline) {
 if(![NSStringFromClass(object_getClass(pipeline))isEqual:@"NVMTLComputePipelineState"])return nil;
 Ivar field=class_getInstanceVariable(object_getClass(pipeline),"_computePipeline");
 if(!field||ivar_getOffset(field)!=72||!ivar_getTypeEncoding(field)||ivar_getTypeEncoding(field)[0]!='^')return nil;
 uintptr_t ptr=0;memcpy(&ptr,(const char*)(__bridge const void*)pipeline+72,8);NSData*state=readMemory(ptr,32);
 if(state.length!=32||u64(state,8)!=(uintptr_t)(__bridge const void*)pipeline||!u64(state,16))return nil;
 id owner=(__bridge id)(void*)(uintptr_t)u64(state,16);
 if(![NSStringFromClass(object_getClass(owner))isEqual:@"NVMTLFunctionVariant"])return nil;
 field=class_getInstanceVariable(object_getClass(owner),"_variant");
 if(!field||ivar_getOffset(field)!=32||!ivar_getTypeEncoding(field)||ivar_getTypeEncoding(field)[0]!='^')return nil;
 memcpy(&ptr,(const char*)(__bridge const void*)owner+32,8);return readMemory(ptr,128);
}
