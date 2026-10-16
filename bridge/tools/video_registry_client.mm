// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#include "video_registry_observer.h"
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <cstdint>
#include <cstdarg>
#include <cstring>
#ifndef KPREG_CALIBRATION
#define KPREG_CALIBRATION 0
#endif
extern "C" void KPVideoImagesStart();
extern "C" NSDictionary *KPVideoImagesSnapshot();
static NSString *registryHash(NSData *data){
    if(!data)return @"";unsigned char h[32];CC_SHA256(data.bytes,(CC_LONG)data.length,h);
    NSMutableString *s=[NSMutableString string];for(auto b:h)[s appendFormat:@"%02x",b];return s;
}
static NSData *ownRegion(const uint8_t *p,size_t count){
    mach_vm_address_t base=(mach_vm_address_t)p;mach_vm_size_t size=0;
    vm_region_basic_info_data_64_t info{};mach_msg_type_number_t fields=VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object=MACH_PORT_NULL;auto status=mach_vm_region(mach_task_self(),&base,&size,VM_REGION_BASIC_INFO_64,
        (vm_region_info_t)&info,&fields,&object);if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
    uintptr_t address=(uintptr_t)p;
    if(status||!(info.protection&VM_PROT_READ)||address<base||count>size||address-base>size-count)return nil;
    return [NSData dataWithBytes:p length:count];
}
#if KPREG_CALIBRATION
__attribute__((noinline)) static uint64_t integers(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f,
    uint64_t g,uint64_t h,uint64_t i,uint64_t j,uint64_t k,uint64_t l){
    return a^(3*b)^(5*c)^(7*d)^(11*e)^(13*f)^(17*g)^(19*h)^(23*i)^(29*j)^(31*k)^(37*l);
}
__attribute__((noinline)) static double floating(double a,double b,double c,double d,double e,double f,
    double g,double h,double i,double j){return a+2*b+3*c+4*d+5*e+6*f+7*g+8*h+9*i+10*j;}
struct Aggregate{uint64_t a,b,c;};
__attribute__((noinline)) static Aggregate aggregate(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,
    uint64_t f,uint64_t g,uint64_t h){return {a+3*b+5*c+7*d,e^(11*f)^(13*g)^(17*h),a+b+c+d+e+f+g+h};}
struct Mixed{uint64_t a;double b;};
__attribute__((noinline)) static Mixed mixed(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,
    uint64_t f,uint64_t g,double x,double y,double z){return {a+3*b+5*c+7*d+11*e+13*f+17*g,x+3*y+5*z+(a^g)/2.};}
