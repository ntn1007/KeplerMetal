// SPDX-License-Identifier: MIT
// Pinned own-process dlsym gate. It can return only the known error 14.
// An optional, identity-gated type-3 context open and close uses public IOKit; no private method is invoked.
// This variant reads bounded caller-provided buffers after a pinned call-site check.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach-o/loader.h>
#include <mach/mach_vm.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <atomic>
#include <cerrno>
#include <cstring>
#include <sched.h>
#include <chrono>
#include <algorithm>
extern "C" void *KPLookupControl();
extern "C" int KPLookupMarker();
namespace {
struct Event {std::atomic<bool> ready{false};char name[96]{},caller[1024]{},target[1024]{};uintptr_t callerOffset=0,targetOffset=0;bool found=false,pin=false,replaced=false;};
Event events[64];std::atomic<unsigned> count{0},dropped{0},inflight{0},gateCalls{0};std::atomic<bool> enabled{false};std::atomic<bool> captureReady{false};thread_local bool inside=false,calibration=false;
bool serviceCalibrated=false,contextProbe=false,attachProbe=false;
std::atomic<unsigned> sharedOpenAttempts{0},sharedCloseAttempts{0},attachAttempts{0};
std::atomic<int> sharedOpenStatus{INT32_MIN},sharedCloseStatus{INT32_MIN},attachStatus{INT32_MIN};
bool metalMatches=false,portsDistinct=false;
std::atomic<unsigned> contextOpenAttempts{0},contextCloseAttempts{0};
std::atomic<int> contextOpenStatus{INT32_MIN},contextCloseStatus{INT32_MIN};
bool calibrated=false;NSString *expectedPath=nil,*route=nil;constexpr const char *systemPath="/System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver";
NSString *hash(NSData*d){if(!d)return @"";unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);NSMutableString*s=[NSMutableString string];for(auto b:h)[s appendFormat:@"%02x",b];return s;}
NSData *readOwn(uintptr_t p,size_t n){NSMutableData*d=[NSMutableData dataWithLength:n];mach_vm_size_t got=0;return mach_vm_read_overwrite(mach_task_self(),p,n,(mach_vm_address_t)d.mutableBytes,&got)==KERN_SUCCESS&&got==n?d:nil;}
NSString *uuid(uintptr_t base){
 NSData*head=readOwn(base,sizeof(mach_header_64));if(!head)return nil;auto*h=(const mach_header_64*)head.bytes;
 if(h->magic!=MH_MAGIC_64||h->cputype!=CPU_TYPE_X86_64||h->ncmds>4096||h->sizeofcmds>1048576)return nil;
 NSData*commands=readOwn(base+sizeof(*h),h->sizeofcmds);if(!commands)return nil;size_t at=0;NSString*id=nil;
 for(unsigned i=0;i<h->ncmds;i++){if(at+sizeof(load_command)>commands.length)return nil;auto*c=(const load_command*)((const char*)commands.bytes+at);
  if(c->cmdsize<sizeof(load_command)||c->cmdsize>commands.length-at)return nil;
  if(c->cmd==LC_UUID&&c->cmdsize==sizeof(uuid_command)){if(id)return nil;NSMutableString*s=[NSMutableString string];for(auto b:((const uuid_command*)c)->uuid)[s appendFormat:@"%02x",b];id=s;}at+=c->cmdsize;}
 return at==commands.length?id:nil;
}
bool sameBytes(uintptr_t p,const unsigned char*expected,size_t n){NSData*d=readOwn(p,n);return d&&d.length==n&&!memcmp(d.bytes,expected,n);}
struct Capture {uintptr_t callerOffset=0;bool callerPathMatches=false,callerUUIDMatches=false;bool callerPinned=false;bool slotWritable=false,configReadable=false,outputWritable=false;bool slotZero=false,outputZero=false;bool indexRead=false;uint32_t index=0,mask=0,count=0;bool headerRead=false,arrayReadable=false,selectedInMask=false,selectedInRange=false,selectedNonzero=false;};
Capture capture;
struct ServiceIdentity {bool send=false,classOK=false,idOK=false;uint64_t registry=0;char className[128]{};};
ServiceIdentity selectedIdentity;
bool contextPolicy(bool enabled,const ServiceIdentity &id){return enabled&&id.send&&id.classOK&&id.idOK&&id.registry==4294968416&&!strcmp(id.className,"nvAccelerator");}
void openCloseContext(uint32_t port,const ServiceIdentity &identity){
 if(!contextPolicy(contextProbe,identity))return;
 id<MTLDevice> device=MTLCreateSystemDefaultDevice();
 metalMatches=device&&device.registryID==identity.registry;
 if(!metalMatches){if(device)[device release];return;}
 io_connect_t conn=MACH_PORT_NULL,shared=MACH_PORT_NULL;contextOpenAttempts.fetch_add(1);
 kern_return_t st=IOServiceOpen((io_service_t)port,mach_task_self(),3,&conn);contextOpenStatus.store(st);
 if(st==KERN_SUCCESS&&conn!=MACH_PORT_NULL&&attachProbe){
  sharedOpenAttempts.fetch_add(1);kern_return_t ss=IOServiceOpen((io_service_t)port,mach_task_self(),6,&shared);sharedOpenStatus.store(ss);
  portsDistinct=ss==KERN_SUCCESS&&shared!=MACH_PORT_NULL&&shared!=conn;
  if(portsDistinct){attachAttempts.fetch_add(1);attachStatus.store(IOConnectAddClient(conn,shared));}
 }
 if(conn!=MACH_PORT_NULL){contextCloseAttempts.fetch_add(1);contextCloseStatus.store(IOServiceClose(conn));}
 if(shared!=MACH_PORT_NULL){sharedCloseAttempts.fetch_add(1);sharedCloseStatus.store(IOServiceClose(shared));}
 [device release];
}

