#import "KeplerNativeCommands.h"
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <mach/vm_region.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstdint>
#include <cstring>
#include <vector>

namespace {
bool fail(NSError **error,NSString *message){if(error)*error=[NSError errorWithDomain:@"KeplerNativeCommands" code:1 userInfo:@{NSLocalizedDescriptionKey:message}];return false;}
NSData *readMemory(uintptr_t p,size_t bytes){if(!p||!bytes||bytes>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:bytes];mach_vm_size_t actual=0;return mach_vm_read_overwrite(mach_task_self(),p,bytes,(mach_vm_address_t)d.mutableBytes,&actual)==KERN_SUCCESS&&actual==bytes?d:nil;}
uint64_t u64(NSData*d,size_t offset){uint64_t r=0;if(offset+8<=d.length)memcpy(&r,(const char*)d.bytes+offset,8);return r;}
uint32_t u32(NSData*d,size_t offset){uint32_t r=0;if(offset+4<=d.length)memcpy(&r,(const char*)d.bytes+offset,4);return r;}
void put32(NSMutableData*d,size_t offset,uint32_t v){memcpy((char*)d.mutableBytes+offset,&v,4);}
NSString *sha(NSData*d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
NSUInteger volume(MTLSize d,NSUInteger cap){NSUInteger n=1;for(NSUInteger v:{d.width,d.height,d.depth}){if(!v||n>cap/v)return 0;n*=v;}return n;}
MTLSize shape(NSArray*a,NSUInteger width){return a.count==3?MTLSizeMake([a[0]unsignedIntegerValue],[a[1]unsignedIntegerValue],[a[2]unsignedIntegerValue]):MTLSizeMake(width,1,1);}
struct Cursor{uintptr_t impl,push,current,end,queue;};
Cursor cursor(id<MTLComputeCommandEncoder>e){Cursor c={};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;memcpy(&c.impl,(const char*)(__bridge const void*)e+120,8);NSData*i=readMemory(c.impl,64);c.push=u64(i,32);c.queue=u64(i,16);NSData*p=readMemory(c.push,144);c.current=u64(p,0);c.end=u64(p,136);return c;}
bool writable(uintptr_t p,size_t bytes){if(!p||!bytes||p+bytes<p)return false;mach_vm_address_t address=p;mach_vm_size_t size=0;vm_region_basic_info_data_64_t info={};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=MACH_PORT_NULL;kern_return_t result=mach_vm_region(mach_task_self(),&address,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);return result==KERN_SUCCESS&&address<=p&&p+bytes<=address+size&&(info.protection&VM_PROT_WRITE);}
struct Packet{size_t header,data,count;unsigned method,mode,channel;};
bool packets(NSData*d,std::vector<Packet>&result){if((d.length!=464&&d.length!=496)||d.length%4)return false;size_t i=0;while(i<d.length){size_t start=i;uint32_t h=u32(d,i);i+=4;unsigned mode=h>>29,method=(h&0x1fff)*4,channel=(h>>13)&7,count=(h>>16)&0x1fff;if(channel!=1||(mode!=1&&mode!=3&&mode!=4)||!count)return false;size_t payload=mode==4?0:count*4;if(i+payload>d.length)return false;result.push_back({start,i,count,method,mode,channel});i+=payload;}return result.size()==(d.length==496?12:9);}
}

BOOL KPCompareResidentPrimer(NSData*original,NSData*current,BOOL permitsInactiveCB0,NSDictionary**evidence){
 if([original isEqual:current]){if(evidence)*evidence=@{@"exact_bytes":@YES,@"inactive_CB0_descriptor_normalized":@NO};return YES;}
 if(!permitsInactiveCB0||original.length!=current.length)return NO;
 std::vector<Packet>a,b;if(!packets(original,a)||!packets(current,b))return NO;
 size_t prefix=original.length==496?3:0,qmd=a[prefix+5].data;
 if(qmd!=b[prefix+5].data||(u32(original,qmd+0x50)&255)!=6||(u32(current,qmd+0x50)&255)!=6)return NO;
 NSMutableData*normalized=[current mutableCopy];put32(normalized,qmd+0x74,u32(original,qmd+0x74));put32(normalized,qmd+0x78,u32(original,qmd+0x78));
 if(![normalized isEqual:original])return NO;
 if(evidence)*evidence=@{@"exact_bytes":@NO,@"inactive_CB0_descriptor_normalized":@YES,@"constant_buffer_valid_mask":@6,@"ignored_QMD_word_offsets":@[@116,@120],@"active_fields_and_other_bytes_exact":@YES,@"current_commands_replayed":@NO};return YES;
}
BOOL KPResidentProfilePermitsInactiveCB0(NSDictionary*p,id<MTLComputePipelineState>pipeline){
 return [p[@"native_registration_v1"]boolValue]&&[p[@"binding_layout_v2"]boolValue]&&pipeline&&p[@"pipeline_owner"]==pipeline&&p[@"library_owner"]&&[p[@"registration_id"]length]&&[p[@"library_SHA256"]length]==64&&[p[@"manifest_SHA256"]length]==64&&!p[@"native_literal_bank_0"];
}

@implementation KPRecordedNativeCompute {
 id<MTLCommandQueue> _queue;
 id<MTLComputePipelineState> _pipeline;
 id<MTLBuffer> _output,_counter,_parameters,_nativeConstants,_nativeDescriptor;
 NSData *_originalCommands,*_relocatedCommands;
 id<MTLBuffer> _constants,_descriptor;
 NSDictionary *_relocationEvidence;
 NSDictionary *_profile,*_bindingState;
 id _literalVariantOwner;
 NSUInteger _groups,_local,_launchHeader,_launchData;
 MTLSize _groupsShape,_localShape;
 uintptr_t _queueCpp;
 id<MTLCommandBuffer> _residentInitialization;
}
- (NSData*)originalCommands{return _originalCommands;}
- (NSData*)relocatedCommands{return _relocatedCommands;}
- (id<MTLBuffer>)constants{return _constants;}
- (id<MTLBuffer>)descriptor{return _descriptor;}
- (NSDictionary*)relocationEvidence{return _relocationEvidence;}
- (BOOL)residentDescriptorReady{return _residentInitialization&&_residentInitialization.status==MTLCommandBufferStatusCompleted;}
- (BOOL)validateResidentThreadgroupMemory:(NSError**)error {
 NSDictionary*memory=_profile[@"dynamic_threadgroup"];NSUInteger length=[_profile[@"dynamic_threadgroup_length"]unsignedIntegerValue];
 if(!memory)return length?fail(error,@"Resident static owner has dynamic shared bytes"):YES;
 NSUInteger offset=[memory[@"parameter_word_offset"]unsignedIntegerValue],base=_bindingState?[_bindingState[_profile[@"constant_buffer_index"]][@"offset"]unsignedIntegerValue]:0;uint32_t words=0;
 if(![_profile[@"native_registration_v1"]boolValue]||length%16||length<[memory[@"min_bytes"]unsignedIntegerValue]||length>[memory[@"max_bytes"]unsignedIntegerValue]||length+[_profile[@"static_threadgroup_bytes"]unsignedIntegerValue]>49152||_parameters.storageMode==MTLStorageModePrivate||!_parameters.contents||base>_parameters.length||offset>_parameters.length-base||_parameters.length-base-offset<4)return fail(error,@"Resident retained dynamic shared state is outside its registration");
 memcpy(&words,(const char*)_parameters.contents+base+offset,4);if(uint64_t(words)*4!=length)return fail(error,@"Resident retained dynamic shared parameter differs from its allocation");
 return YES;
}
+ (instancetype)recordedCommands:(NSData*)commands queue:(id<MTLCommandQueue>)queue pipeline:(id<MTLComputePipelineState>)pipeline output:(id<MTLBuffer>)output counter:(id<MTLBuffer>)counter parameters:(id<MTLBuffer>)parameters nativeConstants:(id<MTLBuffer>)nativeConstants nativeDescriptor:(id<MTLBuffer>)nativeDescriptor constantSnapshot:(NSData*)snapshot groups:(NSUInteger)groups local:(NSUInteger)local error:(NSError**)error {
 return [self recordedCommands:commands queue:queue pipeline:pipeline output:output counter:counter parameters:parameters nativeConstants:nativeConstants nativeDescriptor:nativeDescriptor constantSnapshot:snapshot groups:groups local:local profile:nil error:error];
}
+ (instancetype)recordedCommands:(NSData*)commands queue:(id<MTLCommandQueue>)queue pipeline:(id<MTLComputePipelineState>)pipeline output:(id<MTLBuffer>)output counter:(id<MTLBuffer>)counter parameters:(id<MTLBuffer>)parameters nativeConstants:(id<MTLBuffer>)nativeConstants nativeDescriptor:(id<MTLBuffer>)nativeDescriptor constantSnapshot:(NSData*)snapshot groups:(NSUInteger)groups local:(NSUInteger)local profile:(NSDictionary*)profile error:(NSError**)error {
 NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];
 if(![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"]){fail(error,@"Driver identity changed");return nil;}
 BOOL extended=[profile[@"binding_layout_v2"]boolValue];NSDictionary*bindings=profile[@"binding_state_v2"];NSUInteger parameterOffset=extended?[bindings[profile[@"constant_buffer_index"]][@"offset"]unsignedIntegerValue]:0;NSUInteger limit=extended?[profile[@"max_invocations"]unsignedIntegerValue]:640;MTLSize groupsShape=shape(profile[@"groups_shape"],groups),localShape=shape(profile[@"local_shape"],local);NSUInteger localCount=volume(localShape,pipeline.maxTotalThreadsPerThreadgroup),groupCount=volume(groupsShape,limit);
 if(!queue||!pipeline||pipeline.device!=queue.device||(!extended&&(output.length!=10368||counter.length<132))||parameterOffset>parameters.length||parameters.length-parameterOffset<512||parameters.length-parameterOffset>65536||snapshot.length!=65536||nativeConstants.length!=393216||nativeDescriptor.length!=4096||!groups||!local||!localCount||!groupCount||groupsShape.width!=groups||localShape.width!=local||localShape.width>1024||localShape.height>1024||localShape.depth>64||groupsShape.width>0x7fffffff||groupsShape.height>65535||groupsShape.depth>65535||groupCount>limit/localCount||(![profile[@"multidimensional_grid"]boolValue]&&(groupsShape.height!=1||groupsShape.depth!=1||localShape.height!=1||localShape.depth!=1))){fail(error,@"Unqualified binding/geometry/allocation profile");return nil;}
 BOOL manifestProfile=[profile[@"native_registration_v1"]boolValue];NSUInteger dynamicBytes=[profile[@"dynamic_threadgroup_length"]unsignedIntegerValue],staticBytes=[profile[@"static_threadgroup_bytes"]unsignedIntegerValue];
 if(profile){if(manifestProfile){if(profile[@"pipeline_owner"]!=pipeline||!profile[@"library_owner"]||[(id<MTLLibrary>)profile[@"library_owner"]device]!=queue.device||[profile[@"library_SHA256"]length]!=64||[profile[@"manifest_SHA256"]length]!=64||![profile[@"registration_id"]length]||localCount>[profile[@"max_local"]unsignedIntegerValue]||dynamicBytes%16||dynamicBytes+staticBytes>49152||pipeline.staticThreadgroupMemoryLength!=staticBytes||[profile[@"expected_register_count"]unsignedIntegerValue]<1||[profile[@"expected_register_count"]unsignedIntegerValue]>63){fail(error,@"Native manifest profile ownership/resource metadata differs");return nil;}}
 else{NSString*name=profile[@"function"],*library=profile[@"library_SHA256"];BOOL shared=[name isEqual:@"profile_shared"];if(![library isEqual:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd"]||(!shared&&![name isEqual:@"profile_integer"]&&![name isEqual:@"profile_fma"])||staticBytes!=(shared?512:0)||local>(shared?128:1024)||pipeline.staticThreadgroupMemoryLength!=(shared?512:0)||dynamicBytes){fail(error,@"Unqualified registered native-library profile");return nil;}}}

 if(extended){if(![bindings isKindOfClass:[NSDictionary class]]||bindings.count!=[profile[@"binding_specs"]count]){fail(error,@"Missing schema2 binding snapshot");return nil;}for(NSNumber*index in bindings){NSDictionary*binding=bindings[index];id<MTLBuffer>b=binding[@"buffer"];NSUInteger offset=[binding[@"offset"]unsignedIntegerValue];if(index.unsignedIntegerValue>=16||b.device!=queue.device||offset>b.length||u64(snapshot,index.unsignedIntegerValue*32+8)!=b.gpuAddress+offset){fail(error,@"Native schema2 buffer table differs from retained bindings");return nil;}}}
 else if(u64(snapshot,8)!=output.gpuAddress+64||u64(snapshot,40)!=counter.gpuAddress+64||u64(snapshot,72)!=parameters.gpuAddress){fail(error,@"Native constant resource table differs from retained bindings");return nil;}
 // This shader profile has no self-pointers into the native scratch allocations.
 for(size_t o=0;o<snapshot.length;o+=8){uint64_t v=u64(snapshot,o);if((nativeConstants.gpuAddress<=v&&v<nativeConstants.gpuAddress+nativeConstants.length)||(nativeDescriptor.gpuAddress<=v&&v<nativeDescriptor.gpuAddress+nativeDescriptor.length)){fail(error,@"Unqualified native scratch self-reference");return nil;}}
 std::vector<Packet>p;if(!packets(commands,p)){fail(error,@"Unqualified/truncated native packet stream");return nil;}
 size_t prefix=commands.length==496?3:0;if(bool(prefix)!=bool(dynamicBytes)||prefix&&!manifestProfile){fail(error,@"Dynamic shared prelude/profile mismatch");return nil;}
 if(prefix){if(p[0].method!=0x180||p[0].mode!=1||p[0].count!=4||p[1].method!=0x1b0||p[1].mode!=4||p[1].count!=17||p[2].method!=0x1b4||p[2].mode!=3||p[2].count!=1||u32(commands,p[0].data)!=4||u32(commands,p[0].data+4)!=1||((uint64_t(u32(commands,p[0].data+8))<<32)|u32(commands,p[0].data+12))!=nativeConstants.gpuAddress+0x640||u32(commands,p[2].data)!=staticBytes){fail(error,@"Dynamic threadgroup pointer prelude differs");return nil;}}
 if(prefix&&u32(snapshot,0x640)!=u32(commands,p[2].data)){fail(error,@"Captured dynamic threadgroup base word differs from native prelude");return nil;}
 unsigned expectedMethods[9]={0x180,0x1b0,0x1b4,0x180,0x1b0,0x1b4,0x2b4,0x2bc,0x110};unsigned expectedModes[9]={1,4,3,1,4,3,1,1,1};unsigned expectedCounts[9]={4,17,32,4,17,64,1,1,1};
 for(unsigned i=0;i<9;i++)if(p[prefix+i].method!=expectedMethods[i]||p[prefix+i].mode!=expectedModes[i]||p[prefix+i].count!=expectedCounts[i]){fail(error,@"Unexpected method or payload in pinned direct profile");return nil;}
 uint64_t cbTarget=(uint64_t(u32(commands,p[prefix+0].data+8))<<32)|u32(commands,p[prefix+0].data+12),qmdTarget=(uint64_t(u32(commands,p[prefix+3].data+8))<<32)|u32(commands,p[prefix+3].data+12);
 size_t qmd=p[prefix+5].data;
 // QMDv00_06 bits544:561 are shared-memory bytes. Bits640:647 are
 // CONSTANT_BUFFER_VALID, not a register count; the mask6 means CB1+CB2.
 if(profile&&(u32(commands,qmd+0x44)&0x3ffff)!=staticBytes+dynamicBytes){fail(error,@"Native QMD static shared memory differs from reflected profile");return nil;}
 if(profile&&((u32(commands,qmd+0xb8)>>24)!=[profile[@"expected_register_count"]unsignedIntegerValue]||(!manifestProfile&&[profile[@"expected_register_count"]unsignedIntegerValue]!=([profile[@"function"]isEqual:@"profile_shared"]?8:7)))){fail(error,@"Native register count differs from captured registered profile");return nil;}
 uint64_t cb1=(uint64_t(u32(commands,qmd+0x80)&255)<<32)|u32(commands,qmd+0x7c),cb2=(uint64_t(u32(commands,qmd+0x88)&255)<<32)|u32(commands,qmd+0x84);
 unsigned expectedConstantMask=6;id literalOwner=nil;NSMutableDictionary *literalEvidence=[NSMutableDictionary new];
 if(profile[@"native_literal_bank_0"]){
  Ivar pipelineIvar=class_getInstanceVariable(object_getClass(pipeline),"_computePipeline");
  if(![NSStringFromClass(object_getClass(pipeline))isEqual:@"NVMTLComputePipelineState"]||!pipelineIvar||ivar_getOffset(pipelineIvar)!=72){fail(error,@"Native literal pipeline layout differs");return nil;}
  uintptr_t cpp=0;memcpy(&cpp,(const char*)(__bridge const void*)pipeline+72,8);NSData *state=readMemory(cpp,32);
  if(state.length!=32||u64(state,8)!=(uintptr_t)(__bridge const void*)pipeline||!u64(state,16)){fail(error,@"Native literal pipeline-owner identity differs");return nil;}
  literalOwner=(__bridge id)(void*)(uintptr_t)u64(state,16);
  Ivar variantIvar=class_getInstanceVariable(object_getClass(literalOwner),"_variant");
  if(![NSStringFromClass(object_getClass(literalOwner))isEqual:@"NVMTLFunctionVariant"]||!variantIvar||ivar_getOffset(variantIvar)!=32){fail(error,@"Native literal variant owner differs");return nil;}
  uintptr_t variant=0;memcpy(&variant,(const char*)(__bridge const void*)literalOwner+32,8);NSData *fields=readMemory(variant,128);uint64_t codeAddress=u64(fields,16),codeBytes=u64(fields,24);
  uint64_t cb0=(uint64_t(u32(commands,qmd+0x78)&255)<<32)|u32(commands,qmd+0x74);unsigned cb0Bytes=u32(commands,qmd+0x78)>>15;
  if(fields.length!=128||!codeAddress||!codeBytes||codeBytes>65536||codeBytes%64||cb0!=codeAddress+((codeBytes+255)&~uint64_t(255))||cb0Bytes!=[profile[@"native_literal_bank_0"][@"bytes"]unsignedIntegerValue]||(cb0Bytes!=256&&cb0Bytes!=512&&cb0Bytes!=1024)||u32(fields,48)!=[profile[@"expected_register_count"]unsignedIntegerValue]){fail(error,@"Native CB0 code-allocation relation, length or registers differs");return nil;}
  expectedConstantMask=7;[literalEvidence addEntriesFromDictionary:@{@"GPU_address":@(cb0),@"bytes":@(cb0Bytes),@"native_code_GPU_address":@(codeAddress),@"native_code_bytes":@(codeBytes),@"address_relation":@"native_code_end_aligned_256",@"variant_owner_class":NSStringFromClass(object_getClass(literalOwner)),@"variant_owner_retained":@YES,@"literal_contents_CPU_read":@NO}];
 }
 if(cbTarget!=nativeConstants.gpuAddress+0x6f0||qmdTarget!=nativeDescriptor.gpuAddress||cb1!=nativeConstants.gpuAddress||cb2!=parameters.gpuAddress+parameterOffset||u32(commands,p[prefix+0].data)!=128||u32(commands,p[prefix+0].data+4)!=1||u32(commands,p[prefix+3].data)!=256||u32(commands,p[prefix+3].data+4)!=1||u32(commands,qmd+0x30)!=groups||u32(commands,qmd+0x34)!=(groupsShape.height|(groupsShape.depth<<16))||u32(commands,qmd+0x48)>>16!=local||u32(commands,qmd+0x4c)!=(localShape.height|(localShape.depth<<16))||(u32(commands,qmd+0x50)&255)!=expectedConstantMask||(u32(commands,qmd+0x80)>>15)!=65536||(u32(commands,qmd+0x88)>>15)!=(parameters.length-parameterOffset)||u32(commands,p[prefix+6].data)!=(nativeDescriptor.gpuAddress>>8)||u32(commands,p[prefix+7].data)!=3||u32(commands,p[prefix+8].data)!=0){
  NSString *details=[NSString stringWithFormat:@"Native QMD, CB, upload or launch invariants differ: cbTarget=%llu/%llu qmdTarget=%llu/%llu cb1=%llu/%llu cb2=%llu/%llu uploadCB=%u,%u uploadQMD=%u,%u groups=%u,%u local=%u,%u mask=%u cbSizes=%u,%u expectedCB2=%lu qmdAddr=%u/%llu launch=%u wait=%u",(unsigned long long)cbTarget,(unsigned long long)(nativeConstants.gpuAddress+0x6f0),(unsigned long long)qmdTarget,(unsigned long long)nativeDescriptor.gpuAddress,(unsigned long long)cb1,(unsigned long long)nativeConstants.gpuAddress,(unsigned long long)cb2,(unsigned long long)(parameters.gpuAddress+parameterOffset),u32(commands,p[prefix+0].data),u32(commands,p[prefix+0].data+4),u32(commands,p[prefix+3].data),u32(commands,p[prefix+3].data+4),u32(commands,qmd+0x30),u32(commands,qmd+0x34),u32(commands,qmd+0x48)>>16,u32(commands,qmd+0x4c),u32(commands,qmd+0x50)&255,u32(commands,qmd+0x80)>>15,u32(commands,qmd+0x88)>>15,(unsigned long)(parameters.length-parameterOffset),u32(commands,p[prefix+6].data),(unsigned long long)(nativeDescriptor.gpuAddress>>8),u32(commands,p[prefix+7].data),u32(commands,p[prefix+8].data)];fail(error,details);return nil;
 }
 KPRecordedNativeCompute*r=[self new];r->_queue=queue;r->_pipeline=pipeline;r->_profile=[profile copy];r->_bindingState=[bindings copy];r->_literalVariantOwner=literalOwner;r->_output=output;r->_counter=counter;r->_parameters=parameters;r->_nativeConstants=nativeConstants;r->_nativeDescriptor=nativeDescriptor;r->_groups=groups;r->_local=local;r->_groupsShape=groupsShape;r->_localShape=localShape;r->_originalCommands=[commands copy];
 Ivar queueIvar=class_getInstanceVariable(object_getClass(queue),"_queue");if(!queueIvar||ivar_getOffset(queueIvar)!=680){fail(error,@"Queue layout changed");return nil;}memcpy(&r->_queueCpp,(const char*)(__bridge const void*)queue+680,8);
 r->_constants=[queue.device newBufferWithLength:65536 options:MTLResourceStorageModePrivate];r->_descriptor=[queue.device newBufferWithLength:4096 options:MTLResourceStorageModePrivate];
 if(!r->_constants||!r->_descriptor||(r->_constants.gpuAddress&255)||(r->_descriptor.gpuAddress&255)||r->_constants.gpuAddress>>40||r->_descriptor.gpuAddress>>8>UINT32_MAX){fail(error,@"Dedicated allocations missing or not QMD/CB aligned");return nil;}
 NSMutableData*patched=[commands mutableCopy];uint64_t cb=r->_constants.gpuAddress,desc=r->_descriptor.gpuAddress;
 if(prefix){put32(patched,p[0].data+8,(uint32_t)((cb+0x640)>>32));put32(patched,p[0].data+12,(uint32_t)(cb+0x640));}
 put32(patched,p[prefix+0].data+8,(uint32_t)((cb+0x6f0)>>32));put32(patched,p[prefix+0].data+12,(uint32_t)(cb+0x6f0));
 put32(patched,p[prefix+3].data+8,(uint32_t)(desc>>32));put32(patched,p[prefix+3].data+12,(uint32_t)desc);
 put32(patched,qmd+0x7c,(uint32_t)cb);put32(patched,qmd+0x80,(u32(patched,qmd+0x80)&0xffffff00u)|(uint32_t)(cb>>32));
 put32(patched,p[prefix+6].data,(uint32_t)(desc>>8));r->_relocatedCommands=[patched copy];r->_launchHeader=p[prefix+7].header;r->_launchData=p[prefix+7].data;
 NSMutableArray*bindingRows=[NSMutableArray new];for(NSNumber*index in [bindings.allKeys sortedArrayUsingSelector:@selector(compare:)]){NSDictionary*b=bindings[index];id<MTLBuffer>resource=b[@"buffer"];[bindingRows addObject:@{@"index":index,@"GPU_address":@(resource.gpuAddress),@"offset":b[@"offset"],@"length":@(resource.length),@"native_table_address":@(u64(snapshot,index.unsignedIntegerValue*32+8))}];}
 r->_relocationEvidence=@{@"groups_shape":@[@(groupsShape.width),@(groupsShape.height),@(groupsShape.depth)],@"local_shape":@[@(localShape.width),@(localShape.height),@(localShape.depth)],@"binding_layout_v2":@(extended),@"bindings":bindingRows,@"native_CB_GPU_address":@(nativeConstants.gpuAddress),@"native_QMD_GPU_address":@(nativeDescriptor.gpuAddress),@"dedicated_CB_GPU_address":@(cb),@"dedicated_QMD_GPU_address":@(desc),@"parameters_GPU_address":@(parameters.gpuAddress),@"parameters_offset":@(parameterOffset),@"constant_buffer_bytes":@(parameters.length-parameterOffset),@"output_GPU_address":@(output.gpuAddress),@"counter_GPU_address":@(counter.gpuAddress),@"original_SHA256":sha(commands),@"relocated_SHA256":sha(patched),@"launch_header_offset":@(p[prefix+7].header),@"launch_data_offset":@(p[prefix+7].data),@"strong_bindings_retained":@YES,@"ICB_object":@NO,@"constant_buffer_valid_mask":@(u32(commands,qmd+0x50)&255),@"native_literal_bank_0":literalEvidence,@"static_threadgroup_bytes":@(staticBytes),@"dynamic_threadgroup_length":@(dynamicBytes),@"QMD_total_shared_bytes":@(u32(commands,qmd+0x44)&0x3ffff),@"native_register_count":@(u32(commands,qmd+0xb8)>>24),@"command_bytes":@(commands.length),@"optional_shared_prelude_bytes":@(prefix?32:0),@"dynamic_threadgroup_base_word":@(prefix?u32(commands,p[2].data):0),@"dynamic_threadgroup_base_matches_static":@(prefix&&u32(commands,p[2].data)==staticBytes),@"function":profile[@"function"]?:@"consume_grid",@"library_SHA256":profile[@"library_SHA256"]?:@"b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d",@"profile":profile?@"Registered native-library buffer ABI, original QMD/pipeline metadata":@"Native consume_grid, direct compute, exact driver, CB1/CB2 and fixed geometry"};return r;
}
- (BOOL)encodeCopies:(NSUInteger)copies encoder:(id<MTLComputeCommandEncoder>)encoder suppressLaunches:(BOOL)suppress evidence:(NSDictionary**)evidence error:(NSError**)error {
 return [self encodeSequence:@[self] repetitions:copies encoder:encoder suppressElementIndexes:suppress?[NSIndexSet indexSetWithIndex:0]:[NSIndexSet indexSet] evidence:evidence error:error];
}
- (BOOL)initializeResidentDescriptorInCommandBuffer:(id<MTLCommandBuffer>)cb evidence:(NSDictionary**)evidence error:(NSError**)error {
 if(evidence)*evidence=nil;
 if(_residentInitialization||!cb||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return fail(error,@"Resident initializer requires a new retained recording buffer from its queue");
 std::vector<Packet>p;if(!packets(_relocatedCommands,p))return fail(error,@"Resident QMD source stream is not validated");
 size_t prefix=_relocatedCommands.length==496?3:0;NSData*qmd=[_relocatedCommands subdataWithRange:NSMakeRange(p[prefix+5].data,256)];
 id<MTLBuffer>staging=[_queue.device newBufferWithBytes:qmd.bytes length:256 options:MTLResourceStorageModeShared];if(!staging)return fail(error,@"Cannot allocate QMD initialization staging");
 id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];if(!b)return fail(error,@"Cannot create QMD initializer blit");
 [b copyFromBuffer:staging sourceOffset:0 toBuffer:_descriptor destinationOffset:0 size:256];[b endEncoding];_residentInitialization=cb;
 if(evidence)*evidence=@{@"operation":@"initialize_resident_QMD",@"bytes":@256,@"QMD_SHA256":sha(qmd),@"descriptor_GPU_address":@(_descriptor.gpuAddress),@"user_kernel_dispatches":@0,@"GPU_blit":@YES,@"CPU_descriptor_state":@"already validated relocated QMD",@"system_modified":@NO};return YES;
}
- (BOOL)encodeResidentDescriptorWithOwners:(NSArray<KPRecordedNativeCompute*>*)owners encoder:(id<MTLComputeCommandEncoder>)encoder suppress:(BOOL)suppress evidence:(NSDictionary**)evidence error:(NSError**)error {
 return [self encodeResidentSequence:@[self] owners:owners encoder:encoder suppressElementIndexes:suppress?[NSIndexSet indexSetWithIndex:0]:[NSIndexSet indexSet] evidence:evidence error:error];
}
- (BOOL)encodeResidentSequence:(NSArray<KPRecordedNativeCompute*>*)elements owners:(NSArray<KPRecordedNativeCompute*>*)owners encoder:(id<MTLComputeCommandEncoder>)encoder suppressElementIndexes:(NSIndexSet*)suppressed evidence:(NSDictionary**)evidence error:(NSError**)error {
 if(evidence)*evidence=nil;
 if(!elements.count||elements.count>16||elements.firstObject!=self||suppressed.lastIndex!=NSNotFound&&suppressed.lastIndex>=elements.count||!_residentInitialization||_residentInitialization.status!=MTLCommandBufferStatusCompleted||!owners.count||owners.count>16||![owners containsObject:self]||!encoder||encoder.device!=_queue.device||encoder.dispatchType!=MTLDispatchTypeSerial)return fail(error,@"Resident launch requires initialized validated owners and serial encoder");
 for(KPRecordedNativeCompute*r in owners){
  if(object_getClass(r)!=object_getClass(self))return fail(error,@"Resident owner class differs");
  BOOL fixed=r->_pipeline==_pipeline&&!memcmp(&r->_groupsShape,&_groupsShape,sizeof(MTLSize))&&!memcmp(&r->_localShape,&_localShape,sizeof(MTLSize));
  NSArray*functions=@[@"profile_integer",@"profile_fma",@"profile_shared"];NSString*library=@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd";
  BOOL registeredMix=[_profile[@"library_SHA256"]isEqual:library]&&[r->_profile[@"library_SHA256"]isEqual:library]&&[functions containsObject:_profile[@"function"]]&&[functions containsObject:r->_profile[@"function"]];
  BOOL manifestMix=[_profile[@"native_registration_v1"]boolValue]&&[r->_profile[@"native_registration_v1"]boolValue]&&_profile[@"pipeline_owner"]==_pipeline&&r->_profile[@"pipeline_owner"]==r->_pipeline&&_profile[@"library_owner"]==r->_profile[@"library_owner"]&&[_profile[@"registration_id"]length]&&[_profile[@"registration_id"]isEqual:r->_profile[@"registration_id"]]&&[_profile[@"library_SHA256"]isEqual:r->_profile[@"library_SHA256"]]&&[_profile[@"manifest_SHA256"]isEqual:r->_profile[@"manifest_SHA256"]];
  registeredMix=registeredMix||manifestMix;
  if(object_getClass(r)!=object_getClass(self)||r->_queue!=_queue||r->_queueCpp!=_queueCpp||(!fixed&&!registeredMix)||!r->_residentInitialization||r->_residentInitialization.status!=MTLCommandBufferStatusCompleted)return fail(error,@"Resident owner queue/registration/initialization differs");
  if(![r validateResidentThreadgroupMemory:error])return NO;
 }
 NSMutableData*stream=[NSMutableData data];NSMutableArray*descriptors=[NSMutableArray array];
 for(NSUInteger index=0;index<elements.count;index++){
  KPRecordedNativeCompute*r=elements[index];if(![owners containsObject:r])return fail(error,@"Every resident record must be retained in the flat owner set");
  std::vector<Packet>p;if(!packets(r->_relocatedCommands,p))return fail(error,@"Resident launch source packet differs");size_t prefix=r->_relocatedCommands.length==496?3:0;
  NSMutableData*part=[NSMutableData dataWithData:[r->_relocatedCommands subdataWithRange:NSMakeRange(p[prefix+6].header,r->_relocatedCommands.length-p[prefix+6].header)]];
  if(part.length!=24||u32(part,0)!=0x200120ad||u32(part,8)!=0x200120af||u32(part,16)!=0x20012044)return fail(error,@"Resident launch/select/wait pattern differs");
  if([suppressed containsIndex:index]){put32(part,8,(u32(part,8)&~0x1fffu)|(0x100/4));put32(part,12,0);}
  [stream appendData:part];[descriptors addObject:@(r->_descriptor.gpuAddress)];
 }
 Ivar v=class_getInstanceVariable(object_getClass(encoder),"_commandBuffer");if(!v||ivar_getOffset(v)!=32)return fail(error,@"Resident encoder command-buffer ABI differs");id<MTLCommandBuffer>cb=object_getIvar(encoder,v);
 if(!cb||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return fail(error,@"Resident execution requires an uncommitted retained command buffer");
 [encoder setComputePipelineState:_pipeline];if(_bindingState){for(NSNumber*index in [_bindingState.allKeys sortedArrayUsingSelector:@selector(compare:)]){NSDictionary*b=_bindingState[index];[encoder setBuffer:b[@"buffer"]offset:[b[@"offset"]unsignedIntegerValue]atIndex:index.unsignedIntegerValue];}}else{[encoder setBuffer:_output offset:64 atIndex:0];[encoder setBuffer:_counter offset:64 atIndex:1];[encoder setBuffer:_parameters offset:0 atIndex:2];}if([_profile[@"dynamic_threadgroup_length"]unsignedIntegerValue])[encoder setThreadgroupMemoryLength:[_profile[@"dynamic_threadgroup_length"]unsignedIntegerValue]atIndex:0];
 for(KPRecordedNativeCompute*r in owners){NSMutableArray*resources=[NSMutableArray arrayWithObjects:r->_constants,r->_descriptor,nil];if(r->_bindingState){for(NSDictionary*b in r->_bindingState.allValues)[resources addObject:b[@"buffer"]];}else[resources addObjectsFromArray:@[r->_output,r->_counter,r->_parameters]];for(id<MTLResource>resource in resources)[encoder useResource:resource usage:MTLResourceUsageRead|MTLResourceUsageWrite];}
 NSArray*retained=[owners copy];[cb addCompletedHandler:^(id<MTLCommandBuffer>completed){(void)retained.count;}];
 Cursor before=cursor(encoder);if(!before.current||before.queue!=_queueCpp)return fail(error,@"Resident command cursor identity differs");
 [encoder dispatchThreadgroups:_groupsShape threadsPerThreadgroup:_localShape];Cursor after=cursor(encoder);
 NSData*primer=before.push==after.push&&after.current>=before.current&&after.current-before.current<=65536?readMemory(before.current,after.current-before.current):nil;
 // Registered reflected profiles retain their original library/pipeline.
 // Only inactive CB0 descriptor words may vary, with both VALID masks6;
 // all active fields, packet bytes and other banks must still match exactly.
 BOOL permitsInactiveCB0=KPResidentProfilePermitsInactiveCB0(_profile,_pipeline);
 NSDictionary*primerComparison=nil;
 if(!KPCompareResidentPrimer(_originalCommands,primer,permitsInactiveCB0,&primerComparison)){
  NSMutableArray*changes=[NSMutableArray new];
  if(primer.length==_originalCommands.length)for(NSUInteger i=0;i+4<=primer.length;i+=4)if(u32(primer,i)!=u32(_originalCommands,i))[changes addObject:@{@"byte_offset":@(i),@"original":@(u32(_originalCommands,i)),@"current":@(u32(primer,i))}];
  NSData*detail=[NSJSONSerialization dataWithJSONObject:@{@"original_bytes":@(_originalCommands.length),@"current_bytes":@(primer.length),@"original_SHA256":sha(_originalCommands),@"current_SHA256":primer?sha(primer):@"",@"changed_words":changes}options:0 error:nil];
  return fail(error,[@"Resident preparation differs; discard this command buffer. " stringByAppendingString:[[NSString alloc]initWithData:detail encoding:NSUTF8StringEncoding]]);
 }
 if(before.end!=after.end||before.current+stream.length>=before.end||!writable(before.push,8)||!writable(before.current,stream.length))return fail(error,@"Resident command capacity/protection differs");
 memcpy((void*)before.current,stream.bytes,stream.length);uintptr_t end=before.current+stream.length;memcpy((void*)before.push,&end,8);
 NSData*written=readMemory(before.current,stream.length);if(![written isEqual:stream]||cursor(encoder).current!=end)return fail(error,@"Resident command bytes differ; discard command buffer");
 NSMutableArray*ownerProfiles=[NSMutableArray array];for(KPRecordedNativeCompute*r in owners)[ownerProfiles addObject:@{@"original_record_function":r->_profile[@"function"]?:@"consume_grid",@"descriptor_GPU_address":@(r->_descriptor.gpuAddress),@"groups_shape":r->_relocationEvidence[@"groups_shape"],@"local_shape":r->_relocationEvidence[@"local_shape"],@"static_threadgroup_bytes":r->_relocationEvidence[@"static_threadgroup_bytes"],@"dynamic_threadgroup_bytes":r->_relocationEvidence[@"dynamic_threadgroup_length"],@"QMD_total_shared_bytes":r->_relocationEvidence[@"QMD_total_shared_bytes"],@"dynamic_base_word_validated":@([r->_profile[@"dynamic_threadgroup_length"]unsignedIntegerValue]!=0),@"dynamic_threadgroup_base_word":r->_relocationEvidence[@"dynamic_threadgroup_base_word"],@"dynamic_threadgroup_base_matches_static":r->_relocationEvidence[@"dynamic_threadgroup_base_matches_static"],@"native_register_count":r->_relocationEvidence[@"native_register_count"],@"binding_layout_v2":r->_relocationEvidence[@"binding_layout_v2"],@"constant_buffer_valid_mask":r->_relocationEvidence[@"constant_buffer_valid_mask"],@"native_literal_bank_0":r->_relocationEvidence[@"native_literal_bank_0"],@"registration_id":r->_profile[@"registration_id"]?:@"",@"manifest_SHA256":r->_profile[@"manifest_SHA256"]?:@""}];
 if(evidence)*evidence=@{@"operation":elements.count==1?@"resident_QMD_launch":@"resident_QMD_sequence_launch",@"command_bytes":@(stream.length),@"stream_SHA256":sha(written),@"descriptor_GPU_address":@(_descriptor.gpuAddress),@"descriptor_GPU_addresses":descriptors,@"resident_launches":@(elements.count),@"native_preparation_GPU_dispatches":@0,@"CPU_QMD_uploads_in_launch":@0,@"CPU_constant_uploads_in_launch":@0,@"owners":@(owners.count),@"owner_original_profiles":ownerProfiles,@"primer_comparison":primerComparison,@"launch_suppressed":@(suppressed.count!=0),@"system_modified":@NO,@"full_ICB_contract":@NO};return YES;
}
- (BOOL)encodeSequence:(NSArray<KPRecordedNativeCompute*>*)elements repetitions:(NSUInteger)repetitions encoder:(id<MTLComputeCommandEncoder>)encoder suppressElementIndexes:(NSIndexSet*)suppressed evidence:(NSDictionary**)evidence error:(NSError**)error {
 if(!elements.count||elements.firstObject!=self||!repetitions||elements.count>16||repetitions>16/elements.count||!encoder||encoder.device!=_queue.device||suppressed.lastIndex!=NSNotFound&&suppressed.lastIndex>=elements.count)return fail(error,@"Unqualified sequence/count/device");
 for(KPRecordedNativeCompute*r in elements){BOOL registeredMix=_profile&&r->_profile&&[r->_profile[@"library_SHA256"]isEqual:_profile[@"library_SHA256"]]&&(![_profile[@"native_registration_v1"]boolValue]||[r->_profile[@"registration_id"]isEqual:_profile[@"registration_id"]]);if(object_getClass(r)!=object_getClass(self)||r->_queue!=_queue||r->_queueCpp!=_queueCpp||(r->_pipeline!=_pipeline&&!registeredMix))return fail(error,@"Mixed queue or unregistered pipeline is not qualified");}
 Ivar cbVar=class_getInstanceVariable(object_getClass(encoder),"_commandBuffer");if(!cbVar||ivar_getOffset(cbVar)!=32)return fail(error,@"Command-buffer layout changed");id<MTLCommandBuffer>cb=object_getIvar(encoder,cbVar);if(cb.status!=MTLCommandBufferStatusNotEnqueued||cb.commandQueue!=_queue)return fail(error,@"Only uncommitted buffers from the recording queue are accepted");
 [encoder setComputePipelineState:_pipeline];if(_bindingState){for(NSNumber*index in [_bindingState.allKeys sortedArrayUsingSelector:@selector(compare:)]){NSDictionary*b=_bindingState[index];[encoder setBuffer:b[@"buffer"] offset:[b[@"offset"]unsignedIntegerValue] atIndex:index.unsignedIntegerValue];}}else{[encoder setBuffer:_output offset:64 atIndex:0];[encoder setBuffer:_counter offset:64 atIndex:1];[encoder setBuffer:_parameters offset:0 atIndex:2];}if([_profile[@"dynamic_threadgroup_length"]unsignedIntegerValue])[encoder setThreadgroupMemoryLength:[_profile[@"dynamic_threadgroup_length"]unsignedIntegerValue] atIndex:0];
 for(KPRecordedNativeCompute*element in elements){NSMutableArray*resources=[NSMutableArray arrayWithObjects:element->_constants,element->_descriptor,nil];if(element->_bindingState){for(NSDictionary*b in element->_bindingState.allValues)[resources addObject:b[@"buffer"]];}else[resources addObjectsFromArray:@[element->_output,element->_counter,element->_parameters]];for(id<MTLResource>r in resources)[encoder useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];}
 // Default retention also holds the actual pipeline/library owners through
 // completion. An unretained CB still requires the caller to keep them alive.
 if(cb.retainedReferences){NSArray*owners=[elements copy];[cb addCompletedHandler:^(id<MTLCommandBuffer>completed){(void)owners.count;}];}
 Cursor before=cursor(encoder);if(!before.current||before.queue!=_queueCpp)return fail(error,@"Native encoder/queue identity changed");
 // One native call prepares the existing driver's state/resource registrations.
 // Its command bytes are removed before commit; no priming kernel executes.
 [encoder dispatchThreadgroups:_groupsShape threadsPerThreadgroup:_localShape];Cursor after=cursor(encoder);
 NSData*primer=(before.push==after.push&&after.current>=before.current&&after.current-before.current<=65536)?readMemory(before.current,after.current-before.current):nil;
 if(!primer||![primer isEqual:_originalCommands])return fail(error,@"Native preparation stream changed; discard this command buffer");
 NSMutableData*stream=[NSMutableData data];NSMutableArray*elementEvidence=[NSMutableArray new];
 for(NSUInteger index=0;index<elements.count;index++){KPRecordedNativeCompute*r=elements[index];NSMutableData*part=[r->_relocatedCommands mutableCopy];BOOL suppress=[suppressed containsIndex:index];if(suppress){uint32_t header=u32(part,r->_launchHeader);put32(part,r->_launchHeader,(header&~0x1fffu)|(0x100/4));put32(part,r->_launchData,0);} // PGRAPH NOP, not a malformed LAUNCH.
  [stream appendData:part];[elementEvidence addObject:@{@"index":@(index),@"groups":@(r->_groups),@"local":@(r->_local),@"launch_suppressed":@(suppress),@"commands_SHA256":sha(part),@"relocation":r->_relocationEvidence}];}
 size_t bytes=stream.length*repetitions;
 if(before.push!=after.push||after.end!=before.end||before.current+bytes>=before.end||!writable(before.push,8)||!writable(before.current,bytes))return fail(error,@"Command cursor capacity/protection changed; discard this command buffer");
 for(NSUInteger i=0;i<repetitions;i++)memcpy((void*)(before.current+i*stream.length),stream.bytes,stream.length);
 uintptr_t end=before.current+bytes;memcpy((void*)before.push,&end,8);
 NSData*written=readMemory(before.current,bytes);NSMutableData*wanted=[NSMutableData data];for(NSUInteger i=0;i<repetitions;i++)[wanted appendData:stream];
 if(![written isEqual:wanted]||cursor(encoder).current!=end)return fail(error,@"Written own-process stream differs; discard this command buffer");
 if(evidence)*evidence=@{@"native_preparation_API_calls":@1,@"native_preparation_GPU_dispatches":@0,@"raw_packet_copies":@(elements.count*repetitions),@"sequence_repetitions":@(repetitions),@"sequence_elements":@(elements.count),@"launches_suppressed":@(suppressed.count==elements.count),@"elements":elementEvidence,@"command_bytes":@(bytes),@"stream_SHA256":sha(written),@"cursor_before":@(before.current),@"cursor_after":@(end),@"push":@(before.push),@"write_scope":@"Own uncommitted encoder command words and cursor only",@"system_modified":@NO,@"ICB_implemented":@NO};return YES;
}
@end
