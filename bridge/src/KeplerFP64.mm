#import "KeplerFP64.h"
#import "KeplerProgramImport.h"
#import "KeplerGPUIdentity.h"
#import <objc/runtime.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>

// Generated from this SDK's offline-built, decoded program set. Never inferred
// from caller-supplied metadata. The generator/source hashes are in the package.
struct KPFP64Pin {const char *name,*sha; unsigned local,gprs,bytes;};
#include "KeplerFP64Programs.inc"
extern "C" id<MTLComputePipelineState> KPInternalCreateApprovedSM30Pipeline(
 id<MTLDevice>,NSData*,NSString*,NSData*,KeplerImportConfig,NSError**,NSDictionary**)
 NS_RETURNS_RETAINED;
static NSString*digest(NSData*d){
 if(!d||d.length>UINT32_MAX)return nil;
 unsigned char h[32];CC_SHA256(d.bytes,(CC_LONG)d.length,h);
 NSMutableString*s=[NSMutableString string];for(unsigned char x:h)[s appendFormat:@"%02x",x];return s;
}
static BOOL fail(NSError**e,NSString*s){if(e)*e=[NSError errorWithDomain:@"KeplerFP64" code:1 userInfo:@{NSLocalizedDescriptionKey:s}];return NO;}
static BOOL rangeFits(NSUInteger offset,NSUInteger extent,NSUInteger length){return offset<=length&&extent<=length-offset;}

@interface KPBinary64Input ()
@property(nonatomic,strong,readwrite) id<MTLBuffer> buffer;
@property(nonatomic,readwrite) NSUInteger offset,stride;
@end
@implementation KPBinary64Input
+ (instancetype)inputWithBuffer:(id<MTLBuffer>)b offset:(NSUInteger)o stride:(NSUInteger)s{
 KPBinary64Input*r=[self new];r.buffer=b;r.offset=o;r.stride=s;return r;
}
@end