__attribute__((noinline)) static uint64_t variadic(uint64_t marker,...){
    va_list args;va_start(args,marker);uint64_t result=marker;
    for(unsigned i=0;i<6;i++){uint64_t a=va_arg(args,uint64_t);double b=va_arg(args,double);
        result^=a*(i+1);result+=uint64_t(b*2)*(i+3);}
    va_end(args);return result;
}
static NSDictionary *calibrate(NSString *mode){
    bool overflow=[mode isEqual:@"overflow"],disabled=[mode isEqual:@"disabled"];
    void *target=nullptr;
    if([mode isEqual:@"integer"]||overflow||disabled)target=(void*)integers;
    else if([mode isEqual:@"floating"])target=(void*)floating;
    else if([mode isEqual:@"aggregate"])target=(void*)aggregate;
    else if([mode isEqual:@"mixed"])target=(void*)mixed;
    else if([mode isEqual:@"variadic"])target=(void*)variadic;
    else if([mode isEqual:@"flags"])target=(void*)KPRegistryTestFlagsOriginal;
    if(!target||!KPRegistrySetSyntheticTarget(target)||!KPRegistryEnable(!disabled))return nil;
    NSMutableArray *cases=[NSMutableArray array];unsigned failures=0;
    unsigned tails=overflow?1:6,trials=overflow?1027:64;
    for(unsigned index=0;index<tails;index++)for(unsigned trial=0;trial<trials;trial++){
        uint64_t seed=0x13579+index*991+trial*17;void *tail=KPRegistryTail(index);id actual=nil;bool correct=false;
        if(target==(void*)integers){
            uint64_t a[12];for(unsigned i=0;i<12;i++)a[i]=seed+i;
            uint64_t got=((decltype(&integers))tail)(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10],a[11]);
            const uint64_t weights[]={1,3,5,7,11,13,17,19,23,29,31,37};uint64_t want=0;
            for(unsigned i=0;i<12;i++)want^=a[i]*weights[i];actual=@(got);correct=got==want;
        }else if(target==(void*)floating){
            double a[10];for(unsigned i=0;i<10;i++)a[i]=(seed+i)/2.;
            double got=((decltype(&floating))tail)(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9]);
            double want=0;for(unsigned i=0;i<10;i++)want+=(i+1)*a[i];actual=@(got);correct=got==want;
        }else if(target==(void*)aggregate){
            auto got=((decltype(&aggregate))tail)(seed,seed+1,seed+2,seed+3,seed+4,seed+5,seed+6,seed+7);
            uint64_t x=seed+3*(seed+1)+5*(seed+2)+7*(seed+3),y=(seed+4)^(11*(seed+5))^(13*(seed+6))^(17*(seed+7));
            actual=@[@(got.a),@(got.b),@(got.c)];correct=got.a==x&&got.b==y&&got.c==8*seed+28;
        }else if(target==(void*)mixed){
            auto got=((decltype(&mixed))tail)(seed,seed+1,seed+2,seed+3,seed+4,seed+5,seed+6,seed/2.,(seed+1)/2.,(seed+2)/2.);
            uint64_t x=seed+3*(seed+1)+5*(seed+2)+7*(seed+3)+11*(seed+4)+13*(seed+5)+17*(seed+6);
            double y=seed/2.+3*((seed+1)/2.)+5*((seed+2)/2.)+(seed^(seed+6))/2.;
            actual=@[@(got.a),@(got.b)];correct=got.a==x&&got.b==y;
        }else if(target==(void*)variadic){
            auto got=((decltype(&variadic))tail)(seed,seed,(seed)/2.,seed+3,(seed+5)/2.,
                seed+6,(seed+10)/2.,seed+9,(seed+15)/2.,seed+12,(seed+20)/2.,seed+15,(seed+25)/2.);
            uint64_t want=seed;for(unsigned i=0;i<6;i++){want^=(seed+3*i)*(i+1);want+=(seed+5*i)*(i+3);}
            actual=@(got);correct=got==want;
        }else{
            const unsigned bits[]={0,2,4,6,7,11};uint64_t want=0;
            for(unsigned i=0;i<6;i++)if(trial&(1u<<i))want|=1ull<<bits[i];
            uint64_t got=KPRegistryTestFlagsCall(tail,0x202|want);actual=@(got);
            correct=(got&0x8d5)==want;
        }
        failures+=!correct;[cases addObject:@{@"index":@(index),@"trial":@(trial),@"seed":@(seed),@"actual":actual,@"correct":@(correct)}];
    }
    NSDictionary *trace=KPRegistrySnapshot();uint64_t wanted=disabled?0:cases.count;
    bool bounded=[trace[@"calls"]unsignedLongLongValue]==wanted&&[trace[@"dropped"]unsignedIntValue]==(overflow?3:0)
        &&[trace[@"events"]count]==(overflow?1024:wanted)&&[trace[@"recorders_drained"]boolValue]&&![trace[@"pending"]boolValue];
    return @{@"mode":mode,@"verified_calls":@(cases.count),@"case_failures":@(failures),@"bounded_trace_valid":@(bounded),
        @"cases":cases,@"trace":trace,@"status":(!failures&&bounded)?@"PASS":@"FAIL"};
}
#else
extern "C" NSDictionary *KPRegistryPublicDecode(NSString *,NSString *,NSString *);
extern "C" const char *KPRegistryCodecName();
static NSArray *residentPins(NSDictionary *before,NSDictionary *profile){
    NSString *module=profile[@"module"];bool image=false;
    if(![module isEqual:@"/System/Library/Frameworks/CoreMedia.framework/Versions/A/CoreMedia"]||
        ![profile[@"UUID"]isEqual:@"7c4ae5aed528396982c6a4a534949ef3"]||[profile[@"symbols"]count]!=6)return nil;
    for(NSDictionary *row in before[@"images"])if([row[@"install_name"]isEqual:module]&&[row[@"alive"]boolValue]&&
        [row[@"UUID"]isEqual:profile[@"UUID"]]&&[row[@"current_version"]isEqual:@"3330.13.105"])image=true;
    if(!image)return nil;NSMutableArray *checks=[NSMutableArray array];
    NSArray *names=@[@"FigSignalErrorAtGM",@"FigRegistryItemCopyMatchingInfo",@"FigRegistryItemGetFactory",
        @"FigRegistryItemCopyDescription",@"FigRegistryItemRequiresRosetta",@"FigRegistryItemRequiresMissingRosetta"];
    for(unsigned i=0;i<6;i++){
        NSDictionary *p=profile[@"symbols"][i];void *original=KPRegistryOriginal(i);Dl_info info{};
        size_t length=[p[@"bytes"]unsignedLongLongValue];
        if(![p[@"name"]isEqual:names[i]]||[p[@"index"]unsignedIntValue]!=i||!length||length>65536||
            !original||!dladdr(original,&info)||!info.dli_fname||strcmp(info.dli_fname,module.UTF8String)||
            (uintptr_t)original-(uintptr_t)info.dli_fbase!=[p[@"offset"]unsignedLongLongValue])return nil;
        NSString *actual=registryHash(ownRegion((uint8_t*)original,length));
        if(![actual isEqual:p[@"SHA256"]])return nil;
        [checks addObject:@{@"index":@(i),@"name":names[i],@"offset":p[@"offset"],@"bytes":p[@"bytes"],@"SHA256":actual}];
    }return checks;
}
#endif
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=4)return 1;NSString *assets=@(argv[1]),*out=@(argv[2]),*mode=@(argv[3]);
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"registry-config.json"]]options:0 error:nil];if(!config)return 2;
    Dl_info library{};NSString *kind=KPRegistryLibraryKind();
    if(!dladdr((void*)KPRegistryOriginal,&library)||!library.dli_fname||
        ![registryHash([NSData dataWithContentsOfFile:@(library.dli_fname)])isEqual:config[@"library_SHA256"][kind]])return 2;
    KPVideoImagesStart();NSDictionary *before=KPVideoImagesSnapshot();NSDictionary *result=nil;
