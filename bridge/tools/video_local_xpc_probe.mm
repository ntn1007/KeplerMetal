// SPDX-License-Identifier: MIT
// Public, anonymous, same-process XPC controls. No video/native private handler.
#import <Foundation/Foundation.h>
#include <xpc/xpc.h>
#include <dispatch/dispatch.h>
#include <atomic>
#include <memory>
#include <mutex>
#include <vector>
#include <cstring>
#include <functional>
#include <unistd.h>

namespace {
constexpr int64_t timeout=3*NSEC_PER_SEC;
std::atomic<unsigned> contexts{0};
struct State {
    std::mutex mutex;
    std::vector<xpc_connection_t> peers;
    xpc_object_t held=nullptr;
    NSMutableArray *events=[[NSMutableArray alloc]init];
    std::atomic<unsigned> accepted{0},requests{0},serverInvalid{0},clientInvalid{0},listenerInvalid{0},unexpected{0};
    std::atomic<pid_t> peerPID{0};
    dispatch_semaphore_t acceptedSem=dispatch_semaphore_create(0),heldSem=dispatch_semaphore_create(0);
    State(){contexts++;}
    ~State(){if(held)xpc_release(held);for(auto p:peers)xpc_release(p);
        dispatch_release(acceptedSem);dispatch_release(heldSem);[events release];contexts--;}
};
void note(const std::shared_ptr<State> &state,NSString *side,xpc_object_t event){
    NSString *kind=event==XPC_ERROR_CONNECTION_INVALID?@"INVALID":event==XPC_ERROR_CONNECTION_INTERRUPTED?@"INTERRUPTED":
        xpc_get_type(event)==XPC_TYPE_CONNECTION?@"CONNECTION":xpc_get_type(event)==XPC_TYPE_DICTIONARY?@"DICTIONARY":@"OTHER";
    std::lock_guard<std::mutex>lock(state->mutex);[state->events addObject:@{@"side":side,@"kind":kind}];
}
struct Reply {
    dispatch_semaphore_t done=dispatch_semaphore_create(0);
    unsigned callbacks=0;bool error=false;uint64_t sequence=0;std::vector<uint32_t> words;
    ~Reply(){dispatch_release(done);}
};
bool wait(dispatch_semaphore_t value){return dispatch_semaphore_wait(value,dispatch_time(DISPATCH_TIME_NOW,timeout))==0;}
uint32_t transform(uint32_t value,uint32_t seed,unsigned index){
    uint32_t v=value^seed;unsigned shift=index%31+1;
    return ((v<<shift)|(v>>(32-shift)))+uint32_t(index)*1664525u+1013904223u;
}
void readReply(xpc_object_t object,const std::shared_ptr<Reply> &reply){
    reply->callbacks++;
    reply->error=object==XPC_ERROR_CONNECTION_INVALID||object==XPC_ERROR_CONNECTION_INTERRUPTED;
    if(xpc_get_type(object)==XPC_TYPE_DICTIONARY){
        reply->sequence=xpc_dictionary_get_uint64(object,"sequence");size_t bytes=0;
        const void *data=xpc_dictionary_get_data(object,"words",&bytes);
        if(data&&bytes%4==0&&bytes<=16384){reply->words.resize(bytes/4);memcpy(reply->words.data(),data,bytes);}
    }
    dispatch_semaphore_signal(reply->done);
}
void installPeer(xpc_connection_t peer,std::weak_ptr<State> weak,dispatch_queue_t serverQueue){
    // The handler must own a weak_ptr value, never a reference into the
    // listener block: that block may be destroyed before peer cancellation.
    xpc_connection_set_target_queue(peer,serverQueue);
    auto state=weak.lock();if(!state)return;
    xpc_retain(peer);{std::lock_guard<std::mutex> lock(state->mutex);state->peers.push_back(peer);}
    __unsafe_unretained xpc_connection_t borrowedPeer=peer;
    xpc_connection_set_event_handler(peer,^(xpc_object_t message){@autoreleasepool{
        auto state=weak.lock();if(!state)return;
        note(state,@"server",message);
        if(xpc_get_type(message)==XPC_TYPE_ERROR){
            if(message==XPC_ERROR_CONNECTION_INVALID)state->serverInvalid++;else state->unexpected++;
            return;
        }
        if(xpc_get_type(message)!=XPC_TYPE_DICTIONARY){state->unexpected++;return;}
        state->peerPID=xpc_connection_get_pid(borrowedPeer);
        state->requests++;
        if(xpc_dictionary_get_bool(message,"hold")){
            std::lock_guard<std::mutex> lock(state->mutex);
            if(state->held)state->unexpected++;else state->held=xpc_retain(message);
            dispatch_semaphore_signal(state->heldSem);return;
        }
        size_t bytes=0;const void *raw=xpc_dictionary_get_data(message,"words",&bytes);
        if(!raw||!bytes||bytes%4||bytes>16384){state->unexpected++;return;}
        std::vector<uint32_t> input(bytes/4),output(bytes/4);memcpy(input.data(),raw,bytes);
        uint32_t seed=uint32_t(xpc_dictionary_get_uint64(message,"seed"));
        for(unsigned i=0;i<input.size();i++)output[i]=transform(input[i],seed,i);
        xpc_object_t reply=xpc_dictionary_create_reply(message);
        if(!reply){state->unexpected++;return;}
        xpc_dictionary_set_uint64(reply,"sequence",xpc_dictionary_get_uint64(message,"sequence"));
        xpc_dictionary_set_data(reply,"words",output.data(),bytes);
        xpc_connection_send_message(borrowedPeer,reply);xpc_release(reply);
    }});
    xpc_connection_activate(peer);state->accepted++;dispatch_semaphore_signal(state->acceptedSem);
}
bool until(const std::function<bool()> &predicate){
    for(unsigned i=0;i<3000;i++){if(predicate())return true;usleep(1000);}return predicate();
}
NSDictionary *run(NSString *mode,NSString *output,uint32_t seed){
    auto state=std::make_shared<State>();std::weak_ptr<State> weak=state;
    dispatch_queue_t server=dispatch_queue_create("KeplerMetal.owned.server",DISPATCH_QUEUE_SERIAL);
    dispatch_queue_t clientQueue=dispatch_queue_create("KeplerMetal.owned.client",DISPATCH_QUEUE_SERIAL);
    dispatch_queue_t replyQueue=dispatch_queue_create("KeplerMetal.owned.reply",DISPATCH_QUEUE_SERIAL);
    xpc_connection_t listener=xpc_connection_create(nullptr,server);
    xpc_connection_set_event_handler(listener,^(xpc_object_t event){@autoreleasepool{
        auto state=weak.lock();if(!state)return;
        note(state,@"listener",event);
        if(xpc_get_type(event)==XPC_TYPE_CONNECTION)installPeer((xpc_connection_t)event,weak,server);
        else if(event==XPC_ERROR_CONNECTION_INVALID)state->listenerInvalid++;
        else state->unexpected++;
    }});
    xpc_connection_activate(listener);xpc_endpoint_t endpoint=xpc_endpoint_create(listener);
    xpc_connection_t client=xpc_connection_create_from_endpoint(endpoint);
    xpc_connection_set_target_queue(client,clientQueue);
    xpc_connection_set_event_handler(client,^(xpc_object_t event){@autoreleasepool{
        auto state=weak.lock();if(!state)return;
        note(state,@"client",event);
        if(event==XPC_ERROR_CONNECTION_INVALID)state->clientInvalid++;else state->unexpected++;
    }});
    xpc_connection_activate(client);
    bool anonymous=xpc_connection_get_name(listener)==nullptr;
    bool correct=listener&&endpoint&&client&&anonymous;pid_t clientPeerPID=0;NSMutableArray *trials=[NSMutableArray array];
    if([mode isEqual:@"cancel"]){
        // XPC may not know the peer PID until a reply has been received.
        // Prime the connection, then cancel a second, genuinely pending RPC.
        uint32_t word=0x89abcdef;uint64_t primeSequence=0xfedcba9876543210ull;
        xpc_object_t primer=xpc_dictionary_create(nullptr,nullptr,0);
        xpc_dictionary_set_data(primer,"words",&word,4);xpc_dictionary_set_uint64(primer,"seed",seed);
        xpc_dictionary_set_uint64(primer,"sequence",primeSequence);
        auto prime=std::make_shared<Reply>();
        xpc_connection_send_message_with_reply(client,primer,replyQueue,^(xpc_object_t value){readReply(value,prime);});
        xpc_release(primer);bool primed=wait(prime->done);
        bool primeValid=primed&&prime->callbacks==1&&!prime->error&&prime->sequence==primeSequence&&
            prime->words.size()==1&&prime->words[0]==transform(word,seed,0);
        correct&=primeValid;
        [trials addObject:@{@"kind":@"cancellation_primer",@"sequence":@(primeSequence),@"seed":@(seed),
            @"input_word":@(word),@"reply_word":@(prime->words.empty()?0:prime->words[0]),@"correct":@(primeValid)}];
        auto reply=std::make_shared<Reply>();xpc_object_t request=xpc_dictionary_create(nullptr,nullptr,0);
        xpc_dictionary_set_bool(request,"hold",true);
        xpc_connection_send_message_with_reply(client,request,replyQueue,^(xpc_object_t value){readReply(value,reply);});
        xpc_release(request);bool held=wait(state->heldSem);clientPeerPID=xpc_connection_get_pid(client);xpc_connection_cancel(client);
        bool delivered=wait(reply->done);correct&=held&&delivered&&reply->callbacks==1&&reply->error;
        [trials addObject:@{@"kind":@"pending_reply_cancellation",@"request_held":@(held),
            @"reply_observed":@(delivered),@"reply_callbacks":@(reply->callbacks),@"known_error":@(reply->error),@"correct":@(correct)}];
    }else{
        const unsigned sizes[]={1,31,32,33,257,1024,4096};
        for(unsigned trial=0;trial<7&&correct;trial++){
            unsigned n=sizes[trial];std::vector<uint32_t> input(n);
            for(unsigned i=0;i<n;i++)input[i]=uint32_t(seed+trial*971)^uint32_t(i*747796405u+2891336453u);
            NSData *original=[NSData dataWithBytes:input.data() length:n*4];
            uint64_t sequence=0xf000000000000000ull+trial;
            xpc_object_t request=xpc_dictionary_create(nullptr,nullptr,0);
            xpc_dictionary_set_data(request,"words",input.data(),n*4);
            xpc_dictionary_set_uint64(request,"sequence",sequence);xpc_dictionary_set_uint64(request,"seed",seed);
            memset(input.data(),0xa5,n*4); // The dictionary must own a copy.
            auto reply=std::make_shared<Reply>();
            if([mode isEqual:@"sync"]){
                // A worker performs the potentially blocking SDK call. The
                // main thread retains its bounded deadline and child lifetime.
                dispatch_async(replyQueue,^{
                    xpc_object_t value=xpc_connection_send_message_with_reply_sync(client,request);
                    readReply(value,reply);xpc_release(value);xpc_release(request);
                });
            }else{
                xpc_connection_send_message_with_reply(client,request,replyQueue,^(xpc_object_t value){readReply(value,reply);});
                xpc_release(request); // Test pending-request ownership.
            }
            bool received=wait(reply->done);
            if(!received){puts("{\"status\":\"OWNED_XPC_REPLY_TIMEOUT\",\"GPU_work\":0}");fflush(stdout);_exit(2);}
            bool same=reply->callbacks==1&&!reply->error&&reply->sequence==sequence&&reply->words.size()==n;
            for(unsigned i=0;same&&i<n;i++){uint32_t word;memcpy(&word,(const uint8_t*)original.bytes+i*4,4);
                same=reply->words[i]==transform(word,seed,i);}
            NSString *inputFile=[NSString stringWithFormat:@"input-%u.bin",trial],*resultFile=[NSString stringWithFormat:@"reply-%u.bin",trial];
            correct&=[original writeToFile:[output stringByAppendingPathComponent:inputFile]atomically:NO];
            NSData *data=[NSData dataWithBytes:reply->words.data() length:reply->words.size()*4];
            correct&=[data writeToFile:[output stringByAppendingPathComponent:resultFile]atomically:NO]&&same;
            [trials addObject:@{@"trial":@(trial),@"words":@(n),@"sequence":@(sequence),@"seed":@(seed),
                @"input":inputFile,@"reply":resultFile,@"correct":@(same),@"reply_callbacks":@(reply->callbacks)}];
        }
        clientPeerPID=xpc_connection_get_pid(client);xpc_connection_cancel(client);
    }
    bool accepted=wait(state->acceptedSem);
    bool clientEnded=until([&]{return state->clientInvalid.load()==1;});
    std::vector<xpc_connection_t> peers;{std::lock_guard<std::mutex>lock(state->mutex);peers=state->peers;state->peers.clear();
        if(state->held){xpc_release(state->held);state->held=nullptr;}}
    for(auto peer:peers)xpc_connection_cancel(peer);
    xpc_connection_cancel(listener);
    bool serverEnded=until([&]{return state->serverInvalid.load()==1;});
    dispatch_sync(server,^{});dispatch_sync(clientQueue,^{});dispatch_sync(replyQueue,^{});
    bool sameProcess=clientPeerPID==getpid()&&state->peerPID.load()==getpid();
    correct&=accepted&&clientEnded&&serverEnded&&state->accepted==1&&state->unexpected==0&&sameProcess;
    unsigned requests=state->requests,invalidClient=state->clientInvalid,invalidServer=state->serverInvalid;
    NSArray *events=[[[NSArray alloc]initWithArray:state->events]autorelease];
    for(auto peer:peers)xpc_release(peer);
    xpc_release(client);xpc_release(endpoint);xpc_release(listener);
    state.reset();bool destroyed=until([&]{return weak.expired();});correct&=destroyed;
    dispatch_release(server);dispatch_release(clientQueue);dispatch_release(replyQueue);
    return @{@"status":correct?@"PASS":@"FAIL",@"mode":mode,@"seed":@(seed),@"trials":trials,
        @"accepted_connections":@(accepted),@"requests":@(requests),@"client_invalid":@(invalidClient),
        @"server_invalid":@(invalidServer),@"context_destroyed":@(destroyed),@"live_contexts":@(contexts.load()),
        @"events":events,
        @"listener_name_was_NULL":@(anonymous),@"same_process":@(sameProcess),@"client_peer_PID":@(clientPeerPID),
        @"native_private_handler_called":@NO,
        @"public_video_API_called":@NO,@"hardware_video_execution_proved":@NO,@"GPU_work":@0,
        @"named_service_or_launchd_modified":@NO,@"system_modified":@NO,@"performance_benchmark":@NO};
}
}
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=4||![@[@"sync",@"async",@"cancel"]containsObject:@(argv[1])])return 1;
    NSDictionary *result=run(@(argv[1]),@(argv[2]),uint32_t(strtoul(argv[3],nullptr,0)));
    NSData *json=[NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
    puts([[[[NSString alloc]initWithData:json encoding:NSUTF8StringEncoding]autorelease]UTF8String]);
    return [result[@"status"]isEqual:@"PASS"]?0:3;
}}