@interface KPBinary64Library ()
@property(nonatomic,strong) id<MTLDevice> device;
@property(nonatomic,strong) NSDictionary<NSString*,id<MTLComputePipelineState>> *pipelines;
@property(nonatomic,strong,readwrite) NSDictionary *qualification;
@end
@implementation KPBinary64Library
+ (instancetype)libraryWithDevice:(id<MTLDevice>)d carrierData:(NSData*)carrier
 programs:(NSDictionary<NSString*,NSData*>*)programs error:(NSError**)error{
 if(error)*error=nil;
 if(!KPKepler880MIdentity(d)){fail(error,@"Unqualified FP64 device");return nil;}
 NSData*c=[carrier copy];NSMutableDictionary*snapshots=[NSMutableDictionary dictionary];
 if(![digest(c)isEqual:@(KPFP64CarrierSHA)]||programs.count!=sizeof(KPFP64Pins)/sizeof(KPFP64Pins[0])){fail(error,@"Carrier/program count differs from build pins");return nil;}
 for(const KPFP64Pin&p:KPFP64Pins){
  NSString*k=@(p.name);id v=programs[k];if(![v isKindOfClass:NSData.class]){fail(error,@"Missing FP64 program bytes");return nil;}
  NSData*b=[v copy];if(b.length!=p.bytes||![digest(b)isEqual:@(p.sha)]){fail(error,@"FP64 program hash/size differs");return nil;}snapshots[k]=b;
 }
 Class cls=objc_getClass("NVMTLFunctionVariant");Method method=class_getInstanceMethod(cls,sel_registerName("initWithCompilerOutput:size:device:"));
 IMP original=method?method_getImplementation(method):nil;if(!original){fail(error,@"Missing native constructor");return nil;}
 NSMutableDictionary*psos=[NSMutableDictionary dictionary];NSMutableArray*proofs=[NSMutableArray array];
 for(const KPFP64Pin&p:KPFP64Pins){
  NSDictionary*proof=nil;KeplerImportConfig config={p.gprs,576,576};
  id<MTLComputePipelineState>pipeline=KPInternalCreateApprovedSM30Pipeline(d,c,@"add_buffers",snapshots[@(p.name)],config,error,&proof);
  BOOL restored=method_getImplementation(method)==original;
  if(!pipeline||!restored||![proof[@"contract_verified"]boolValue]){if(!restored)fail(error,@"FP64 constructor was not restored");return nil;}
  psos[@(p.name)]=pipeline;[proofs addObject:@{@"program":@(p.name),@"code_SHA256":@(p.sha),@"local":@(p.local),@"gprs":@(p.gprs),@"code_bytes":@(p.bytes),@"constructor_restored":@YES,@"import":proof}];
 }
 KPBinary64Library*r=[self new];r.device=d;r.pipelines=[psos copy];
 NSMutableSet*operations=[NSMutableSet set];for(const KPFP64Pin&p:KPFP64Pins)[operations addObject:[@(p.name)componentsSeparatedByString:@"-l"][0]];
 NSMutableDictionary*contracts=[NSMutableDictionary dictionary];BOOL hasReverse=NO;
 for(NSString*name in operations){
  BOOL reverse=[name hasPrefix:@"to_"];hasReverse|=reverse;
  NSString*format=[name hasPrefix:@"to_f32_"]?@"binary32_low32_zero_high":[name hasPrefix:@"to_i64_"]?@"int64_twos_complement":[name hasPrefix:@"to_u64_"]?@"uint64":@"binary64";
  contracts[name]=@{@"output_format":format,@"rounding":reverse?[name substringFromIndex:name.length-2]:@"rn",@"integer_out_of_range":(reverse&&![name hasPrefix:@"to_f32_"])?@"saturate; NaN→0":@"not_applicable"};
 }
 r.qualification=@{@"programs":proofs,@"available_operations":[operations.allObjects sortedArrayUsingSelector:@selector(compare:)],@"output_contracts":contracts,@"carrier_SHA256":@(KPFP64CarrierSHA),@"inputs_copied":@YES,@"constructor_restored":@YES,@"registration_is_GPU_qualification":@NO,@"rounding":hasReverse?@"per_operation":@"nearest_even",@"arithmetic_rounding":@"nearest_even",@"output_stride":@16,@"input_strides":@[@8,@16],@"binary32_input":@"low32bits_of_8byte_slot",@"system_modified":@NO};return r;
}
- (BOOL)encodeOperation:(KPBinary64Operation)op commandBuffer:(id<MTLCommandBuffer>)cb
 inputs:(NSArray<KPBinary64Input*>*)inputs output:(id<MTLBuffer>)output outputOffset:(NSUInteger)off
 count:(NSUInteger)n threadsPerGroup:(NSUInteger)local stamp:(uint32_t)stamp error:(NSError**)error
 evidence:(NSDictionary**)evidence{
 if(error)*error=nil;if(evidence)*evidence=nil;
 if(op>KPBinary64ToUnsigned64TowardNegativeInfinity||![@[@32,@128,@1024]containsObject:@(local)]||n>1048576)return fail(error,@"Unsupported operation/local/count");
 NSUInteger required=(op==KPBinary64SquareRoot||op>=KPBinary64FromSigned64)?1:op==KPBinary64FMA?3:2;
 if(inputs.count!=required||!cb||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences||cb.commandQueue.device.registryID!=self.device.registryID)return fail(error,@"Input count or command-buffer contract differs");
 if(!output||output.device.registryID!=self.device.registryID||(output.storageMode!=MTLStorageModeShared&&output.storageMode!=MTLStorageModePrivate)||output.hazardTrackingMode==MTLHazardTrackingModeUntracked||off%8||!rangeFits(off,n*16,output.length)||!output.gpuAddress||output.gpuAddress%8)return fail(error,@"Output device/storage/alignment/range differs");
 uint32_t mask=0;NSMutableArray*bindings=[NSMutableArray array];
 for(NSUInteger i=0;i<inputs.count;i++){
  KPBinary64Input*v=inputs[i];if(![v isKindOfClass:KPBinary64Input.class])return fail(error,@"Input view type differs");
  id<MTLBuffer>b=v.buffer;NSUInteger extent=n?(n-1)*v.stride+8:0;
  if(!b||(v.stride!=8&&v.stride!=16)||v.offset%8||b.device.registryID!=self.device.registryID||(b.storageMode!=MTLStorageModeShared&&b.storageMode!=MTLStorageModePrivate)||b.hazardTrackingMode==MTLHazardTrackingModeUntracked||!rangeFits(v.offset,extent,b.length)||!b.gpuAddress||b.gpuAddress%8)return fail(error,@"Input device/storage/stride/alignment/range differs");
  uint64_t src=b.gpuAddress,dst=output.gpuAddress;
  if(src>UINT64_MAX-b.length||dst>UINT64_MAX-output.length)return fail(error,@"Buffer address range overflow");
  if(n&&dst+off<src+v.offset+extent&&src+v.offset<dst+off+n*16)return fail(error,@"FP64 output overlaps an input");
  mask|=(v.stride==16?1u:0u)<<i;[bindings addObject:@{@"offset":@(v.offset),@"stride":@(v.stride),@"extent":@(extent)}];
 }
 if(!n){if(evidence)*evidence=@{@"count":@0,@"encoded_dispatches":@0,@"inputs":bindings};return YES;}
 struct Params {uint64_t addresses[4];uint32_t grid[3],block[3];};static_assert(sizeof(Params)==56,"Qualified ABI");static_assert(sizeof(KPBinary64Record)==16,"Public result ABI");
 Params p={};for(unsigned i=0;i<3;i++){KPBinary64Input*v=inputs[i<inputs.count?i:0];p.addresses[i==2?3:i]=v.buffer.gpuAddress+v.offset;}
 p.addresses[2]=output.gpuAddress+off;p.grid[0]=(uint32_t)n;p.grid[1]=stamp;p.grid[2]=mask;p.block[0]=(uint32_t)local;p.block[1]=p.block[2]=1;
 id<MTLBuffer>params=[self.device newBufferWithBytes:&p length:sizeof(p) options:MTLResourceStorageModeShared];
 NSArray*names=@[@"add",@"mul",@"fma",@"div",@"sqrt",@"from_i64",@"from_u64",@"from_f32",@"to_f32_rn",@"to_f32_rz",@"to_f32_rp",@"to_f32_rm",@"to_i64_rn",@"to_i64_rz",@"to_i64_rp",@"to_i64_rm",@"to_u64_rn",@"to_u64_rz",@"to_u64_rp",@"to_u64_rm"];NSString*key=[NSString stringWithFormat:@"%@-l%lu",names[op],(unsigned long)local];
 id<MTLComputePipelineState>pipeline=self.pipelines[key];if(!pipeline||!params)return fail(error,@"Unavailable pipeline/parameter buffer");
 id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(!e)return fail(error,@"Cannot create FP64 encoder");
 [e setComputePipelineState:pipeline];[e setBuffer:params offset:0 atIndex:0];[e setBuffer:output offset:off atIndex:1];
 for(KPBinary64Input*v in inputs)[e useResource:v.buffer usage:MTLResourceUsageRead];
 [e dispatchThreadgroups:MTLSizeMake((n+local-1)/local,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];
 if(evidence)*evidence=@{@"program":key,@"count":@(n),@"local":@(local),@"stamp":@(stamp),@"inputs":bindings,@"output_offset":@(off),@"output_stride":@16,@"stride_mask":@(mask),@"encoded_dispatches":@1,@"CPU_arithmetic":@NO,@"CPU_readback":@NO};return YES;
}
@end