ServiceIdentity identifyService(uint32_t port){
 ServiceIdentity result{};mach_port_type_t type=0;
 if(!port||mach_port_type(mach_task_self(),port,&type)!=KERN_SUCCESS||!(type&MACH_PORT_TYPE_SEND))return result;
 result.send=true;result.classOK=IOObjectGetClass((io_object_t)port,result.className)==KERN_SUCCESS;
 if(result.classOK&&!strcmp(result.className,"nvAccelerator"))result.idOK=IORegistryEntryGetRegistryEntryID((io_registry_entry_t)port,&result.registry)==KERN_SUCCESS;
 return result;
}
bool regionAllows(void *p,size_t n,vm_prot_t required){
 if(!p||!n||(uintptr_t)p>UINTPTR_MAX-n)return false;
 mach_vm_address_t addr=(mach_vm_address_t)p;mach_vm_size_t size=0;vm_region_basic_info_data_64_t info{};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=MACH_PORT_NULL;
 kern_return_t kr=mach_vm_region(mach_task_self(),&addr,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);
 if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
 return kr==KERN_SUCCESS&&addr<=(uintptr_t)p&&size>=(uintptr_t)p-addr&&n<=size-((uintptr_t)p-addr)&&(info.protection&required)==required;
}
__attribute__((noinline)) int gate(void *slot,void *config,void *output){
 unsigned n=gateCalls.fetch_add(1,std::memory_order_relaxed);if(n!=0)return 14;
 Dl_info d{};void *caller=__builtin_return_address(0);dladdr(caller,&d);uintptr_t base=(uintptr_t)d.dli_fbase;
 capture.callerOffset=d.dli_fbase?(uintptr_t)caller-base:0;capture.callerPathMatches=d.dli_fname&&expectedPath&&[expectedPath isEqual:@(d.dli_fname)];capture.callerUUIDMatches=base&&[uuid(base)isEqual:@"78a7c6684a3934c99309f3c418487d6f"];
 static const unsigned char invocation[]={0x48,0x8d,0x7d,0xc0,0x48,0x8d,0xb5,0x48,0xfe,0xff,0xff,0x48,0x89,0xda,0x41,0xff,0x96,0x18,0x04,0x00,0x00};
 bool pinned=capture.callerPathMatches&&capture.callerUUIDMatches&&capture.callerOffset==0x24d16&&sameBytes(base+0x24d01,invocation,sizeof(invocation));
 capture.callerPinned=pinned;
 if(pinned){
  capture.slotWritable=regionAllows(slot,8,VM_PROT_READ|VM_PROT_WRITE);
  capture.configReadable=regionAllows(config,4,VM_PROT_READ);
  capture.outputWritable=regionAllows(output,0x128,VM_PROT_READ|VM_PROT_WRITE);
  if(capture.slotWritable){NSData *d=readOwn((uintptr_t)slot,8);if(d){uint64_t x;memcpy(&x,d.bytes,8);capture.slotZero=x==0;}}
  if(regionAllows(config,20,VM_PROT_READ)){
   NSData *h=readOwn((uintptr_t)config,20);if(h){uintptr_t vector=0;memcpy(&capture.index,h.bytes,4);memcpy(&vector,(const char*)h.bytes+8,8);memcpy(&capture.mask,(const char*)h.bytes+16,4);
    capture.indexRead=true;capture.headerRead=true;for(uint32_t x=capture.mask;x;x>>=1)capture.count++;
    capture.selectedInRange=capture.index<capture.count;capture.selectedInMask=capture.index<32&&((capture.mask>>capture.index)&1);
    if(capture.count&&regionAllows((void*)vector,(size_t)capture.count*4,VM_PROT_READ)){
     capture.arrayReadable=true;if(capture.selectedInRange){NSData *e=readOwn(vector+capture.index*4,4);if(e){uint32_t value=0;memcpy(&value,e.bytes,4);capture.selectedNonzero=value!=0;if(value){selectedIdentity=identifyService(value);openCloseContext(value,selectedIdentity);}}}
    }
   }
  }
  if(capture.outputWritable){NSData *d=readOwn((uintptr_t)output,0x128);if(d){const unsigned char*p=(const unsigned char*)d.bytes;capture.outputZero=std::all_of(p,p+0x128,[](unsigned char x){return x==0;});}}
 }
 captureReady.store(true,std::memory_order_release);return 14;
}
int calibrationGate(){return 43;}
__attribute__((noinline)) void *observed(void *handle,const char *name){
 int incoming=errno;if(!enabled.load(std::memory_order_seq_cst)||inside){errno=incoming;return dlsym(handle,name);}
 inflight.fetch_add(1,std::memory_order_seq_cst);if(!enabled.load(std::memory_order_seq_cst)){inflight--;errno=incoming;return dlsym(handle,name);}
 inside=true;void *caller=__builtin_return_address(0);errno=incoming;void *result=dlsym(handle,name);int outgoing=errno;void *answer=result;
 if(calibration&&name&&!strcmp(name,"KPLookupMarker")&&result==(void*)&KPLookupMarker){answer=(void*)&calibrationGate;}
 else if(name&&!strncmp(name,"AVD_",4)){
  @autoreleasepool{
   Dl_info c{},t{};dladdr(caller,&c);if(result)dladdr(result,&t);uintptr_t coff=c.dli_fbase?(uintptr_t)caller-(uintptr_t)c.dli_fbase:0,toff=t.dli_fbase?(uintptr_t)result-(uintptr_t)t.dli_fbase:0;
   static const unsigned char callsite[]={0x48,0x8d,0x35,0x00,0xe6,0x0c,0x00,0xe8,0x99,0x07,0x0a,0x00};
   static const unsigned char stub[]={0x55,0x48,0x89,0xe5,0xb8,0x0e,0x00,0x00,0x00,0x5d,0xc3};
   bool basePin=c.dli_fname&&c.dli_fbase&&expectedPath&&[expectedPath isEqual:@(c.dli_fname)]&&coff==([route isEqual:@"wrong-caller"]?0x23796:0x23795)&&
    [uuid((uintptr_t)c.dli_fbase)isEqual:@"78a7c6684a3934c99309f3c418487d6f"]&&sameBytes((uintptr_t)c.dli_fbase+0x23789,callsite,sizeof(callsite))&&
    t.dli_fname&&t.dli_fbase&&!strcmp(t.dli_fname,systemPath)&&toff==([route isEqual:@"wrong-target"]?0x3fa3:0x3fa2)&&
    [uuid((uintptr_t)t.dli_fbase)isEqual:@"2a283a4a38263b6fb2b2e092931ad628"]&&sameBytes((uintptr_t)result,stub,sizeof(stub));
   bool named=!strcmp(name,[route isEqual:@"wrong-name"]?"AVD_WrongName":"AVD_CreateAVDAccelerator");bool selected=basePin&&named&&![route isEqual:@"passive"];
   if(selected)answer=(void*)&gate;
   unsigned i=count.fetch_add(1);if(i<64){auto&e=events[i];strlcpy(e.name,name,sizeof(e.name));strlcpy(e.caller,c.dli_fname?:"",sizeof(e.caller));strlcpy(e.target,t.dli_fname?:"",sizeof(e.target));
    e.callerOffset=coff;e.targetOffset=toff;e.found=result!=nullptr;e.pin=basePin&&named;e.replaced=selected;e.ready.store(true,std::memory_order_release);
   }else dropped++;
  }
 }
 inside=false;inflight.fetch_sub(1,std::memory_order_seq_cst);errno=outgoing;return answer;
}
__attribute__((used)) static const struct{const void *replacement,*original;} interpose __attribute__((section("__DATA,__interpose")))={(const void*)&observed,(const void*)&dlsym};
}
extern "C" bool KPGateBegin(NSString*assets){
 NSDictionary*p=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"legacy-gva-profile.json"]] options:0 error:nil];
 NSDictionary*choice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"provider-gate-choice.json"]] options:0 error:nil];
 NSDictionary*probeChoice=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"service-probe-choice.json"]] options:0 error:nil];
 if(probeChoice.count!=2||![probeChoice[@"enabled"] isKindOfClass:[NSNumber class]]||![probeChoice[@"attach"] isKindOfClass:[NSNumber class]])return false;contextProbe=[probeChoice[@"enabled"]boolValue];attachProbe=[probeChoice[@"attach"]boolValue];if(attachProbe&&!contextProbe)return false;
 if(choice.count!=1||![@[@"passive",@"enabled",@"wrong-caller",@"wrong-target",@"wrong-name"]containsObject:choice[@"mode"]])return false;
 NSString*path=p[@"path"];if(![p[@"enabled"]boolValue]||![p[@"stage"]isEqual:@"create-only"]||
 ![hash([NSData dataWithContentsOfFile:path])isEqual:@"54dc80c41bab45492d1eb601fb1d242b513107645d068bf24edee155b965681f"]||
 ![hash([NSData dataWithContentsOfFile:@(systemPath)])isEqual:@"2d3894048f5d61f6735955211bba28cb1e1a0ff9a7f556ebb6c144018388a865"])return false;
 io_service_t expected=IOServiceGetMatchingService(kIOMainPortDefault,IOServiceMatching("nvAccelerator"));
 ServiceIdentity known=identifyService(expected),invalid=identifyService(MACH_PORT_NULL);
 serviceCalibrated=contextPolicy(true,known)&&!contextPolicy(false,known)&&!contextPolicy(true,invalid);
 if(expected)IOObjectRelease(expected);if(!serviceCalibrated)return false;
 expectedPath=[path copy];route=[choice[@"mode"]copy];enabled.store(true,std::memory_order_seq_cst);
 void *baseline=KPLookupControl();calibration=true;void *substituted=KPLookupControl();calibration=false;void *again=KPLookupControl();
 calibrated=baseline==(void*)&KPLookupMarker&&substituted==(void*)&calibrationGate&&((int(*)())substituted)()==43&&again==baseline&&!count.load()&&!dropped.load();
 if(!calibrated)enabled.store(false);return calibrated;
}
extern "C" NSDictionary *KPGateSnapshot(){
 enabled.store(false,std::memory_order_seq_cst);auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
 while(inflight.load()&&std::chrono::steady_clock::now()<deadline)sched_yield();bool drained=!inflight.load();unsigned missing=0;
 NSMutableArray*a=[NSMutableArray array];for(unsigned i=0;i<std::min(count.load(),64u);i++){auto&e=events[i];if(!e.ready.load(std::memory_order_acquire)){missing++;continue;}
 [a addObject:@{@"name":@(e.name),@"caller_image":@(e.caller),@"caller_offset":@(e.callerOffset),@"target_image":@(e.target),@"target_offset":@(e.targetOffset),@"found":@(e.found),@"identity_pin":@(e.pin),@"result_replaced":@(e.replaced)}];}
 return @{@"status":calibrated&&drained&&!missing&&!dropped.load()?@"COMPLETE":@"INCOMPLETE",@"calibration_pass":@(calibrated),@"service_calibration_pass":@(serviceCalibrated),@"context_probe_enabled":@(contextProbe),@"context_open_attempts":@(contextOpenAttempts.load()),@"context_open_status":@(contextOpenStatus.load()),@"context_close_attempts":@(contextCloseAttempts.load()),@"context_close_status":@(contextCloseStatus.load()),@"association_probe_enabled":@(attachProbe),@"metal_registry_matches":@(metalMatches),@"shared_open_attempts":@(sharedOpenAttempts.load()),@"shared_open_status":@(sharedOpenStatus.load()),@"shared_close_attempts":@(sharedCloseAttempts.load()),@"shared_close_status":@(sharedCloseStatus.load()),@"connections_distinct":@(portsDistinct),@"association_attempts":@(attachAttempts.load()),@"association_status":@(attachStatus.load()),@"mode":route?:@"",@"events":a,@"gate_calls":@(gateCalls.load()),@"gate_return":@14,@"dropped":@(dropped.load()),@"drained":@(drained),@"sierra_loaded":@NO,@"sierra_export_called":@NO,@"gate_reads_arguments":@YES,@"argument_observation":@{@"ready":@(captureReady.load(std::memory_order_acquire)),@"caller_pinned":@(capture.callerPinned),@"caller_offset":@(capture.callerOffset),@"caller_path_matches":@(capture.callerPathMatches),@"caller_UUID_matches":@(capture.callerUUIDMatches),@"slot_region_read_write":@(capture.slotWritable),@"slot_initially_zero":@(capture.slotZero),@"config_region_readable":@(capture.configReadable),@"config_first_word_read":@(capture.indexRead),@"config_first_word":@(capture.index),@"config_header_20_read":@(capture.headerRead),@"display_mask":@(capture.mask),@"display_array_required_count":@(capture.count),@"display_array_region_readable":@(capture.arrayReadable),@"selected_index_in_mask":@(capture.selectedInMask),@"selected_index_in_range":@(capture.selectedInRange),@"selected_display_value_nonzero":@(capture.selectedNonzero),@"selected_port_send_right":@(selectedIdentity.send),@"selected_service_class_ok":@(selectedIdentity.classOK),@"selected_service_class":@(selectedIdentity.classOK?selectedIdentity.className:""),@"selected_service_registry_ok":@(selectedIdentity.idOK),@"selected_service_registry_ID":@(selectedIdentity.registry),@"output_region_read_write_296":@(capture.outputWritable),@"output_296_initially_zero":@(capture.outputZero),@"region_is_not_allocation_size_proof":@YES},@"explicit_gpu_dispatches_by_gate":@0,@"explicit_video_external_methods":@0,@"system_modified":@NO,@"hardware_video_execution_proved":@NO};
}
