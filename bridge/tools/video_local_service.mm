// SPDX-License-Identifier: MIT
// Opt-in anonymous decoder transport in this disposable process only.
// The callback type is the public xpc_main slot used by the pinned service
// entry. This is an experiment, not an implementation of the full service.
#import <Foundation/Foundation.h>
#include <xpc/xpc.h>
#include <dispatch/dispatch.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach-o/loader.h>
#include <mach/vm_prot.h>
#include <dlfcn.h>
#include <atomic>
#include <memory>
#include <mutex>
#include <vector>
#include <cstring>
#include <cerrno>
#include <unistd.h>

namespace {
constexpr const char *vtPath="/System/Library/Frameworks/VideoToolbox.framework/Versions/A/VideoToolbox";
constexpr const char *vtUUID="e7231bea63883d0a95c0a93ce970b96b";
constexpr uint32_t vtVersion=(3330u<<16)|(13u<<8)|105u;
std::atomic<bool> enabled{false};
thread_local bool inside=false;
NSString *digest(NSData *data){
    if(!data)return @"";unsigned char bytes[32];CC_SHA256(data.bytes,(CC_LONG)data.length,bytes);
    NSMutableString *text=[NSMutableString string];for(auto b:bytes)[text appendFormat:@"%02x",b];return text;
}
bool vtAddress(const void *address,uint64_t *offset=nullptr,const void **base=nullptr){
    Dl_info info{};if(!address||!dladdr(address,&info)||!info.dli_fname||strcmp(info.dli_fname,vtPath))return false;
    auto header=(const mach_header_64*)info.dli_fbase;
    if(header->magic!=MH_MAGIC_64||header->cputype!=CPU_TYPE_X86_64||header->ncmds>4096||header->sizeofcmds>1048576)return false;
    size_t at=0;bool uuid=false,version=false,executable=false;
    for(uint32_t i=0;i<header->ncmds;i++){
        if(at+sizeof(load_command)>header->sizeofcmds)return false;
        auto command=(const load_command*)((const uint8_t*)(header+1)+at);
        if(command->cmdsize<sizeof(load_command)||command->cmdsize>header->sizeofcmds-at)return false;
        if(command->cmd==LC_UUID&&command->cmdsize>=sizeof(uuid_command)){
            NSMutableString *text=[NSMutableString string];for(auto b:((const uuid_command*)command)->uuid)[text appendFormat:@"%02x",b];
            uuid=[text isEqual:@(vtUUID)];
        }
        if(command->cmd==LC_ID_DYLIB&&command->cmdsize>=sizeof(dylib_command))
            version=((const dylib_command*)command)->dylib.current_version==vtVersion;
        if(command->cmd==LC_SEGMENT_64&&command->cmdsize>=sizeof(segment_command_64)){
            auto segment=(const segment_command_64*)command;
            if(!strncmp(segment->segname,"__TEXT",16)){
                uintptr_t delta=(uintptr_t)address-(uintptr_t)info.dli_fbase;
                executable=(segment->initprot&VM_PROT_EXECUTE)&&delta<segment->vmsize&&segment->vmsize-delta>=101;
            }
        }
        at+=command->cmdsize;
    }
    if(at!=header->sizeofcmds||!uuid||!version||!executable)return false;
    if(offset)*offset=(uintptr_t)address-(uintptr_t)info.dli_fbase;if(base)*base=info.dli_fbase;return true;
}
struct State {
    std::mutex mutex;
    xpc_connection_handler_t handler=nullptr;
    xpc_connection_t listener=nullptr;
    xpc_endpoint_t endpoint=nullptr;
    dispatch_queue_t queue=dispatch_queue_create("KeplerMetal.owned.decoder",DISPATCH_QUEUE_SERIAL);
    // Client identities are borrowed. Returning +1 transfers that ownership
    // to VideoToolbox; retaining/canceling its client here changes its lifetime.
    // Only live connection arguments are inspected in ownedSync.
    std::vector<xpc_connection_t> clients,peers;
    NSMutableArray *exchanges=[[NSMutableArray alloc]init];
    std::atomic<unsigned> constructors{0},accepted{0},callbackReturned{0},unexpected{0},inflight{0};
    std::atomic<pid_t> clientPeerPID{0},serverPeerPID{0};
    bool invoke=false,preflight=false,hardware=false;
    ~State(){for(auto p:peers)xpc_release(p);
        if(endpoint)xpc_release(endpoint);if(listener)xpc_release(listener);dispatch_release(queue);[exchanges release];}
};
std::shared_ptr<State> current;
bool nativePin(xpc_connection_handler_t handler){
    uint64_t offset=0;if(!vtAddress((const void*)handler,&offset)||offset!=4268444)return false;
    return [digest([NSData dataWithBytes:(const void*)handler length:101])isEqual:
        @"100deacc2722bfbba2cee35dcf2ddcd00628d9840991e9d6f2ff82d426cab3b9"];
}
bool numeric(xpc_object_t object,const char *key,int64_t *out){
    if(!object||xpc_get_type(object)!=XPC_TYPE_DICTIONARY)return false;
    xpc_object_t value=xpc_dictionary_get_value(object,key);if(!value)return false;
    if(xpc_get_type(value)==XPC_TYPE_INT64){int64_t n=xpc_int64_get_value(value);
        if(n>=INT32_MIN&&n<=UINT32_MAX){*out=n;return true;}}
    if(xpc_get_type(value)==XPC_TYPE_UINT64){uint64_t n=xpc_uint64_get_value(value);
        if(n<=UINT32_MAX){*out=(int64_t)n;return true;}
        if(n>=UINT64_MAX-uint64_t(INT32_MAX)){*out=-1-int64_t(UINT64_MAX-n);return true;}}
    return false;
}
bool owns(const std::shared_ptr<State> &state,xpc_connection_t client){
    std::lock_guard<std::mutex> lock(state->mutex);
    for(auto p:state->clients)if(p==client)return true;return false;
}
__attribute__((noinline)) xpc_connection_t ownedCreate(const char *name,dispatch_queue_t target){
    int incoming=errno;void *pc=__builtin_return_address(0);auto state=std::atomic_load(&current);uint64_t offset=0;
    if(!enabled.load()||!state||inside||!state->invoke||!name||strcmp(name,"com.apple.coremedia.videodecoder")||
        !vtAddress(pc,&offset)||offset!=6326308){errno=incoming;return xpc_connection_create(name,target);}
    state->inflight++;
    if(!enabled.load()){state->inflight--;errno=incoming;return xpc_connection_create(name,target);}
    inside=true;
    if(state->constructors.fetch_add(1)!=0||!nativePin(state->handler)){
        state->unexpected++;state->inflight--;inside=false;errno=incoming;return xpc_connection_create(name,target);
    }
    xpc_connection_t result=xpc_connection_create_from_endpoint(state->endpoint);
    if(result){xpc_connection_set_target_queue(result,target);
        std::lock_guard<std::mutex> lock(state->mutex);state->clients.push_back(result);}
    else state->unexpected++;
    state->inflight--;inside=false;errno=incoming;return result;
}
__attribute__((noinline)) xpc_object_t ownedSync(xpc_connection_t connection,xpc_object_t message){
    int incoming=errno;void *pc=__builtin_return_address(0);auto state=std::atomic_load(&current);
    bool observe=enabled.load()&&state&&!inside&&owns(state,connection)&&vtAddress(pc);
    if(!observe){errno=incoming;return xpc_connection_send_message_with_reply_sync(connection,message);}
    state->inflight++;
    if(!enabled.load()){state->inflight--;errno=incoming;return xpc_connection_send_message_with_reply_sync(connection,message);}
    inside=true;
    int64_t opcode=0;bool op=numeric(message,"OpCode",&opcode);
    errno=incoming;xpc_object_t result=xpc_connection_send_message_with_reply_sync(connection,message);int saved=errno;
    int64_t status=0;bool st=numeric(result,"Status",&status);pid_t peer=xpc_connection_get_pid(connection);state->clientPeerPID=peer;
    NSDictionary *row=@{@"has_opcode":@(op),@"opcode":@(opcode),@"has_status":@(st),@"status":@(status),
        @"peer_PID":@(peer),@"same_process":@(peer==getpid()),
        @"reply_is_dictionary":@(result&&xpc_get_type(result)==XPC_TYPE_DICTIONARY),
        @"reply_connection_invalid":@(result==XPC_ERROR_CONNECTION_INVALID),
        @"reply_connection_interrupted":@(result==XPC_ERROR_CONNECTION_INTERRUPTED)};
    {std::lock_guard<std::mutex> lock(state->mutex);if(state->exchanges.count<64)[state->exchanges addObject:row];else state->unexpected++;}
    state->inflight--;inside=false;errno=saved;return result;
}
#define KP_OWN_PAIR(function,original) static const struct{const void*replacement;const void*originalFunction;} interpose_##function \
    __attribute__((used)) __attribute__((section("__DATA,__interpose")))={(void*)&function,(void*)&original};
KP_OWN_PAIR(ownedCreate,xpc_connection_create)
KP_OWN_PAIR(ownedSync,xpc_connection_send_message_with_reply_sync)
}
extern "C" bool KPVideoOwnedBegin(NSString *assets,NSString *mode){
    if(std::atomic_load(&current)||![@[@"inspect",@"cpu",@"hardware"]containsObject:mode])return false;
    NSDictionary *choice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:
        [assets stringByAppendingPathComponent:@"owned-choice.json"]]options:0 error:nil];
    if(choice.count!=1||![@[@"native",@"owned"]containsObject:choice[@"route"]])return false;
    auto state=std::make_shared<State>();
    state->handler=(xpc_connection_handler_t)dlsym(RTLD_DEFAULT,"VTRemoteDecodeServer_XPCServiceConnectionHandler");
    state->preflight=nativePin(state->handler);if(!state->preflight)return false;
    state->hardware=[mode isEqual:@"hardware"];
    state->invoke=![mode isEqual:@"inspect"]&&[choice[@"route"]isEqual:@"owned"];std::atomic_store(&current,state);
    if(!state->invoke)return true;
    std::weak_ptr<State> weak=state;
    state->listener=xpc_connection_create(nullptr,state->queue);
    if(!state->listener)return false;
    xpc_connection_set_event_handler(state->listener,^(xpc_object_t event){@autoreleasepool{
        auto state=weak.lock();if(!state)return;
        if(xpc_get_type(event)==XPC_TYPE_CONNECTION){
            auto peer=(xpc_connection_t)event;
            if(state->accepted.fetch_add(1)!=0||!nativePin(state->handler)){
                state->unexpected++;xpc_connection_cancel(peer);return;
            }
            xpc_retain(peer);{std::lock_guard<std::mutex> lock(state->mutex);state->peers.push_back(peer);}
            xpc_connection_set_target_queue(peer,state->queue);
            // The original callback installs its own handler and resumes the
            // real accepted connection. No event-handler substitution follows.
            state->serverPeerPID=xpc_connection_get_pid(peer);
            state->handler(peer);state->callbackReturned++;
        }else if(event!=XPC_ERROR_CONNECTION_INVALID)state->unexpected++;
    }});
    xpc_connection_activate(state->listener);state->endpoint=xpc_endpoint_create(state->listener);
    if(!state->endpoint)return false;
    enabled.store(true);return true;
}
extern "C" NSDictionary *KPVideoOwnedSnapshot(){
    enabled.store(false);auto state=std::atomic_load(&current);if(!state)return @{@"status":@"NO_STATE"};
    bool drained=state->inflight.load()==0;
    std::vector<xpc_connection_t> peers;
    {std::lock_guard<std::mutex> lock(state->mutex);peers=state->peers;}
    for(auto p:peers)xpc_connection_cancel(p);
    if(state->listener)xpc_connection_cancel(state->listener);
    dispatch_sync(state->queue,^{});
    bool own=state->invoke;
    bool noTransport=state->constructors==0&&state->accepted==0&&state->callbackReturned==0;
    bool usedTransport=state->constructors==1&&state->accepted==1&&state->callbackReturned==1;
    bool complete=drained&&state->unexpected.load()==0&&(!own||usedTransport||(state->hardware&&noTransport));
    NSDictionary *result=@{@"status":complete?@"COMPLETE":@"INCOMPLETE",@"preflight":@(state->preflight),
        @"route":own?@"owned":@"native",@"constructor_calls":@(state->constructors.load()),
        @"accepted":@(state->accepted.load()),@"native_callback_returned":@(state->callbackReturned.load()),
        @"unexpected":@(state->unexpected.load()),@"recorders_drained":@(drained),
        @"client_peer_PID":@(state->clientPeerPID.load()),@"server_peer_PID_at_accept":@(state->serverPeerPID.load()),
        @"PID":@(getpid()),@"exchanges":[NSArray arrayWithArray:state->exchanges],
        @"constructor_return_replaced":@(state->constructors.load()==1),@"native_handler_bytes":@101,
        @"native_handler_offset":@4268444,@"native_handler_SHA256":@"100deacc2722bfbba2cee35dcf2ddcd00628d9840991e9d6f2ff82d426cab3b9",
        @"full_native_service_lifetime_qualified":@NO,@"message_contents_modified":@NO,
        @"native_event_handlers_replaced":@NO,@"system_service_modified":@NO,@"system_modified":@NO,
        @"hardware_video_execution_proved":@NO,@"performance_benchmark":@NO};
    std::atomic_store(&current,std::shared_ptr<State>{});state.reset();return result;
}
