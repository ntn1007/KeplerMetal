// SPDX-License-Identifier: MIT
// Public XPC calls in our own process only. No native callback is replaced.
#include "video_routing.h"
#include <xpc/xpc.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <atomic>
#include <chrono>
#include <cstring>
#include <mutex>
#include <sched.h>
#include <libproc.h>
#include <sys/proc_info.h>
#include <sys/time.h>
#include <unistd.h>
#include <cerrno>

namespace {
std::atomic<bool> enabled{false},begun{false};
std::atomic<unsigned> inflight{0},count{0},dropped{0};
thread_local bool inside=false;
constexpr unsigned capacity=512;
std::mutex rowsMutex;
NSMutableArray *rows=nil,*controls=nil,*summaryControls=nil,*peerControls=nil,*namedControls=nil;
NSDictionary *allowed=nil;
bool nativeCapture=false,controlValid=false,peerCapture=false;

// Public process metadata only. No task ports, memory reads or remote hooks.
bool sameBirth(pid_t before,pid_t after,const proc_bsdinfo &a,const proc_bsdinfo &b,
    int firstSize,int secondSize,int pathSize,bool terminated,uint64_t receiptMicros,uid_t uid){
    if(before<=0||before!=after||firstSize!=sizeof(a)||secondSize!=sizeof(b)||
        a.pbi_pid!=uint32_t(before)||b.pbi_pid!=uint32_t(before)||a.pbi_uid!=uid||b.pbi_uid!=uid||
        a.pbi_start_tvsec!=b.pbi_start_tvsec||a.pbi_start_tvusec!=b.pbi_start_tvusec||
        !a.pbi_start_tvsec||a.pbi_start_tvusec>=1000000||
        a.pbi_start_tvsec>(UINT64_MAX-a.pbi_start_tvusec)/1000000||
        pathSize<=0||pathSize>=PROC_PIDPATHINFO_MAXSIZE||!terminated||!receiptMicros)return false;
    return a.pbi_start_tvsec*1000000+a.pbi_start_tvusec<=receiptMicros;
}
uint64_t wallMicros(){timeval t{};if(gettimeofday(&t,nullptr)||t.tv_sec<=0)return 0;
    return uint64_t(t.tv_sec)*1000000+uint64_t(t.tv_usec);}
NSDictionary *peerMetadata(xpc_connection_t connection,uint64_t receiptMicros,bool ownControl=false){
    int saved=errno;pid_t before=ownControl?getpid():xpc_connection_get_pid(connection);
    uid_t uid=ownControl?geteuid():xpc_connection_get_euid(connection);
    proc_bsdinfo a{},b{};char path[PROC_PIDPATHINFO_MAXSIZE]{};
    int first=0,second=0,length=0,firstErr=0,secondErr=0,pathErr=0;
    if(before>0){errno=0;first=proc_pidinfo(before,PROC_PIDTBSDINFO,0,&a,sizeof(a));firstErr=errno;
        errno=0;length=proc_pidpath(before,path,sizeof(path));pathErr=errno;
        errno=0;second=proc_pidinfo(before,PROC_PIDTBSDINFO,0,&b,sizeof(b));secondErr=errno;}
    pid_t after=ownControl?getpid():xpc_connection_get_pid(connection);
    size_t n=strnlen(path,sizeof(path));bool terminated=n>0&&n<sizeof(path);
    bool consistent=sameBirth(before,after,a,b,first,second,length,terminated,receiptMicros,uid);
    NSString *name=terminated?[[[NSString alloc]initWithBytes:path length:n encoding:NSUTF8StringEncoding]autorelease]:nil;
    NSDictionary *result=@{@"PID_before":@(before),@"PID_after":@(after),@"peer_euid":@(uid),
        @"first_info_bytes":@(first),@"second_info_bytes":@(second),@"path_bytes":@(length),
        @"first_errno":@(firstErr),@"second_errno":@(secondErr),@"path_errno":@(pathErr),
        @"first_birth_seconds":@(a.pbi_start_tvsec),@"first_birth_microseconds":@(a.pbi_start_tvusec),
        @"second_birth_seconds":@(b.pbi_start_tvsec),@"second_birth_microseconds":@(b.pbi_start_tvusec),
        @"receipt_wall_microseconds":@(receiptMicros),@"path":name?:@"",@"consistent":@(consistent&&name),
        @"authenticated_peer_identity_proved":@NO,@"PID_reuse_fully_excluded":@NO,
        @"remote_memory_read":@NO,@"remote_process_modified":@NO};
    errno=saved;return result;
}
NSString *hash(NSData *data){
    if(!data)return @"";unsigned char digest[32];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
    NSMutableString *s=[NSMutableString string];for(auto b:digest)[s appendFormat:@"%02x",b];return s;
}
NSDictionary *identity(const void *address){
    Dl_info info{};if(!address||!dladdr(address,&info)||!info.dli_fname||!info.dli_fbase)return nil;
    auto h=(const mach_header_64*)info.dli_fbase;
    if(h->magic!=MH_MAGIC_64||h->ncmds>4096||h->sizeofcmds>1048576)return nil;
    size_t at=0;NSString *uuid=nil,*version=nil;
    for(unsigned i=0;i<h->ncmds;i++){
        if(at+sizeof(load_command)>h->sizeofcmds)return nil;
        auto command=(const load_command*)((const uint8_t*)(h+1)+at);
        if(command->cmdsize<sizeof(load_command)||command->cmdsize>h->sizeofcmds-at)return nil;
        if(command->cmd==LC_UUID&&command->cmdsize>=sizeof(uuid_command)){
            NSMutableString *s=[NSMutableString string];for(auto b:((const uuid_command*)command)->uuid)[s appendFormat:@"%02x",b];uuid=s;
        }else if(command->cmd==LC_ID_DYLIB&&command->cmdsize>=sizeof(dylib_command)){
            uint32_t v=((const dylib_command*)command)->dylib.current_version;
            version=[NSString stringWithFormat:@"%u.%u.%u",v>>16,(v>>8)&255,v&255];
        }at+=command->cmdsize;
    }
    if(at!=h->sizeofcmds||!uuid||!version)return nil;
    return @{@"install_name":@(info.dli_fname),@"UUID":uuid,@"current_version":version,
        @"caller_offset":@((uintptr_t)address-(uintptr_t)info.dli_fbase)};
}
NSString *text(const char *value,bool *truncated){
    if(!value)return @"";size_t n=strnlen(value,256);*truncated|=n==256;
    NSString *s=[[[NSString alloc]initWithBytes:value length:n encoding:NSUTF8StringEncoding]autorelease];
    if(!s){*truncated=true;return @"";}return s;
}
NSString *typeName(xpc_object_t value){
    if(!value)return @"null";xpc_type_t type=xpc_get_type(value);
    if(type==XPC_TYPE_DICTIONARY)return @"dictionary";if(type==XPC_TYPE_ERROR)return @"error";
    if(type==XPC_TYPE_INT64)return @"int64";if(type==XPC_TYPE_UINT64)return @"uint64";
    if(type==XPC_TYPE_STRING)return @"string";if(type==XPC_TYPE_DATA)return @"data";
    if(type==XPC_TYPE_ARRAY)return @"array";if(type==XPC_TYPE_BOOL)return @"bool";
    return @"other";
}
NSDictionary *summary(xpc_object_t value){
    NSMutableDictionary *d=[NSMutableDictionary dictionaryWithObject:typeName(value) forKey:@"type"];
    if(value==XPC_ERROR_CONNECTION_INVALID)d[@"error_kind"]=@"CONNECTION_INVALID";
    else if(value==XPC_ERROR_CONNECTION_INTERRUPTED)d[@"error_kind"]=@"CONNECTION_INTERRUPTED";
    if(!value||xpc_get_type(value)!=XPC_TYPE_DICTIONARY)return d;
    NSMutableArray *entries=[NSMutableArray array];__block bool truncated=false;
    xpc_dictionary_apply(value,^bool(const char *key,xpc_object_t object){
        if(entries.count==32){truncated=true;return false;}
        bool cut=false;NSString *name=text(key,&cut);truncated|=cut;
        NSMutableDictionary *item=[NSMutableDictionary dictionaryWithDictionary:@{@"key":name,@"type":typeName(object)}];
        NSString *lower=name.lowercaseString;
        if([lower hasPrefix:@"."])lower=[lower substringFromIndex:1];
        if([@[@"status",@"err",@"error",@"osstatus",@"errorcode",@"errorreturn",@"opcode",@"operation",@"messageid",@"method"]containsObject:lower]){
            if(xpc_get_type(object)==XPC_TYPE_INT64){int64_t n=xpc_int64_get_value(object);
                if(n>=INT32_MIN&&n<=INT32_MAX)item[@"scalar"]=@(n);else item[@"scalar_omitted"]=@YES;
            }else if(xpc_get_type(object)==XPC_TYPE_UINT64){uint64_t n=xpc_uint64_get_value(object);
                if(n<=UINT32_MAX)item[@"scalar"]=@(n);
                else if(n>=UINT64_MAX-uint64_t(INT32_MAX)){
                    // Some public XPC clients carry a negative OSStatus in a
                    // sign-extended uint64. Record only that bounded int32.
                    item[@"scalar_signed32"]=@(-1-int64_t(UINT64_MAX-n));
                    item[@"scalar_encoding"]=@"uint64_sign_extended_int32";
                }else item[@"scalar_omitted"]=@YES;
            }
        }
        [entries addObject:item];return true;
    });
    d[@"keys"]=[entries sortedArrayUsingDescriptors:@[[NSSortDescriptor sortDescriptorWithKey:@"key" ascending:YES]]];
    d[@"key_count"]=@(xpc_dictionary_get_count(value));d[@"truncated"]=@(truncated);
    d[@"binary_or_string_values_copied"]=@NO;return d;
}
struct Scope {
    bool active=false,control=false;NSDictionary *caller=nil;
    Scope(void *pc,bool ownMock):control(ownMock){
        if(!enabled.load(std::memory_order_seq_cst)||inside)return;
        inflight.fetch_add(1,std::memory_order_seq_cst);
        if(!enabled.load(std::memory_order_seq_cst)){inflight.fetch_sub(1);return;}
        inside=true;
        if(control){caller=@{@"install_name":@"synthetic",@"UUID":@"",@"caller_offset":@0};active=true;}
        else if(nativeCapture){caller=identity(pc);NSString *path=caller[@"install_name"];NSDictionary *expected=path?allowed[path]:nil;
            active=expected&&[caller[@"UUID"]isEqual:expected[@"UUID"]]&&
                [caller[@"current_version"]isEqual:expected[@"current_version"]];}
        if(!active){inside=false;inflight.fetch_sub(1);}
    }
    ~Scope(){if(active){inside=false;inflight.fetch_sub(1,std::memory_order_seq_cst);}}
};
void record(Scope &scope,NSString *api,const char *name,xpc_connection_t connection,uint64_t flags,
    NSDictionary *message,NSDictionary *reply,bool resultPresent,uint64_t receiptMicros=0){
    unsigned index=count.fetch_add(1,std::memory_order_relaxed);
    if(index>=capacity){dropped.fetch_add(1);return;}
    bool cut=false;NSString *service=text(scope.control?"synthetic":(name?name:(connection?xpc_connection_get_name(connection):nullptr)),&cut);
    NSMutableDictionary *row=[NSMutableDictionary dictionaryWithDictionary:@{@"ordinal":@(index),@"API":api,@"synthetic_control":@(scope.control),
        @"caller":scope.caller?:@{},@"service":service,@"flags":@(flags),@"truncated":@(cut),
        @"result_present":@(resultPresent),@"message":message?:@{},@"reply":reply?:@{}}];
    if(peerCapture&&!scope.control&&[api isEqual:@"send_with_reply_sync"]&&
        [service isEqual:@"com.apple.coremedia.videodecoder"]&&[reply[@"type"]isEqual:@"dictionary"]){
        for(NSDictionary *item in message[@"keys"])if([item[@"key"]isEqual:@"OpCode"]&&
            (uint64_t([item[@"scalar"]unsignedLongLongValue])==1969382770||
             uint64_t([item[@"scalar"]unsignedLongLongValue])==1400140404)){
            row[@"peer_metadata"]=peerMetadata(connection,receiptMicros);break;
        }
    }
    std::lock_guard<std::mutex> lock(rowsMutex);[rows addObject:row];
}
thread_local xpc_object_t controlConnection=nullptr,controlMessage=nullptr,controlReply=nullptr;
thread_local dispatch_queue_t controlQueue=nullptr;
thread_local xpc_handler_t controlHandler=nullptr;
thread_local const char *controlName=nullptr;
thread_local uint64_t controlFlags=0;
thread_local bool argumentsValid=true;
thread_local int controlInputErrno=0,controlOutputErrno=0;
xpc_connection_t mockCreate(const char *name,dispatch_queue_t queue,uint64_t flags){
    argumentsValid&=name==controlName&&queue==controlQueue&&flags==controlFlags&&errno==controlInputErrno;
    errno=controlOutputErrno;
    return (xpc_connection_t)controlConnection;
}
xpc_object_t mockSync(xpc_connection_t connection,xpc_object_t message){
    argumentsValid&=connection==(xpc_connection_t)controlConnection&&message==controlMessage&&errno==controlInputErrno;
    auto result=xpc_retain(controlReply);errno=controlOutputErrno;return result;
}
void mockAsync(xpc_connection_t connection,xpc_object_t message,dispatch_queue_t queue,xpc_handler_t handler){
    argumentsValid&=connection==(xpc_connection_t)controlConnection&&message==controlMessage&&
        queue==controlQueue&&handler==controlHandler&&errno==controlInputErrno;handler(controlReply);errno=controlOutputErrno;
}
xpc_connection_t createImpl(const char *name,dispatch_queue_t queue,uint64_t flags,void *pc,bool mock){
    int incoming=errno,saved=incoming;xpc_connection_t result=nullptr;
    @autoreleasepool{
        Scope scope(pc,mock);
        errno=incoming;result=mock?mockCreate(name,queue,flags):xpc_connection_create_mach_service(name,queue,flags);saved=errno;
        if(scope.active)record(scope,@"create_mach_service",name,result,flags,nil,nil,result!=nullptr);
    }
    errno=saved;return result;
}
xpc_connection_t namedImpl(const char *name,dispatch_queue_t queue,void *pc,bool mock){
    int incoming=errno,saved=incoming;xpc_connection_t result=nullptr;
    @autoreleasepool{
        Scope scope(pc,mock);errno=incoming;
        result=mock?mockCreate(name,queue,0):xpc_connection_create(name,queue);saved=errno;
        if(scope.active)record(scope,@"create",name,result,0,nil,nil,result!=nullptr);
    }
    errno=saved;return result;
}
xpc_object_t syncImpl(xpc_connection_t connection,xpc_object_t message,void *pc,bool mock){
    int incoming=errno,saved=incoming;xpc_object_t result=nullptr;
    @autoreleasepool{
        Scope scope(pc,mock);NSDictionary *sent=scope.active?summary(message):nil;
        errno=incoming;result=mock?mockSync(connection,message):xpc_connection_send_message_with_reply_sync(connection,message);saved=errno;
        uint64_t receipt=wallMicros();
        if(scope.active)record(scope,@"send_with_reply_sync",nullptr,connection,0,sent,summary(result),result!=nullptr,receipt);
    }
    errno=saved;return result;
}
void asyncImpl(xpc_connection_t connection,xpc_object_t message,dispatch_queue_t queue,
    xpc_handler_t handler,void *pc,bool mock){
    int incoming=errno,saved=incoming;
    @autoreleasepool{
        Scope scope(pc,mock);
        if(scope.active)record(scope,@"send_with_reply",nullptr,connection,0,summary(message),nil,false);
        errno=incoming;if(mock)mockAsync(connection,message,queue,handler);
        else xpc_connection_send_message_with_reply(connection,message,queue,handler);saved=errno;
    }
    errno=saved;
}
__attribute__((noinline)) xpc_connection_t observedCreate(const char *name,dispatch_queue_t queue,uint64_t flags){
    return createImpl(name,queue,flags,__builtin_return_address(0),false);
}
__attribute__((noinline)) xpc_connection_t observedNamed(const char *name,dispatch_queue_t queue){
    return namedImpl(name,queue,__builtin_return_address(0),false);
}
__attribute__((noinline)) xpc_object_t observedSync(xpc_connection_t connection,xpc_object_t message){
    return syncImpl(connection,message,__builtin_return_address(0),false);
}
__attribute__((noinline)) void observedAsync(xpc_connection_t connection,xpc_object_t message,
    dispatch_queue_t queue,xpc_handler_t handler){
    asyncImpl(connection,message,queue,handler,__builtin_return_address(0),false);
}
bool calibrate(){
    controlConnection=xpc_dictionary_create(nullptr,nullptr,0);controlMessage=xpc_dictionary_create(nullptr,nullptr,0);
    controlReply=xpc_dictionary_create(nullptr,nullptr,0);
    if(!controlConnection||!controlMessage||!controlReply)return false;
    bool valid=true;
    for(unsigned i=0;i<32;i++){
        controlQueue=i&1?dispatch_get_main_queue():nullptr;controlFlags=0x8000000000000000ull+uint64_t(i)*0x100000001ull;
        NSString *name=[NSString stringWithFormat:@"KeplerMetal.synthetic.%u",i];controlName=name.UTF8String;
        xpc_dictionary_set_int64(controlReply,"status",-100-int(i));xpc_dictionary_set_uint64(controlMessage,"opcode",i);
        controlInputErrno=100+int(i);controlOutputErrno=200+int(i);errno=controlInputErrno;
        argumentsValid=true;auto connection=createImpl(controlName,controlQueue,controlFlags,nullptr,true);
        bool errnoValid=errno==controlOutputErrno;errno=controlInputErrno;
        xpc_object_t reply=syncImpl(connection,controlMessage,nullptr,true);
        errnoValid&=errno==controlOutputErrno;
        __block unsigned callbacks=0;__block bool replyValid=false;
        xpc_handler_t handler=^(xpc_object_t value){callbacks++;replyValid=value==controlReply;};controlHandler=handler;
        errno=controlInputErrno;asyncImpl(connection,controlMessage,controlQueue,handler,nullptr,true);
        errnoValid&=errno==controlOutputErrno;
        bool correct=argumentsValid&&connection==(xpc_connection_t)controlConnection&&reply==controlReply&&
            xpc_dictionary_get_int64(reply,"status")==-100-int(i)&&callbacks==1&&replyValid&&errnoValid;
        [controls addObject:@{@"trial":@(i),@"flags":@(controlFlags),@"correct":@(correct),@"callbacks":@(callbacks),
            @"input_errno":@(controlInputErrno),@"output_errno":@(controlOutputErrno),@"errno_preserved":@(errnoValid)}];
        valid&=correct;if(reply)xpc_release(reply);
    }
    xpc_release(controlConnection);xpc_release(controlMessage);xpc_release(controlReply);
    controlConnection=controlMessage=controlReply=nullptr;controlHandler=nullptr;return valid;
}
bool summaryContracts(){
    struct Case { const char *key;bool unsignedValue;uint64_t bits;const char *field;int64_t wanted; };
    const Case cases[]={
        {"Status",true,0,"scalar",0},
        {"Status",true,UINT32_MAX,"scalar",UINT32_MAX},
        {"Status",true,UINT64_MAX-12905,"scalar_signed32",-12906},
        {"Status",true,UINT64_MAX-uint64_t(INT32_MAX),"scalar_signed32",INT32_MIN},
        {"Status",true,UINT64_MAX,"scalar_signed32",-1},
        {"Status",true,uint64_t(UINT32_MAX)+1,"scalar_omitted",1},
        {"Status",true,UINT64_MAX-uint64_t(INT32_MAX)-1,"scalar_omitted",1},
        {"Status",false,uint64_t(int64_t(-12906)),"scalar",-12906},
        {"Status",false,uint64_t(INT32_MAX)+1,"scalar_omitted",1},
        {".ErrorReturn",false,uint64_t(int64_t(-12906)),"scalar",-12906},
        {".Operation",true,1969382770,"scalar",1969382770},
        {"PID",true,12345,nullptr,0}};
    bool valid=true;unsigned trial=0;
    for(const auto &c:cases){
        xpc_object_t object=xpc_dictionary_create(nullptr,nullptr,0);
        if(c.unsignedValue)xpc_dictionary_set_uint64(object,c.key,c.bits);
        else {int64_t value;std::memcpy(&value,&c.bits,sizeof(value));xpc_dictionary_set_int64(object,c.key,value);}
        NSDictionary *item=[summary(object)[@"keys"]firstObject];
        bool correct=c.field?item[@(c.field)]&&[item[@(c.field)]longLongValue]==c.wanted:
            !item[@"scalar"]&&!item[@"scalar_signed32"]&&!item[@"scalar_omitted"];
        if(c.field&&!strcmp(c.field,"scalar_signed32"))correct&=[item[@"scalar_encoding"]isEqual:@"uint64_sign_extended_int32"];
        [summaryControls addObject:@{@"trial":@(trial++),@"kind":@"numeric_bounds_and_allowlist",@"correct":@(correct)}];
        valid&=correct;xpc_release(object);
    }
    xpc_object_t object=xpc_dictionary_create(nullptr,nullptr,0);
    xpc_dictionary_set_string(object,"Status","KeplerMetal.synthetic.private-value");
    xpc_dictionary_set_data(object,"Payload","abc",3);
    xpc_object_t nested=xpc_dictionary_create(nullptr,nullptr,0);
    xpc_dictionary_set_string(nested,"secret","KeplerMetal.synthetic.nested-value");
    xpc_dictionary_set_value(object,"Nested",nested);xpc_release(nested);
    NSDictionary *limited=summary(object);
    NSData *json=[NSJSONSerialization dataWithJSONObject:limited options:0 error:nil];
    NSString *serialized=[[[NSString alloc]initWithData:json encoding:NSUTF8StringEncoding]autorelease];
    bool privateValues=serialized&&[serialized rangeOfString:@"private-value"].location==NSNotFound&&
        [serialized rangeOfString:@"nested-value"].location==NSNotFound&&[serialized rangeOfString:@"secret"].location==NSNotFound;
    [summaryControls addObject:@{@"trial":@(trial++),@"kind":@"no_string_binary_or_nested_values",@"correct":@(privateValues)}];
    valid&=privateValues;xpc_release(object);
    object=xpc_dictionary_create(nullptr,nullptr,0);
    for(unsigned i=0;i<33;i++){char key[32];snprintf(key,sizeof(key),"bounded-%u",i);xpc_dictionary_set_int64(object,key,i);}
    limited=summary(object);bool bounded=[limited[@"keys"]count]==32&&[limited[@"key_count"]unsignedIntValue]==33&&[limited[@"truncated"]boolValue];
    [summaryControls addObject:@{@"trial":@(trial++),@"kind":@"dictionary_capacity",@"correct":@(bounded)}];
    valid&=bounded;xpc_release(object);return valid;
}
bool peerContracts(){
    bool valid=true;
    for(unsigned i=0;i<19;i++){
        proc_bsdinfo a{},b{};a.pbi_pid=b.pbi_pid=123;a.pbi_uid=b.pbi_uid=501;
        a.pbi_start_tvsec=b.pbi_start_tvsec=100;a.pbi_start_tvusec=b.pbi_start_tvusec=50;
        pid_t first=123,last=123;int n1=sizeof(a),n2=sizeof(b),path=20;bool nul=true;uint64_t receipt=101000000;
        switch(i){case 1:first=0;break;case 2:last=124;break;case 3:a.pbi_pid=124;break;
            case 4:b.pbi_pid=124;break;case 5:n1--;break;case 6:n2--;break;
            case 7:b.pbi_start_tvsec++;break;case 8:b.pbi_start_tvusec++;break;
            case 9:a.pbi_uid++;break;case 10:path=0;break;case 11:nul=false;break;
            case 12:receipt=99000000;break;case 13:a.pbi_start_tvusec=b.pbi_start_tvusec=1000000;break;
            case 14:a.pbi_start_tvsec=b.pbi_start_tvsec=0;break;case 15:path=PROC_PIDPATHINFO_MAXSIZE;break;
            case 16:a.pbi_start_tvsec=b.pbi_start_tvsec=UINT64_MAX;break;
            case 17:b.pbi_uid++;break;case 18:receipt=0;break;default:break;}
        bool actual=sameBirth(first,last,a,b,n1,n2,path,nul,receipt,501),correct=actual==(i==0);
        [peerControls addObject:@{@"trial":@(i),@"kind":@"pure_PID_birth_path_predicate",@"accepted":@(actual),@"correct":@(correct)}];
        valid&=correct;
    }
    NSDictionary *self=peerMetadata(nullptr,wallMicros(),true);bool selfValid=[self[@"consistent"]boolValue]&&
        [self[@"PID_before"]intValue]==getpid()&&[self[@"PID_after"]intValue]==getpid();
    [peerControls addObject:@{@"trial":@19,@"kind":@"public_own_process_metadata",@"correct":@(selfValid),
        @"remote_process_queried":@NO}];return valid&&selfValid;
}
bool namedContracts(){
    controlConnection=xpc_dictionary_create(nullptr,nullptr,0);if(!controlConnection)return false;
    bool valid=true;controlFlags=0;
    for(unsigned i=0;i<16;i++){
        NSString *name=[NSString stringWithFormat:@"KeplerMetal.named-control.%u",i];controlName=name.UTF8String;
        controlQueue=i&1?dispatch_get_main_queue():nullptr;controlInputErrno=300+i;controlOutputErrno=400+i;
        argumentsValid=true;errno=controlInputErrno;
        auto returned=namedImpl(controlName,controlQueue,nullptr,true);
        bool good=argumentsValid&&returned==(xpc_connection_t)controlConnection&&errno==controlOutputErrno;
        [namedControls addObject:@{@"trial":@(i),@"correct":@(good),@"errno_preserved":@(errno==controlOutputErrno)}];
        valid&=good;
    }
    xpc_release(controlConnection);controlConnection=nullptr;return valid;
}
#define KP_ROUTE_PAIR(function,original) \
    __attribute__((used)) static const struct{const void *replacement,*original_;} pair_##function \
    __attribute__((section("__DATA,__interpose")))={(void*)&function,(void*)&original};
KP_ROUTE_PAIR(observedCreate,xpc_connection_create_mach_service)
KP_ROUTE_PAIR(observedNamed,xpc_connection_create)
KP_ROUTE_PAIR(observedSync,xpc_connection_send_message_with_reply_sync)
KP_ROUTE_PAIR(observedAsync,xpc_connection_send_message_with_reply)
}
extern "C" bool KPVideoRoutingBegin(NSString *assets){
    if(begun.exchange(true))return false;
    NSDictionary *config=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"routing-config.json"]]options:0 error:nil];
    NSData *profileData=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"routing-profile.json"]];
    NSDictionary *profile=[NSJSONSerialization JSONObjectWithData:profileData options:0 error:nil];
    NSDictionary *choice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"routing-choice.json"]]options:0 error:nil];
    NSDictionary *peerChoice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"peer-choice.json"]]options:0 error:nil];
    Dl_info self{};if(!config||!profile||choice.count!=1||![@[@"passive",@"observe"]containsObject:choice[@"mode"]]||
        peerChoice.count!=1||![@[@"passive",@"observe"]containsObject:peerChoice[@"mode"]]||
        ![hash(profileData)isEqual:config[@"profile_SHA256"]]||!dladdr((void*)KPVideoRoutingBegin,&self)||!self.dli_fname||
        ![hash([NSData dataWithContentsOfFile:@(self.dli_fname)])isEqual:config[@"library_SHA256"]])return false;
    NSMutableDictionary *table=[NSMutableDictionary dictionary];
    for(NSDictionary *module in profile[@"modules"])table[module[@"install_name"]]=module;
    if(table.count!=7)return false;
    for(NSString *name in profile[@"required_before_begin"]){bool matched=false;
        for(uint32_t i=0;i<_dyld_image_count();i++){
            const char *path=_dyld_get_image_name(i);if(!path||strcmp(path,name.UTF8String))continue;
            NSDictionary *actual=identity(_dyld_get_image_header(i)),*expected=table[name];
            matched=[actual[@"UUID"]isEqual:expected[@"UUID"]]&&[actual[@"current_version"]isEqual:expected[@"current_version"]];
        }if(!matched)return false;
    }
    allowed=[table copy];rows=[[NSMutableArray alloc]init];controls=[[NSMutableArray alloc]init];summaryControls=[[NSMutableArray alloc]init];peerControls=[[NSMutableArray alloc]init];namedControls=[[NSMutableArray alloc]init];
    peerCapture=[peerChoice[@"mode"]isEqual:@"observe"];
    nativeCapture=[choice[@"mode"]isEqual:@"observe"];enabled.store(true,std::memory_order_seq_cst);
    bool abi=calibrate(),summaries=summaryContracts(),peers=peerContracts(),named=namedContracts();controlValid=abi&&summaries&&peers&&named;
    if(!controlValid)enabled.store(false);return controlValid;
}
extern "C" NSDictionary *KPVideoRoutingSnapshot(){
    enabled.store(false,std::memory_order_seq_cst);auto end=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(inflight.load(std::memory_order_seq_cst)&&std::chrono::steady_clock::now()<end)sched_yield();
    bool drained=!inflight.load();NSArray *events=@[];
    if(drained){std::lock_guard<std::mutex>lock(rowsMutex);events=[[[rows sortedArrayUsingDescriptors:
        @[[NSSortDescriptor sortDescriptorWithKey:@"ordinal" ascending:YES]]]copy]autorelease];}
    return @{@"schema":@4,@"status":drained&&!dropped.load()?@"COMPLETE":@"INCOMPLETE",@"recorders_drained":@(drained),
        @"disabled_before_snapshot":@YES,@"calls":@(count.load()),@"dropped":@(dropped.load()),@"events":events?:@[],
        @"controls":controls?:@[],@"synthetic_ABI_calls":@112,@"synthetic_controls_valid":@(controlValid),
        @"named_constructor_controls":namedControls?:@[],@"named_constructor_control_calls":@(namedControls.count),
        @"scalar_summary_controls":summaryControls?:@[],@"scalar_summary_controls_calls":@(summaryControls.count),
        @"peer_controls":peerControls?:@[],@"peer_control_cases":@(peerControls.count),@"peer_capture_enabled":@(peerCapture),
        @"errno_preserved_around_interposed_calls":@YES,@"remote_memory_read":@NO,@"PID_reuse_fully_excluded":@NO,
        @"synthetic_native_IPC_calls":@0,@"native_capture_enabled":@(nativeCapture),@"system_modified":@NO,
        @"arguments_or_return_values_modified":@NO,@"async_handler_replaced":@NO,@"observer_generated_native_messages":@0,
        @"message_binary_or_string_values_copied":@NO,@"own_process_only":@YES,@"other_process_injected":@NO};
}
