// Experimental import through the installed driver's observed shader constructor.
// All changes are to our own program data and the method table of this process.
// No driver file, OCLP state, kernel method or hardware register is modified.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <vector>
#include <cstring>
#include <cstdio>
#include <chrono>
#include <algorithm>
#include <cmath>

struct Parameters {uint64_t addresses[4];uint32_t grid[3];uint32_t block[3];};
static_assert(sizeof(Parameters)==56,"Observed constant-buffer ABI");
static IMP originalInit;
static NSData *nakCode;
static NSString *directory;
static NSMutableArray *retainedPayloads,*events;
static bool replaceCode,contractVerified;
static NSString *configuredMode;
using Clock=std::chrono::steady_clock;
static double elapsedMS(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
static float normalInput(uint32_t index,unsigned run,uint32_t salt){
 uint32_t bits=(index+1)*0x9e3779b9u+(run+1)*salt;
 bits^=bits>>16;bits*=0x7feb352du;bits^=bits>>15;bits*=0x846ca68bu;bits^=bits>>16;
 uint32_t exponent=100+(bits%55);bits=(bits&0x807fffffu)|(exponent<<23);
 float value;memcpy(&value,&bits,4);return value;
}
__attribute__((noinline)) static void cpuAdd(const float*__restrict a,const float*__restrict b,float*__restrict out,uint32_t count){
 for(uint32_t i=0;i<count;i++)out[i]=a[i]+b[i];
}
struct Section {size_t header,payload,size;uint32_t type;};
static uint32_t u32(const unsigned char*b,size_t offset){uint32_t v;memcpy(&v,b+offset,4);return v;}
static uint64_t u64(const unsigned char*b,size_t offset){uint64_t v;memcpy(&v,b+offset,8);return v;}
static void put32(unsigned char*b,size_t offset,uint32_t value){memcpy(b+offset,&value,4);}
static bool sections(const unsigned char*b,size_t size,std::vector<Section>&out){
 if(size<32||(u32(b,0)!=7&&u32(b,0)!=8)||u32(b,4)!=size)return false;
 size_t offset=8;for(unsigned n=0;n<32;n++){
  if(offset>size-16)return false;uint64_t next=u64(b,offset);uint32_t type=u32(b,offset+8),bytes=u32(b,offset+12);
  if(bytes>size-offset-16)return false;out.push_back({offset,offset+16,bytes,type});
  if(!next)return out.back().payload+out.back().size==size;
  if(next<16ull+bytes||next>size-offset)return false;offset+=next;
 }return false;
}
static id observedInit(id self,SEL selector,const void*input,NSUInteger length,id device){
 const unsigned char*b=(const unsigned char*)input;std::vector<Section>table;
 NSMutableDictionary*event=[NSMutableDictionary dictionary];event[@"original_container_bytes"]=@(length);
 bool valid=sections(b,length,table);Section metadata={},code={};unsigned metadataCount=0,codeCount=0;
 if(valid)for(const Section&s:table){if(s.type==0x10004){metadata=s;metadataCount++;}if(s.type==0x10005){code=s;codeCount++;}}
 valid=valid && table.front().type==1 && table.front().size==4 && u32(b,table.front().payload)==5;
 valid=valid && metadataCount==1 && codeCount==1 && metadata.size==232 && code.size%64==0;
 const void*passed=input;NSUInteger passedSize=length;NSMutableData*patched=nil;
 if(replaceCode && valid && nakCode.length && nakCode.length%64==0){
  uint32_t oldRegisters=u32(b,metadata.payload+28);
  valid=oldRegisters>0 && oldRegisters<=63 && (!u64(b,code.header)||u64(b,code.header)==16+code.size);
  if(valid){
   patched=[NSMutableData dataWithBytes:input length:code.payload];[patched appendData:nakCode];
   [patched appendBytes:b+code.payload+code.size length:length-code.payload-code.size];
   unsigned char*bytes=(unsigned char*)patched.mutableBytes;
   put32(bytes,4,(uint32_t)patched.length);put32(bytes,code.header+12,(uint32_t)nakCode.length);
   if(u64(b,code.header)){uint64_t next=16+nakCode.length;memcpy(bytes+code.header,&next,8);}
   // Metadata word 7 matches the original shader's register count (6/8).
   // Validate the driver's decoded count below before any dispatch.
   uint32_t requestedRegisters=[configuredMode isEqualToString:@"native_patch"]?oldRegisters:24;
   put32(bytes,metadata.payload+28,requestedRegisters);
   // Controlled differential experiment: values observed in the branch carrier.
   if([configuredMode hasPrefix:@"stack_"]){put32(bytes,metadata.payload+36,576);put32(bytes,metadata.payload+44,576);}
   event[@"original_launch_words_9_11"]=@[@(u32(b,metadata.payload+36)),@(u32(b,metadata.payload+44))];
   event[@"passed_launch_words_9_11"]=@[@(u32(bytes,metadata.payload+36)),@(u32(bytes,metadata.payload+44))];
   [retainedPayloads addObject:patched];passed=patched.bytes;passedSize=patched.length;
   event[@"original_registers"]=@(oldRegisters);event[@"requested_registers"]=@(requestedRegisters);
   event[@"original_code_bytes"]=@(code.size);event[@"nak_code_bytes"]=@(nakCode.length);
   event[@"code_payload_offset"]=@(code.payload);
   event[@"container_saved"]=@([patched writeToFile:[directory stringByAppendingPathComponent:@"imported.compiler-output.bin"] atomically:YES]);
  }
 }
 event[@"container_layout_valid"]=@(valid);event[@"code_replaced"]=@(patched!=nil);
 id result=((id(*)(id,SEL,const void*,NSUInteger,id))originalInit)(self,selector,passed,passedSize,device);
 if(result){
  Ivar ivar=class_getInstanceVariable(object_getClass(result),"_variant");uintptr_t pointer=0;
  if(ivar)memcpy(&pointer,(const char*)result+ivar_getOffset(ivar),8);
  unsigned char variant[128]={};mach_vm_size_t read=0;
  kern_return_t status=pointer?mach_vm_read_overwrite(mach_task_self(),pointer,sizeof variant,(mach_vm_address_t)variant,&read):KERN_INVALID_ADDRESS;
  event[@"variant_read_status"]=@(status);
  if(status==KERN_SUCCESS && read==sizeof variant){
   uint64_t decodedSize=u64(variant,24);uint32_t decodedRegisters=u32(variant,48);
   event[@"driver_decoded_code_bytes"]=@(decodedSize);event[@"driver_decoded_registers"]=@(decodedRegisters);
   contractVerified=patched && decodedSize==nakCode.length && decodedRegisters==[event[@"requested_registers"] unsignedIntValue];
  }
 }
 [events addObject:event];return result;
}
static bool saveJSON(NSDictionary*result){
 NSData*data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
 if(!data)return false;fwrite(data.bytes,1,data.length,stdout);putchar('\n');return true;
}
static uint64_t legacyAddress(id<MTLBuffer>buffer){
 Ivar ivar=class_getInstanceVariable(object_getClass(buffer),"_res");
 if(!ivar)return 0;size_t offset=ivar_getOffset(ivar);
 if(offset+16>class_getInstanceSize(object_getClass(buffer)))return 0;
 uint64_t address=0;memcpy(&address,(const char*)buffer+offset+8,8);return address;
}
int main(int argc,char**argv){@autoreleasepool{
 if(argc<5||argc>8){fprintf(stderr,"usage: nak_macos_probe CARRIER.metallib NAK.sass OUTDIR MODE [COUNT [WARMUPS TRIALS]]\n");return 1;}
 NSString*mode=@(argv[4]);replaceCode=![mode isEqualToString:@"control"];
 NSSet*allowed=[NSSet setWithArray:@[@"control",@"import",@"addresses",@"execute",@"marker",@"metadata",@"native_patch",@"straight_marker",@"straight_add",@"stack_marker",@"stack_execute"]];
 if(![allowed containsObject:mode])return 2;
 configuredMode=mode;
 bool execute=[mode isEqualToString:@"execute"]||[mode isEqualToString:@"control"]||[mode isEqualToString:@"marker"]||[mode isEqualToString:@"metadata"]||[mode isEqualToString:@"native_patch"]||[mode isEqualToString:@"straight_marker"]||[mode isEqualToString:@"straight_add"]||[mode isEqualToString:@"stack_marker"]||[mode isEqualToString:@"stack_execute"];
 bool inspectAddresses=[mode isEqualToString:@"addresses"];
 uint32_t count=argc>=6?(uint32_t)strtoul(argv[5],NULL,10):1;if(!count||count>1048576)return 2;
 unsigned warmups=argc==8?(unsigned)strtoul(argv[6],NULL,10):0,trials=argc==8?(unsigned)strtoul(argv[7],NULL,10):0;
 if(argc==7||(argc==8&&(!warmups||warmups>10||trials<3||trials>30||(![mode isEqualToString:@"straight_add"]&&![mode isEqualToString:@"execute"]&&![mode isEqualToString:@"stack_execute"]))))return 2;
 if([mode isEqualToString:@"straight_add"]&&count%32)return 2;
 directory=@(argv[3]);[[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:nil error:nil];
 events=[NSMutableArray array];retainedPayloads=[NSMutableArray array];nakCode=[NSData dataWithContentsOfFile:@(argv[2])];
 if(!nakCode||!nakCode.length||nakCode.length>65536||nakCode.length%64)return 3;
 id<MTLDevice>device=MTLCreateSystemDefaultDevice();if(!device||![device.name containsString:@"880M"])return 4;
 Class cls=objc_getClass("NVMTLFunctionVariant");Method method=class_getInstanceMethod(cls,sel_registerName("initWithCompilerOutput:size:device:"));
 if(!method||strcmp(method_getTypeEncoding(method),"@40@0:8r^v16Q24@32"))return 5;
 originalInit=method_setImplementation(method,(IMP)observedInit);
 NSError*error=nil;id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:@(argv[1])] error:&error];
 id<MTLComputePipelineState>pipeline=nil;
 if(library)pipeline=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"add_buffers"] error:&error];
 method_setImplementation(method,originalInit);
 NSMutableDictionary*result=[NSMutableDictionary dictionaryWithDictionary:@{
  @"mode":mode,@"device":device.name,@"registry_id":@(device.registryID),@"pipeline_created":@(pipeline!=nil),
  @"import_contract_verified":@(contractVerified),@"events":events,@"gpu_dispatch":@NO,
  @"error":error.description ?: @"",@"scope":@"experimental program import within our process; installed driver owns GPU"}];
 if(!pipeline||(replaceCode&&!contractVerified)){saveJSON(result);return 6;}
 if([device respondsToSelector:@selector(currentAllocatedSize)])result[@"metal_reported_allocated_bytes_after_pipeline"]=@(device.currentAllocatedSize);
 if(!execute&&!inspectAddresses){saveJSON(result);return 0;}
 const uint32_t total=(count+47+31)&~31u;const float canary=-123456.f;
 std::vector<float>a(total),b(total),out(total,canary);
 for(uint32_t i=0;i<total;i++){a[i]=float(int(i%127)-63)*.25f;b[i]=float(int(i%31)-15)*.5f;}
 id<MTLBuffer>ba=[device newBufferWithBytes:a.data() length:total*4 options:MTLResourceStorageModeShared];
 id<MTLBuffer>bb=[device newBufferWithBytes:b.data() length:total*4 options:MTLResourceStorageModeShared];
 id<MTLBuffer>bo=[device newBufferWithBytes:out.data() length:total*4 options:MTLResourceStorageModeShared];
 id<MTLBuffer>bn=[device newBufferWithBytes:&count length:4 options:MTLResourceStorageModeShared];
 if(!ba||!bb||!bo||!bn)return 7;
 Parameters parameters={{ba.gpuAddress,bb.gpuAddress,bo.gpuAddress,bn.gpuAddress},{count,1,1},{32,1,1}};
 id<MTLBuffer>bp=[device newBufferWithBytes:&parameters length:sizeof parameters options:MTLResourceStorageModeShared];
 if(!bp||!ba.gpuAddress||!bb.gpuAddress||!bo.gpuAddress||!bn.gpuAddress)return 8;
 result[@"address_comparison"]=@[
   @{@"role":@"a",@"public":@(ba.gpuAddress),@"legacy_vendor_1":@(legacyAddress(ba))},
   @{@"role":@"b",@"public":@(bb.gpuAddress),@"legacy_vendor_1":@(legacyAddress(bb))},
   @{@"role":@"output",@"public":@(bo.gpuAddress),@"legacy_vendor_1":@(legacyAddress(bo))},
   @{@"role":@"count",@"public":@(bn.gpuAddress),@"legacy_vendor_1":@(legacyAddress(bn))}];
 if(inspectAddresses){saveJSON(result);return 0;}
 if(trials){
  id<MTLCommandQueue>queue=[device newCommandQueue];if(!queue)return 9;
  NSMutableArray*samples=[NSMutableArray array];unsigned allBad=0,allBadGuard=0;
  std::vector<float>cpu(count),readback(total);
  for(unsigned run=0;run<warmups+trials;run++){@autoreleasepool{
   // Different inputs and a reset output rule out a cached previous result.
   for(uint32_t i=0;i<count;i++){a[i]=normalInput(i,run,0x85ebca6bu);b[i]=normalInput(i,run,0xc2b2ae35u);}
   Clock::time_point start=Clock::now();cpuAdd(a.data(),b.data(),cpu.data(),count);double cpuMS=elapsedMS(start);
   start=Clock::now();memcpy(ba.contents,a.data(),total*4);memcpy(bb.contents,b.data(),total*4);
   std::fill((float*)bo.contents,(float*)bo.contents+total,canary);double uploadMS=elapsedMS(start);
   start=Clock::now();id<MTLCommandBuffer>command=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];
   [encoder setComputePipelineState:pipeline];[encoder setBuffer:bp offset:0 atIndex:0];[encoder setBuffer:bo offset:0 atIndex:1];
   [encoder useResource:ba usage:MTLResourceUsageRead];[encoder useResource:bb usage:MTLResourceUsageRead];
   [encoder useResource:bn usage:MTLResourceUsageRead];[encoder useResource:bo usage:MTLResourceUsageWrite];
   [encoder dispatchThreadgroups:MTLSizeMake(([mode isEqualToString:@"straight_add"]?count:total)/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
   [encoder endEncoding];[command commit];[command waitUntilCompleted];double submitWaitMS=elapsedMS(start);
   if(command.status!=MTLCommandBufferStatusCompleted){result[@"command_error"]=command.error.description?:@"";saveJSON(result);return 9;}
   start=Clock::now();memcpy(readback.data(),bo.contents,total*4);double readbackMS=elapsedMS(start);
   unsigned bad=0,badGuard=0;double maxError=0;
   for(uint32_t i=0;i<count;i++){if(readback[i]!=cpu[i])bad++;maxError=std::max(maxError,std::fabs(double(readback[i])-double(cpu[i])));}
   for(uint32_t i=count;i<total;i++)if(readback[i]!=canary)badGuard++;
   allBad+=bad;allBadGuard+=badGuard;
   if(run>=warmups)[samples addObject:@{@"trial":@(run-warmups),@"cpu_ms":@(cpuMS),@"host_upload_reset_ms":@(uploadMS),
    @"encode_submit_wait_ms":@(submitWaitMS),@"gpu_command_ms":@((command.GPUEndTime-command.GPUStartTime)*1000),
    @"host_readback_ms":@(readbackMS),@"wall_with_host_copies_ms":@(uploadMS+submitWaitMS+readbackMS),
    @"mismatches":@(bad),@"changed_guard_elements":@(badGuard),@"max_absolute_error":@(maxError),@"command_status":@(command.status)}];
   if(bad||badGuard)break;
  }}
  result[@"gpu_dispatch"]=@YES;result[@"active_elements"]=@(count);result[@"guard_elements"]=@(total-count);
  result[@"warmups"]=@(warmups);result[@"measured_trials"]=@(samples.count);result[@"samples"]=samples;
  result[@"mismatches_including_warmups"]=@(allBad);result[@"changed_guard_elements_including_warmups"]=@(allBadGuard);
  result[@"requested_shared_buffer_bytes"]=@(uint64_t(total)*12+4+sizeof parameters);
  result[@"memory_note"]=@"shared Metal buffers; initial allocations and pipeline creation excluded; upload/reset and readback separately timed; command timestamp is not a VRAM-only kernel metric";
  result[@"cpu_note"]=@"one thread, optimized C++ add with restrict, same float32 inputs; validation outside timing";
  result[@"input_pattern"]=@"deterministic float32 normals with hashed sign/mantissa/exponents 100..154; seed changes every trial; NaN, infinity and subnormals not qualified";
  if([device respondsToSelector:@selector(currentAllocatedSize)])result[@"metal_reported_allocated_bytes_after_trials"]=@(device.currentAllocatedSize);
  saveJSON(result);return allBad||allBadGuard?10:0;
 }
 id<MTLCommandQueue>queue=[device newCommandQueue];id<MTLCommandBuffer>command=[queue commandBuffer];
 id<MTLComputeCommandEncoder>encoder=[command computeCommandEncoder];[encoder setComputePipelineState:pipeline];
 [encoder setBuffer:bp offset:0 atIndex:0];[encoder setBuffer:bo offset:0 atIndex:1];
 [encoder useResource:ba usage:MTLResourceUsageRead];[encoder useResource:bb usage:MTLResourceUsageRead];
 [encoder useResource:bn usage:MTLResourceUsageRead];[encoder useResource:bo usage:MTLResourceUsageWrite];
 if([mode isEqualToString:@"straight_marker"]){[encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];}
 else if([mode isEqualToString:@"straight_add"]){[encoder dispatchThreadgroups:MTLSizeMake(count/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];}
 else {[encoder dispatchThreadgroups:MTLSizeMake(total/32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];}[encoder endEncoding];
 [command commit];[command waitUntilCompleted];
 result[@"gpu_dispatch"]=@YES;result[@"command_status"]=@(command.status);result[@"command_error"]=command.error.description ?: @"";
 result[@"gpu_seconds"]=@(command.GPUEndTime-command.GPUStartTime);result[@"active_elements"]=@(count);result[@"guard_elements"]=@(total-count);
 result[@"buffer_gpu_addresses"]=@[@(ba.gpuAddress),@(bb.gpuAddress),@(bo.gpuAddress),@(bn.gpuAddress),@(bp.gpuAddress)];
 if(command.status!=MTLCommandBufferStatusCompleted){saveJSON(result);return 9;}
 const float*values=(const float*)bo.contents;unsigned bad=0,badGuard=0;
 uint64_t sum=parameters.addresses[0]+parameters.addresses[1]+parameters.addresses[2]+parameters.addresses[3];
 float carrierValue=float(sum&65535)+float(parameters.grid[1]+parameters.grid[2]+parameters.block[0]+parameters.block[1]+parameters.block[2]);
 for(uint32_t i=0;i<count;i++){float expected=([mode isEqualToString:@"marker"]||[mode isEqualToString:@"stack_marker"]||[mode isEqualToString:@"straight_marker"]||[mode isEqualToString:@"native_patch"])?77.f:(([mode isEqualToString:@"metadata"]||!replaceCode)?carrierValue:a[i]+b[i]);if(values[i]!=expected)bad++;}
 for(uint32_t i=count;i<total;i++)if(values[i]!=canary)badGuard++;
 result[@"mismatches"]=@(bad);result[@"changed_guard_elements"]=@(badGuard);result[@"first_value"]=@(values[0]);
 result[@"first_add_expected"]=@(a[0]+b[0]);result[@"carrier_expected"]=@(carrierValue);
 NSData*output=[NSData dataWithBytes:values length:total*4];[output writeToFile:[directory stringByAppendingPathComponent:@"output.f32"] atomically:YES];
 saveJSON(result);return bad||badGuard?10:0;
}}