#if KPREG_CALIBRATION
    if(![kind isEqual:@"calibration"])return 3;result=calibrate(mode);if(!result)return 4;
#else
    if(![@[@"inspect",@"cpu",@"hardware"]containsObject:mode]||[kind isEqual:@"calibration"])return 3;
    NSDictionary *profile=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"registry-profile.json"]]options:0 error:nil];
    NSArray *checks=residentPins(before,profile);if(checks.count!=6)return 4;
    bool inspect=[mode isEqual:@"inspect"];if(!KPRegistryEnable(!inspect))return 5;
    NSString *codec=@(KPRegistryCodecName());
    NSDictionary *decoded=inspect?nil:KPRegistryPublicDecode([[assets stringByAppendingPathComponent:@"fixtures"]
        stringByAppendingPathComponent:codec],mode,out);if(!inspect&&!decoded)return 6;
    NSDictionary *trace=KPRegistrySnapshot();bool valid=[trace[@"recorders_drained"]boolValue]&&
        ![trace[@"pending"]boolValue]&&![trace[@"dropped"]boolValue];
    result=@{@"status":valid?@"OBSERVATION_COMPLETED":@"TRACE_INCOMPLETE",@"mode":mode,@"codec":codec,
        @"resident_code_pins":checks,@"public_decode":decoded?:(id)[NSNull null],@"trace":trace};
#endif
    NSDictionary *after=KPVideoImagesSnapshot();
    NSData *data=[NSJSONSerialization dataWithJSONObject:@{@"before":before,@"after":after}
        options:NSJSONWritingPrettyPrinted error:nil];
    if(![data writeToFile:[out stringByAppendingPathComponent:@"images.json"]options:0 error:nil])return 7;
    NSMutableDictionary *record=[NSMutableDictionary dictionaryWithDictionary:result];
    record[@"library_kind"]=kind;record[@"direct_unknown_private_call"]=@NO;record[@"system_modified"]=@NO;
    record[@"performance_benchmark"]=@NO;record[@"hardware_video_execution_proved"]=@NO;
    data=[NSJSONSerialization dataWithJSONObject:record options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(data.bytes,1,data.length,stdout);puts("");
    return ([record[@"status"]isEqual:@"PASS"]||[record[@"status"]isEqual:@"OBSERVATION_COMPLETED"])?0:8;
}}
