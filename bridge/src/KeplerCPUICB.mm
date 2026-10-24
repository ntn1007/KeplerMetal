#import "KeplerRenderCommandRecords.h"
#import "KeplerRenderStateRecords.h"
#import "KeplerGPUIdentity.h"
#import "KeplerDriverProfile.h"
#import "KeplerCPUICB.h"
#import "KeplerNativeCommands.h"
#include "KeplerCommandIR.h"
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
#include <cstring>
#include <mutex>
#include <map>
#include <cmath>
#include <atomic>

@class KPComputeICB,KPComputeICBCommand,KPRenderICB,KPRenderICBCommand,KPCommandIRArgumentContext,KPReusableIRContext;
@protocol KPOptionalNativeCASFactory <NSObject>
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device
      function:(id<MTLFunction>)function libraryData:(NSData*)library
      expectedSHA256:(NSString*)librarySHA certificateData:(NSData*)certificate
      expectedCertificateSHA256:(NSString*)certificateSHA options:(MTLPipelineOption)options
      reflection:(MTLComputePipelineReflection**)reflection error:(NSError**)error
      evidence:(NSDictionary**)evidence NS_RETURNS_RETAINED;
@end
@protocol KPOptionalRenderRecord <NSObject>
- (NSDictionary*)evidence;
@end
// Runtime optional module: historical compute-only clients keep their existing
// link dependencies. Its implementation is loaded only by the render install.
@protocol KPCPURenderTransport <NSObject>
- (instancetype)initWithQueue:(id<MTLCommandQueue>)queue libraryData:(NSData*)data error:(NSError**)error;
- (id<MTLRenderPipelineState>)pipeline;
- (BOOL)registerVertexLibraryData:(NSData*)data expectedSHA256:(NSString*)expected manifestData:(NSData*)manifest expectedManifestSHA256:(NSString*)manifestSHA error:(NSError**)error;
- (id<MTLRenderPipelineState>)pipelineForName:(NSString*)name;
- (NSDictionary*)profileForPipeline:(id<MTLRenderPipelineState>)pipeline;
- (BOOL)acceptsRenderTarget:(id<MTLTexture>)target;
- (NSUInteger)maxVertexBindings;
- (NSUInteger)maxFragmentBindings;
- (BOOL)encodeFragmentArgumentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset pipelineName:(NSString*)name bindingIndex:(NSUInteger)index resources:(NSDictionary*)resources error:(NSError**)error;
- (id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString*)name bindingIndex:(NSUInteger)index sources:(NSArray*)sources selectedBank:(NSUInteger)bank commandBuffer:(id<MTLCommandBuffer>)cb counter:(id<MTLBuffer>*)counter error:(NSError**)error;
- (BOOL)registerArgumentTableSelectorLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error;
- (id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString*)name bindingIndex:(NSUInteger)index sources:(NSArray*)sources selectionBuffer:(id<MTLBuffer>)selection selectionOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb counter:(id<MTLBuffer>*)counter error:(NSError**)error;
- (BOOL)validateFragmentBindings:(NSDictionary*)bindings pipeline:(id<MTLRenderPipelineState>)pipeline error:(NSError**)error;
- (id)prepareFragmentDrawPipeline:(id<MTLRenderPipelineState>)pipeline vertexBindings:(NSDictionary*)vertexBindings fragmentBindings:(NSDictionary*)fragmentBindings vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count instances:(NSUInteger)instances baseInstance:(NSUInteger)base error:(NSError**)error;

- (BOOL)validateVertexBindings:(NSDictionary*)bindings pipeline:(id<MTLRenderPipelineState>)pipeline vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count instances:(NSUInteger)instances baseInstance:(NSUInteger)base error:(NSError**)error;
- (BOOL)validateIndexedVertexBindings:(NSDictionary*)bindings pipeline:(id<MTLRenderPipelineState>)pipeline indexCount:(NSUInteger)count indexBuffer:(id<MTLBuffer>)indices indexOffset:(NSUInteger)offset kind:(NSUInteger)kind instances:(NSUInteger)instances baseVertex:(NSInteger)vertexBase baseInstance:(NSUInteger)base error:(NSError**)error;
- (id)prepareIndexedVertexPipeline:(id<MTLRenderPipelineState>)pipeline bindings:(NSDictionary*)bindings indexCount:(NSUInteger)count indexBuffer:(id<MTLBuffer>)indices indexOffset:(NSUInteger)offset kind:(NSUInteger)kind instances:(NSUInteger)instances baseVertex:(NSInteger)vertexBase baseInstance:(NSUInteger)base error:(NSError**)error;

- (id)prepareVertexDrawPipeline:(id<MTLRenderPipelineState>)pipeline bindings:(NSDictionary*)bindings vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count instances:(NSUInteger)instances baseInstance:(NSUInteger)base error:(NSError**)error;
- (id)prepareInheritedDrawKind:(NSUInteger)kind indexBuffer:(id<MTLBuffer>)indices offset:(NSUInteger)offset instances:(NSUInteger)instances error:(NSError**)error;
- (BOOL)encodeInheritedRecords:(NSArray*)records encoder:(id<MTLRenderCommandEncoder>)encoder target:(id<MTLTexture>)target evidence:(NSDictionary**)evidence error:(NSError**)error;
- (BOOL)encodeGPUIndirectRecords:(NSArray*)records arguments:(id<MTLBuffer>)arguments encoder:(id<MTLRenderCommandEncoder>)encoder target:(id<MTLTexture>)target evidence:(NSDictionary**)evidence error:(NSError**)error;
- (id)prepareIndexedFragmentPipeline:(id<MTLRenderPipelineState>)pipeline vertexBindings:(NSDictionary*)vertexBindings fragmentBindings:(NSDictionary*)fragmentBindings indexCount:(NSUInteger)count indexBuffer:(id<MTLBuffer>)indices indexOffset:(NSUInteger)offset kind:(NSUInteger)kind instances:(NSUInteger)instances baseVertex:(NSInteger)vertexBase baseInstance:(NSUInteger)base error:(NSError**)error;
@end
// The scope owns the device, so an associated strong scope would form a cycle.
// Ended encoders must also be free to release their command buffers/resources.
@interface KPScopeLink : NSObject
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic,strong) id<MTLTexture> renderTarget;
@property(nonatomic,strong) id<MTLRenderPipelineState> callerRenderPipeline;
@property(nonatomic,strong) id<MTLComputePipelineState> callerComputePipeline;
@property(nonatomic) Class originalComputeClass;
@property(nonatomic) BOOL computeEncodingEnded;
@property(nonatomic) BOOL encodingRenderICB;
@property(nonatomic,strong) NSMutableDictionary *callerVertexBindings;
@property(nonatomic,strong) NSMutableDictionary *callerFragmentBindings;
@property(nonatomic,strong) MTLRenderPassDescriptor *renderPass;
@end
@implementation KPScopeLink
@end
@interface KPAdaptedEncoder : NSObject
@property(nonatomic,weak) id<MTLCommandEncoder> encoder;
@property(nonatomic) Class originalClass;
@end
@implementation KPAdaptedEncoder
@end
namespace {
char contextKey;
std::mutex installMutex;
// Never reuse an identity in this process, including after a scope is restored.
// Saturate at the 32-bit namespace boundary rather than wrapping.
std::atomic<uint64_t>stablePipelineIdentityCounter{1};
uint64_t allocateStablePipelineIdentity(){uint64_t n=stablePipelineIdentityCounter.load();while(n<=UINT32_MAX){if(stablePipelineIdentityCounter.compare_exchange_weak(n,n+1))return(uint64_t(KP_COMMAND_STABLE_PIPELINE_MAGIC)<<32)|n;}return 0;}
std::atomic<uint32_t>contextGenerationCounter{1};
uint32_t allocateContextGeneration(){uint32_t n=contextGenerationCounter.load();while(n<=0xffffffu){if(contextGenerationCounter.compare_exchange_weak(n,n+1))return n;}return 0;}
std::map<uintptr_t,Class>deviceClasses,encoderClasses,renderEncoderClasses,blitEncoderClasses;
KPCPUICBScope *scopeFor(id object){return ((KPScopeLink*)objc_getAssociatedObject(object,&contextKey)).scope;}
void linkScope(id object,KPCPUICBScope *scope){KPScopeLink*link=[KPScopeLink new];link.scope=scope;objc_setAssociatedObject(object,&contextKey,link,OBJC_ASSOCIATION_RETAIN_NONATOMIC);}
NSString *hash(NSData*d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
NSUInteger volume(MTLSize d,NSUInteger cap){NSUInteger n=1;for(NSUInteger v:{d.width,d.height,d.depth}){if(!v||n>cap/v)return 0;n*=v;}return n;}
BOOL wholeNumber(id value,NSUInteger minimum,NSUInteger maximum){return [value isKindOfClass:[NSNumber class]]&&[value doubleValue]>=minimum&&[value doubleValue]<=maximum&&[value doubleValue]==[value unsignedLongLongValue];}
BOOL digestString(id value){if(![value isKindOfClass:[NSString class]]||[value length]!=64)return NO;return [value rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"]invertedSet]].location==NSNotFound;}
id<MTLLibrary>libraryFromSnapshot(id<MTLDevice>device,NSData*snapshot,NSError**error){if(!snapshot.length)return nil;dispatch_data_t payload=dispatch_data_create(snapshot.bytes,snapshot.length,dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT,0),^{(void)snapshot.length;});return [device newLibraryWithData:payload error:error];}
BOOL fail(NSError**error,NSString*s){if(error)*error=[NSError errorWithDomain:@"KeplerCPUICB" code:1 userInfo:@{NSLocalizedDescriptionKey:s}];return NO;}
// Caller holds installMutex. Cache only our subclasses, never replace methods
// on shared native classes; weak instance links select the active scope.
Class scopedClass(std::map<uintptr_t,Class>&cache,Class original,NSString*prefix,SEL selector,IMP implementation,NSError**error){uintptr_t key=(uintptr_t)(__bridge const void*)original;auto found=cache.find(key);if(found!=cache.end())return found->second;Method method=class_getInstanceMethod(original,selector);if(!method){fail(error,@"Native selector ABI missing");return nil;}NSString*name=[prefix stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];Class dynamic=objc_allocateClassPair(original,name.UTF8String,0);if(!dynamic||!class_addMethod(dynamic,selector,implementation,method_getTypeEncoding(method))){fail(error,@"Scoped subclass creation failed");return nil;}objc_registerClassPair(dynamic);if(class_getInstanceSize(dynamic)!=class_getInstanceSize(original)){fail(error,@"Scoped instance layout changed");return nil;}cache[key]=dynamic;return dynamic;}
void reject(NSString*s){@throw [NSException exceptionWithName:@"KeplerCPUICBUnsupported" reason:s userInfo:nil];}
void bounds(NSRange range,NSUInteger count){if(range.location>count||range.length>count-range.location)reject(@"ICB range outside allocated command slots");}
NSData*readMemory(uintptr_t p,size_t n){if(!p||!n||n>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:n];mach_vm_size_t actual=0;return mach_vm_read_overwrite(mach_task_self(),p,n,(mach_vm_address_t)d.mutableBytes,&actual)==KERN_SUCCESS&&actual==n?d:nil;}
uint64_t word(NSData*d,size_t o){uint64_t v=0;if(o+8<=d.length)memcpy(&v,(const char*)d.bytes+o,8);return v;}
struct Cursor{uintptr_t push,current,end;};
Cursor cursor(id<MTLComputeCommandEncoder>e){Cursor c={};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;uintptr_t impl=0;memcpy(&impl,(const char*)(__bridge const void*)e+120,8);c.push=word(readMemory(impl,64),32);NSData*d=readMemory(c.push,144);c.current=word(d,0);c.end=word(d,136);return c;}
id<MTLBuffer>queueBuffer(id<MTLCommandQueue>q,unsigned offset){Ivar v=class_getInstanceVariable(object_getClass(q),"_queue");if(!v||ivar_getOffset(v)!=680)return nil;uintptr_t cpp=0;memcpy(&cpp,(const char*)(__bridge const void*)q+680,8);uintptr_t p=word(readMemory(cpp,64),offset);id x=(__bridge id)(void*)p;return [x isKindOfClass:objc_getClass("NVMTLBuffer")]?x:nil;}
BOOL complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return c.status==MTLCommandBufferStatusCompleted;}
BOOL residentNativeProfile(NSDictionary*p){
 BOOL legacy=[p[@"library_SHA256"]isEqual:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd"]&&[@[@"profile_integer",@"profile_fma",@"profile_shared"]containsObject:p[@"function"]?:@""];
 BOOL registered=[p[@"native_registration_v1"]boolValue]&&p[@"pipeline_owner"]&&p[@"library_owner"]&&[p[@"registration_id"]length]&&digestString(p[@"library_SHA256"])&&digestString(p[@"manifest_SHA256"]);
 return legacy||registered;
}
BOOL sameResidentRegistration(NSDictionary*a,NSDictionary*b){
 if(!residentNativeProfile(a)||!residentNativeProfile(b)||![a[@"library_SHA256"]isEqual:b[@"library_SHA256"]])return NO;
 if([a[@"native_registration_v1"]boolValue]||[b[@"native_registration_v1"]boolValue])return [a[@"native_registration_v1"]boolValue]&&[b[@"native_registration_v1"]boolValue]&&[a[@"registration_id"]isEqual:b[@"registration_id"]]&&[a[@"manifest_SHA256"]isEqual:b[@"manifest_SHA256"]]&&a[@"library_owner"]==b[@"library_owner"];
 return YES;
}
// A committed predecessor has already acquired its queue position. Requiring
// the consumer to remain NotEnqueued prevents it from having an earlier one.
// Source buffers in another queue, merely Enqueued or Error are not accepted.
NSDictionary*residentPredecessorOrder(id<MTLCommandBuffer>producer,id<MTLCommandBuffer>consumer){
 if(!producer||!consumer||producer.commandQueue!=consumer.commandQueue||!producer.retainedReferences||!consumer.retainedReferences||consumer.status!=MTLCommandBufferStatusNotEnqueued)return nil;
 MTLCommandBufferStatus status=producer.status;BOOL same=producer==consumer;
 if(!same&&status!=MTLCommandBufferStatusCommitted&&status!=MTLCommandBufferStatusScheduled&&status!=MTLCommandBufferStatusCompleted)return nil;
 return @{@"kind":same?@"same_recording_CB":status==MTLCommandBufferStatusCompleted?@"completed_predecessor":@"committed_same_queue_predecessor",@"producer_status":@(status),@"consumer_status":@(consumer.status),@"same_queue":@YES,@"consumer_not_enqueued":@YES,@"CPU_wait_performed":@NO};
}
}

@interface KPCPUICBScope ()
@property(nonatomic,strong) id<MTLDevice> device;
@property(nonatomic,strong) id<MTLCommandQueue> queue;
@property(nonatomic,strong) id<MTLComputePipelineState> pipeline;
@property(nonatomic,strong) NSMutableDictionary *profiles;
@property(nonatomic,strong) NSMutableDictionary *namedPipelines;
@property(nonatomic,strong) NSMutableArray *eventRows;
@property(nonatomic,strong) NSMutableArray *adapted;
@property(nonatomic) Class originalDeviceClass,originalQueueClass;
@property(nonatomic,strong) NSMutableArray *automaticBuffers;
@property(nonatomic,strong) NSObject *factoryLock;
@property(nonatomic,strong) NSMutableArray *adaptedFunctions,*functionLibraries,*adaptedIRLibraries;
@property(nonatomic,strong) NSMutableDictionary *registeredIRLibraries;
@property(nonatomic) BOOL renderRecordArgumentsEnabled;
@property(nonatomic,strong) NSHashTable *renderArgumentContexts;
@property(nonatomic,strong) NSMutableDictionary *stablePipelineIdentities;
@property(nonatomic) BOOL restored;
@property(nonatomic) NSUInteger releasedEncoderCount;
@property(nonatomic) NSUInteger maxKernelBindings;
@property(nonatomic,strong) id<KPCPURenderTransport> renderEngine;
@property(nonatomic,strong) id<MTLLibrary> indirectRenderRangeLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> indirectRenderRangePipeline;
@property(nonatomic,strong) id<MTLLibrary> indirectRenderCommandLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> indirectRenderCommandPipeline;
@property(nonatomic,strong) id<MTLLibrary> indirectRenderStateLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> indirectRenderStatePipeline;
@property(nonatomic,strong) id<MTLLibrary> GPUSelectionLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> GPUChoiceProducer;
@property(nonatomic,strong) id<MTLComputePipelineState> GPUCommandSelector;
@property(nonatomic,strong) id<MTLLibrary> GPUGridLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> GPUGridSelector;
@property(nonatomic,strong) id<MTLLibrary> GPUBindingLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> GPUBindingSelector;
@property(nonatomic,strong) id<MTLLibrary> GPUCommandIRLibrary;
@property(nonatomic,strong) id<MTLComputePipelineState> GPUCommandIRSelector;
@property(nonatomic,strong) id<MTLLibrary> GPUCommandIRv2Library;
@property(nonatomic,strong) id<MTLComputePipelineState> GPUCommandIRv2Selector;
- (NSDictionary*)profileForPipeline:(id<MTLComputePipelineState>)pipeline;
- (BOOL)validateRenderCommandArgumentContext:(KPRenderCommandArgumentContext*)context error:(NSError**)error;
- (KPRecordedNativeCompute*)materialize:(KPComputeICBCommand*)command;
- (KPGPUCommandSelection*)newGPUCommandBindingPlanFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources input:(id<MTLBuffer>)input inputOffset:(NSUInteger)offset nonce:(uint32_t)nonce IR:(BOOL)IR error:(NSError**)error;
- (KPGPUCommandSelection*)newGPUCommandIRv2FromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset stablePipelineIdentities:(BOOL)stable error:(NSError**)error;
- (KPGPUCommandSelection*)newGPUCommandIRv2FromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources records:(id<MTLBuffer>)records recordOffset:(NSUInteger)offset stablePipelineIdentities:(BOOL)stable reusable:(KPReusableIRContext*)reusable generation:(uint32_t)generation error:(NSError**)error;
- (id<MTLFunction>)newNativeSourceCommandIRFunctionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected functionName:(NSString*)name rootBufferIndex:(NSUInteger)index generationTagged:(BOOL)tagged error:(NSError**)error;
@end

#include "KeplerReusableIRContext.inc"

@interface KPComputeICBCommand : NSObject<MTLIndirectComputeCommand>
@property(nonatomic,weak) KPComputeICB *owner;
@property(nonatomic,strong) id<MTLComputePipelineState> pipeline;
@property(nonatomic,strong) NSMutableDictionary *bindings;
@property(nonatomic,strong) NSMutableDictionary *threadgroupLengths;
@property(nonatomic,strong) NSArray<id<MTLBuffer>> *GPUResourceOwners;
@property(nonatomic) MTLSize groups;
@property(nonatomic) MTLSize local;
@property(nonatomic) BOOL hasDispatch;
@property(nonatomic) BOOL barrier;
@property(nonatomic,strong) KPRecordedNativeCompute *record;
@property(nonatomic,strong) NSArray<KPRecordedNativeCompute*> *residentOwners;
@property(nonatomic,strong) id<MTLCommandBuffer> residentCopyBuffer;
@property(nonatomic) BOOL GPUGenerated;
@property(nonatomic,weak) KPReusableIRContext *reusableContext;
@property(nonatomic) uint32_t reusableGeneration;
- (void)checkReusableMutation;
- (void)copyStateFrom:(KPComputeICBCommand*)source;
@end

@interface KPComputeICB : NSObject<MTLIndirectCommandBuffer>
@property(nonatomic,strong) KPCPUICBScope *scope;
@property(nonatomic,strong) KPCommandIRArgumentContext *commandIRArgumentContext;
@property(nonatomic,strong) KPReusableIRContext *reusableContext;
@property(nonatomic,strong) id<MTLBuffer> metadata;
@property(nonatomic,strong) NSMutableArray *commands;
@property(atomic,copy) NSString *label;
- (void)executeRange:(NSRange)range encoder:(id<MTLComputeCommandEncoder>)encoder;
@end

@class KPIndirectRenderPlan;
@interface KPRenderICB : KPComputeICB
@property(nonatomic,strong) KPRenderCommandArgumentContext *renderArgumentContext;
@property(nonatomic) MTLIndirectCommandType allowedTypes;
@property(nonatomic,strong) KPIndirectRenderPlan *indirectRenderPlan;
@property(nonatomic) NSUInteger maxVertexBuffers,maxFragmentBuffers;
- (void)executeRenderRange:(NSRange)range encoder:(id<MTLRenderCommandEncoder>)encoder target:(id<MTLTexture>)target;
@end
@interface KPRenderICBCommand : NSObject<MTLIndirectRenderCommand>
@property(nonatomic,weak) KPRenderICB *owner;
@property(nonatomic,strong) id<MTLRenderPipelineState> pipeline;
@property(nonatomic,strong) id<MTLBuffer> indices;
@property(nonatomic) NSUInteger kind,offset,instances;
@property(nonatomic) NSUInteger vertexStart,vertexCount,baseInstance;
@property(nonatomic) NSInteger baseVertex;
@property(nonatomic,strong) NSMutableDictionary *vertexBindings,*fragmentBindings;
@property(nonatomic) BOOL hasDraw;
@property(nonatomic,strong) id record;
- (void)copyStateFrom:(KPRenderICBCommand*)source;
@end

@interface KPRenderCatalogueSource : NSObject
@property(nonatomic,weak) KPRenderICB *buffer;
@property(nonatomic,copy) NSArray *snapshots;
@end
@implementation KPRenderCatalogueSource
@end
@interface KPRenderStateCatalogue ()
@property(nonatomic,weak) KPCPUICBScope *scope;
@property(nonatomic,readwrite) NSUInteger logicalCommandCount;
@property(nonatomic,readwrite,copy) NSArray<NSNumber*> *stateIdentifiers;
@property(nonatomic,copy) NSArray<KPRenderCatalogueSource*> *sources;
@property(nonatomic,copy) NSArray *records;
@property(nonatomic,copy) NSData *templates;
- (instancetype)initOwned;
@end
@implementation KPRenderStateCatalogue
- (instancetype)initOwned{return [super init];}
@end

@interface KPIndirectRenderPlan : NSObject
@property(nonatomic,weak) id<MTLCommandBuffer> commandBuffer;
@property(nonatomic,strong) id<MTLBuffer> range,arguments,witness,templates,config,commandRecords;
@property(nonatomic,strong) NSArray *records;
@property(nonatomic,strong) NSArray *owners;
@property(nonatomic,strong) KPRenderStateCatalogue *stateCatalogue;
@property(nonatomic) NSUInteger rangeOffset;
@property(atomic) BOOL consumed,completed,failed;
@end
@implementation KPIndirectRenderPlan
@end

@implementation KPComputeICBCommand
- (instancetype)init{if((self=[super init])){_bindings=[NSMutableDictionary new];_threadgroupLengths=[NSMutableDictionary new];}return self;}
- (void)checkReusableMutation{if(_reusableContext){NSError*error=nil;if(![_reusableContext idle:&error])reject(error.localizedDescription);if(_reusableGeneration==_reusableContext.generation&&![_reusableContext retire:&error])reject(error.localizedDescription);}}
- (void)invalidate{_record=nil;_residentOwners=nil;_residentCopyBuffer=nil;_GPUResourceOwners=nil;_GPUGenerated=NO;}
- (void)setComputePipelineState:(id<MTLComputePipelineState>)pipeline {[self checkReusableMutation];if(_GPUGenerated)reject(@"GPU-selected command requires reset before CPU re-encoding");if(!_owner||![_owner.scope profileForPipeline:pipeline])reject(@"Pipeline is not owned by this registered scope");_pipeline=pipeline;[self invalidate];}
- (void)setKernelBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset atIndex:(NSUInteger)index {[self checkReusableMutation];if(_GPUGenerated)reject(@"GPU-selected command requires reset before CPU re-encoding");NSDictionary*p=[_owner.scope profileForPipeline:_pipeline],*spec=p[@"binding_specs"][@(index)];BOOL extended=[p[@"binding_layout_v2"]boolValue];if(!_owner||(!extended&&index>=3)||(extended&&!spec)||buffer.device!=_owner.scope.device||offset>buffer.length||(extended&&offset%[spec[@"alignment"]unsignedIntegerValue]))reject(@"Unqualified kernel buffer/index/offset alignment");_bindings[@(index)]=@{@"buffer":buffer,@"offset":@(offset)};[self invalidate];}
- (void)setKernelBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset attributeStride:(NSUInteger)stride atIndex:(NSUInteger)index{reject(@"Dynamic attribute stride is not implemented");}
- (void)concurrentDispatchThreadgroups:(MTLSize)groups threadsPerThreadgroup:(MTLSize)local {[self checkReusableMutation];if(_GPUGenerated)reject(@"GPU-selected command requires reset before CPU re-encoding");NSDictionary*p=[_owner.scope profileForPipeline:_pipeline];BOOL multidimensional=[p[@"multidimensional_grid"]boolValue];NSUInteger limit=[p[@"max_local"]unsignedIntegerValue];if(!limit)limit=[p[@"static_threadgroup_bytes"]unsignedIntegerValue]?128:1024;NSUInteger maxInvocations=[p[@"max_invocations"]unsignedIntegerValue]?:640;NSUInteger localCount=volume(local,limit),groupCount=volume(groups,maxInvocations);if(!localCount||!groupCount||local.width>1024||local.height>1024||local.depth>64||groups.width>0x7fffffff||groups.height>65535||groups.depth>65535||groupCount>maxInvocations/localCount||(!multidimensional&&(groups.height!=1||groups.depth!=1||local.height!=1||local.depth!=1)))reject(@"Grid exceeds registered dimension/thread bounds");_groups=groups;_local=local;_hasDispatch=YES;[self invalidate];}
- (void)concurrentDispatchThreads:(MTLSize)grid threadsPerThreadgroup:(MTLSize)local{reject(@"Nonuniform thread grids are not implemented");}
- (void)setBarrier{[self checkReusableMutation];_barrier=YES;}
- (void)clearBarrier{[self checkReusableMutation];_barrier=NO;}
- (void)setImageblockWidth:(NSUInteger)width height:(NSUInteger)height{reject(@"Imageblock state is not implemented");}
- (void)setThreadgroupMemoryLength:(NSUInteger)length atIndex:(NSUInteger)index{[self checkReusableMutation];if(_GPUGenerated)reject(@"GPU-selected command requires reset before CPU re-encoding");NSDictionary*p=[_owner.scope profileForPipeline:_pipeline],*memory=p[@"dynamic_threadgroup"];if(![p[@"native_registration_v1"]boolValue]||!memory||index!=[memory[@"index"]unsignedIntegerValue]||length%16||length<[memory[@"min_bytes"]unsignedIntegerValue]||length>[memory[@"max_bytes"]unsignedIntegerValue]||length+[p[@"static_threadgroup_bytes"]unsignedIntegerValue]>49152)reject(@"Threadgroup memory index/length outside registered native ABI");_threadgroupLengths[@(index)]=@(length);[self invalidate];}
- (void)setStageInRegion:(MTLRegion)region{reject(@"Stage-in regions are not implemented");}
- (void)reset{[self checkReusableMutation];_reusableContext=nil;_reusableGeneration=0;_pipeline=nil;[_bindings removeAllObjects];[_threadgroupLengths removeAllObjects];_hasDispatch=NO;_barrier=NO;_groups=MTLSizeMake(0,0,0);_local=MTLSizeMake(0,0,0);[self invalidate];}
- (void)copyStateFrom:(KPComputeICBCommand*)s{[self checkReusableMutation];if(s.reusableContext)reject(@"Copying reusable command state is not qualified");_pipeline=s.pipeline;_bindings=[s.bindings mutableCopy];_threadgroupLengths=[s.threadgroupLengths mutableCopy];_groups=s.groups;_local=s.local;_hasDispatch=s.hasDispatch;_barrier=s.barrier;_record=s.record;_residentOwners=s.residentOwners;_residentCopyBuffer=s.residentCopyBuffer;_GPUResourceOwners=s.GPUResourceOwners;_GPUGenerated=s.GPUGenerated;}
@end

// Validate the current public command state, not just a cached native record.
// Registered layouts use their reflected manifest bounds and active bindings.
static NSString*residentBindingError(KPComputeICBCommand*c,KPCPUICBScope*scope){
 NSDictionary*p=[scope profileForPipeline:c.pipeline];if(!c.hasDispatch||!residentNativeProfile(p))return @"Resident command requires a registered native profile";
 BOOL extended=[p[@"binding_layout_v2"]boolValue];NSUInteger maxLocal=[p[@"max_local"]unsignedIntegerValue]?:([p[@"static_threadgroup_bytes"]unsignedIntegerValue]?128:1024),limit=extended?[p[@"max_invocations"]unsignedIntegerValue]:640;
 NSUInteger local=volume(c.local,maxLocal),groups=volume(c.groups,limit);if(!local||!groups||groups>limit/local)return @"Resident command grid exceeds its registration";NSUInteger count=local*groups;
 if(extended){NSDictionary*specs=p[@"binding_specs"];if(c.bindings.count!=specs.count)return @"Resident schema2 binding count differs";
  for(NSNumber*index in specs){NSDictionary*spec=specs[index],*binding=c.bindings[index];id<MTLBuffer>b=binding[@"buffer"];NSUInteger offset=[binding[@"offset"]unsignedIntegerValue],stride=[spec[@"per_invocation_bytes"]unsignedIntegerValue],alignment=[spec[@"alignment"]unsignedIntegerValue];if(stride&&count>NSUIntegerMax/stride)return @"Resident buffer extent overflows";NSUInteger required=MAX([spec[@"minimum_bytes"]unsignedIntegerValue],count*stride);if(!b||b.device!=scope.device||!alignment||offset>b.length||offset%alignment||required>b.length-offset)return @"Resident schema2 buffer range is insufficient";}
 }else{if(c.bindings.count!=3)return @"Resident schema1 binding count differs";for(NSNumber*index in @[@0,@1,@2])if([c.bindings[index][@"buffer"]device]!=scope.device)return @"Resident buffer device differs";
  if([c.bindings[@0][@"offset"]unsignedIntegerValue]!=64||[c.bindings[@1][@"offset"]unsignedIntegerValue]!=64||[c.bindings[@2][@"offset"]unsignedIntegerValue]||[c.bindings[@0][@"buffer"]length]!=10368||[c.bindings[@1][@"buffer"]length]!=132||[c.bindings[@2][@"buffer"]length]<512)return @"Resident schema1 buffer range differs";
 }
 NSDictionary*memory=p[@"dynamic_threadgroup"];
 if(memory){
  NSNumber*constantIndex=extended?p[@"constant_buffer_index"]:@2;NSDictionary*binding=c.bindings[constantIndex];NSUInteger length=[c.threadgroupLengths[memory[@"index"]]unsignedIntegerValue],wordOffset=[memory[@"parameter_word_offset"]unsignedIntegerValue],base=[binding[@"offset"]unsignedIntegerValue];id<MTLBuffer>parameters=binding[@"buffer"];uint32_t words=0;
  if(c.threadgroupLengths.count!=1||length%16||length<[memory[@"min_bytes"]unsignedIntegerValue]||length>[memory[@"max_bytes"]unsignedIntegerValue]||length+[p[@"static_threadgroup_bytes"]unsignedIntegerValue]>49152||parameters.storageMode==MTLStorageModePrivate||!parameters.contents||base>parameters.length||wordOffset>parameters.length-base||parameters.length-base-wordOffset<4)return @"Resident dynamic shared state is outside its registration";
  memcpy(&words,(const char*)parameters.contents+base+wordOffset,4);if(uint64_t(words)*4!=length)return @"Resident dynamic shared parameter differs from its allocation";
 }else if(c.threadgroupLengths.count)return @"Resident static profile has unexpected dynamic shared bindings";
 return nil;
}

@interface KPGPUCommandSelection ()
@property(nonatomic,strong) KPCPUICBScope *scope;
@property(nonatomic,strong) KPComputeICB *targetICB;
@property(nonatomic,strong) NSArray<KPComputeICBCommand*> *targetCommands;
@property(nonatomic,strong) NSArray<KPRecordedNativeCompute*> *targetRecords;
@property(nonatomic,strong) NSArray<KPRecordedNativeCompute*> *owners;
@property(nonatomic,strong) id<MTLBuffer> input,templates,choices,invocationCounts,producerConfig;
@property(nonatomic,strong) id<MTLBuffer> geometryLimits,generatedGeometry;
@property(nonatomic,strong) id<MTLBuffer> constantTemplates,resourceAddresses;
@property(nonatomic,strong) NSArray<id<MTLBuffer>> *resourceOwners;
@property(nonatomic,strong) NSArray<id<MTLBuffer>> *selectorConfigs;
@property(nonatomic,strong) id<MTLCommandBuffer> producerBuffer,selectionBuffer;
@property(nonatomic,strong) NSMutableArray *eventRows;
@property(nonatomic) NSUInteger inputOffset,candidateCount;
@property(nonatomic) BOOL gridPrefix;
@property(nonatomic) BOOL bindingGeneration;
@property(nonatomic) BOOL commandIRGeneration;
@property(nonatomic) BOOL commandIRStablePipelineIdentities;
@property(nonatomic,strong) NSArray<NSNumber*> *commandIRPipelineIdentities;
@property(nonatomic) NSUInteger commandIRVersion,commandIRBufferCount,commandIRConstantIndex;
@property(nonatomic,strong) id<MTLBuffer> commandIRLimits,commandIRContext;
@property(nonatomic,strong) id<MTLBuffer> commandIRNativeBindings;
@property(nonatomic,strong) NSArray<KPRecordedNativeCompute*> *commandIRBindingRecords;
@property(nonatomic,strong) NSArray<id<MTLBuffer>> *commandIRParameters;
@property(nonatomic,strong) NSArray<NSNumber*> *commandIRParameterAddresses;
@property(nonatomic,strong) KPCommandIRArgumentContext *commandIRArgumentContext;
@property(nonatomic,strong) NSMutableArray<NSMutableDictionary*> *commandIRArgumentRoots;
@property(nonatomic,strong) KPReusableIRContext *reusableContext;
@property(nonatomic) uint32_t reusableGeneration;
@end

@implementation KPGPUCommandSelection
- (NSArray*)events{@synchronized(_eventRows){return [_eventRows copy];}}
#include "KeplerCommandIRPlan.inc"
- (BOOL)validateOwners:(NSError**)error {
 if(_scope.restored)return fail(error,@"GPU selection scope was restored");
 if(_commandIRVersion==2&&_commandIRArgumentContext&&_targetICB.commandIRArgumentContext!=_commandIRArgumentContext)return fail(error,@"Command IR target belongs to a newer plan");
 if(_reusableContext&&(_reusableContext.retired||_reusableContext.poisoned||_reusableContext.generation!=_reusableGeneration||_reusableContext.plan!=self))return fail(error,@"Reusable command IR generation was retired");
 for(KPRecordedNativeCompute*r in _owners)if(![r validateResidentThreadgroupMemory:error])return NO;
 for(NSUInteger i=0;i<_targetCommands.count;i++)if(_targetCommands[i].record!=_targetRecords[i])return fail(error,@"GPU selection destination changed after preparation");
 return YES;
}
- (BOOL)acceptBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
 if(!cb||cb.commandQueue!=_scope.queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return fail(error,@"GPU selection requires retained uncommitted buffer from its queue");
 return [self validateOwners:error];
}
- (BOOL)encodeProducerInCommandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
 if(_commandIRGeneration)return fail(error,@"IR plans require an explicit public-MSL producer");
 if(_producerBuffer||_selectionBuffer)return fail(error,@"GPU choice producer is already encoded or selection started");
 if(![self acceptBuffer:cb error:error])return NO;
 id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(!e)return fail(error,@"Cannot create GPU choice encoder");
 [e setComputePipelineState:_scope.GPUChoiceProducer];[e setBuffer:_input offset:_inputOffset atIndex:0];[e setBuffer:_choices offset:64 atIndex:1];[e setBuffer:_invocationCounts offset:64 atIndex:2];[e setBuffer:_producerConfig offset:0 atIndex:3];
 [e dispatchThreadgroups:MTLSizeMake(_targetRecords.count,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];_producerBuffer=cb;
 NSArray*keep=@[_input,_choices,_invocationCounts,_producerConfig,_scope.GPUChoiceProducer,_scope.GPUSelectionLibrary];[cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)keep.count;}];
 NSDictionary*proof=@{@"operation":@"GPU_command_choice_producer",@"rows":@(_targetRecords.count),@"threads_per_row":@32,@"input_CPU_read":@NO,@"choice_CPU_read":@NO,@"CPU_resolved_choice_supplied":@NO};[_eventRows addObject:proof];[_scope.eventRows addObject:proof];return YES;
}
- (BOOL)encodeSelectionInCommandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
 if(_selectionBuffer)return fail(error,@"GPU command selection is already encoded");if(![self acceptBuffer:cb error:error])return NO;
 NSDictionary*order=_producerBuffer?residentPredecessorOrder(_producerBuffer,cb):nil;if(_producerBuffer&&!order)return fail(error,@"GPU choice producer must precede selection on the same queue");
 NSMutableArray*rows=[NSMutableArray new];
 for(NSUInteger i=0;i<_targetRecords.count;i++){
  id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];if(!e)return fail(error,@"Cannot create GPU command selector encoder; discard buffer");
  [e setComputePipelineState:_commandIRVersion==2?_scope.GPUCommandIRv2Selector:_commandIRGeneration?_scope.GPUCommandIRSelector:_bindingGeneration?_scope.GPUBindingSelector:_gridPrefix?_scope.GPUGridSelector:_scope.GPUCommandSelector];[e setBuffer:_templates offset:0 atIndex:0];[e setBuffer:_commandIRGeneration?_input:_choices offset:_commandIRGeneration?_inputOffset:64 atIndex:1];[e setBuffer:_invocationCounts offset:64+_targetRecords.count*4 atIndex:2];[e setBuffer:_selectorConfigs[i]offset:0 atIndex:3];[e setBuffer:_targetRecords[i].descriptor offset:0 atIndex:4];
  if(_gridPrefix){[e setBuffer:_commandIRGeneration?_commandIRLimits:_geometryLimits offset:0 atIndex:5];[e setBuffer:_generatedGeometry offset:64 atIndex:6];}
  if(_bindingGeneration){[e setBuffer:_resourceAddresses offset:0 atIndex:7];[e setBuffer:_constantTemplates offset:0 atIndex:8];[e setBuffer:_targetRecords[i].constants offset:0 atIndex:9];for(id<MTLBuffer>r in _resourceOwners)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];}
  if(_commandIRVersion==2)[e setBuffer:_commandIRNativeBindings offset:0 atIndex:10];
  [e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(64,1,1)];[e endEncoding];
  KPComputeICBCommand*c=_targetCommands[i];c.residentOwners=_owners;c.residentCopyBuffer=cb;c.GPUGenerated=YES;c.GPUResourceOwners=_resourceOwners;
  [rows addObject:@{@"destination_GPU_address":@(_targetRecords[i].descriptor.gpuAddress),@"destination_original_function":_targetRecords[i].relocationEvidence[@"function"],@"selected_function_CPU_known":_commandIRGeneration?(id)NSNull.null:@NO,@"selected_function_CPU_read":@NO,@"QMD_bytes":@256}];
 }
 _selectionBuffer=cb;NSMutableArray*keep=[@[_templates,_choices,_invocationCounts,_selectorConfigs,_owners,_scope.GPUCommandSelector,_scope.GPUSelectionLibrary]mutableCopy];if(_gridPrefix)[keep addObjectsFromArray:@[_commandIRGeneration?_commandIRLimits:_geometryLimits,_generatedGeometry,_scope.GPUGridSelector,_scope.GPUGridLibrary]];[cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)keep.count;}];
 if(_bindingGeneration)[keep addObjectsFromArray:@[_resourceAddresses,_constantTemplates,_resourceOwners,_scope.GPUBindingSelector,_scope.GPUBindingLibrary]];
 if(_commandIRGeneration)[keep addObjectsFromArray:@[_input,_commandIRLimits,_commandIRContext,_commandIRParameters,_commandIRVersion==2?_scope.GPUCommandIRv2Library:_scope.GPUCommandIRLibrary,_commandIRVersion==2?_scope.GPUCommandIRv2Selector:_scope.GPUCommandIRSelector]];
 if(_commandIRVersion==2)[keep addObjectsFromArray:@[_commandIRNativeBindings,_commandIRBindingRecords]];
 if(_commandIRGeneration){NSDictionary*IRproof=@{@"operation":@"GPU_command_IR_materialization",@"rows":@(_targetRecords.count),@"record_CPU_read":@NO,@"invalid_or_reset_zero_CTA":@YES,@"sealed_native_pipeline_and_resource_catalogue":@YES,@"nonuniform_threads_supported":@NO,@"stage_in_supported":@NO,@"serial_WAIT_FOR_IDLE_after_each_command":@YES};[_eventRows addObject:IRproof];[_scope.eventRows addObject:IRproof];}
 NSDictionary*proof=@{@"operation":@"GPU_command_descriptor_selection",@"candidate_count":@(_candidateCount),@"rows":rows,@"producer_encoded":@(_producerBuffer!=nil),@"producer_order":order?:@{},@"choice_CPU_read":@NO,@"descriptor_CPU_upload":@NO,@"CPU_shadow_is_execution_source":@NO,@"owners_retained":@(_owners.count),@"GPU_choice_clamped":@(!_commandIRGeneration),@"GPU_generated_X_grid":@(_gridPrefix),@"GPU_generated_resource_bindings":@(_bindingGeneration),@"extra_GPU_resource_owners":@(_resourceOwners.count),@"QMD_grid_word_offset":_gridPrefix?@48:[NSNull null],@"QMD_CB1_address_word_offsets":_bindingGeneration?@[@124,@128]:@[],@"CB1_resource_address_offsets":_bindingGeneration?@[@8,@40]:@[],@"local_size_modified":@NO,@"general_GPU_ICB_encoding":@NO};[_eventRows addObject:proof];[_scope.eventRows addObject:proof];return YES;
}
@end

#include "KeplerRenderCommandArguments.inc"
#include "KeplerCommandIRArgumentEncoder.inc"
#include "KeplerCommandIRFunction.inc"
#include "KeplerCommandIRReflection.inc"
#include "KeplerCommandIRProducer.inc"
#include "KeplerNativeThreadLimits.inc"
#include "KeplerCommandIRPipelineContracts.inc"
#include "KeplerAutomaticComputeFactories.inc"
#include "KeplerCommandIRLibrary.inc"

@implementation KPComputeICB
- (id<MTLDevice>)device{return _scope.device;}
- (NSUInteger)size{return _commands.count;}
- (MTLCPUCacheMode)cpuCacheMode{return _metadata.cpuCacheMode;}
- (MTLStorageMode)storageMode{return _metadata.storageMode;}
- (MTLHazardTrackingMode)hazardTrackingMode{return _metadata.hazardTrackingMode;}
- (MTLResourceOptions)resourceOptions{return _metadata.resourceOptions;}
- (NSUInteger)allocatedSize{return _metadata.allocatedSize;}
- (id<MTLHeap>)heap{return nil;}
- (NSUInteger)heapOffset{return 0;}
- (BOOL)isAliasable{return NO;}
- (void)makeAliasable{reject(@"ICB prototype is not heap allocated");}
- (MTLPurgeableState)setPurgeableState:(MTLPurgeableState)state{if(state!=MTLPurgeableStateKeepCurrent&&state!=MTLPurgeableStateNonVolatile)reject(@"Volatile/purgeable command state is not implemented");return MTLPurgeableStateNonVolatile;}
- (kern_return_t)setOwnerWithIdentity:(task_id_token_t)token{return [_metadata setOwnerWithIdentity:token];}
- (MTLResourceID)gpuResourceID{reject(@"GPU argument-buffer ICB identity is not implemented");return MTLResourceID{0};}
- (void)resetWithRange:(NSRange)range{bounds(range,self.size);if(range.length&&_reusableContext){NSError*e=nil;if(![_reusableContext retire:&e])reject(e.localizedDescription);}for(NSUInteger i=range.location;i<NSMaxRange(range);i++)[_commands[i] reset];[_scope.eventRows addObject:@{@"operation":@"CPU_reset",@"location":@(range.location),@"length":@(range.length)}];}
- (id<MTLIndirectComputeCommand>)indirectComputeCommandAtIndex:(NSUInteger)i{bounds(NSMakeRange(i,1),self.size);return _commands[i];}
- (id<MTLIndirectRenderCommand>)indirectRenderCommandAtIndex:(NSUInteger)i{reject(@"Render ICBs are not implemented");return nil;}
- (void)executeRange:(NSRange)range encoder:(id<MTLComputeCommandEncoder>)encoder {
 bounds(range,self.size);if(_scope.restored)reject(@"Scope was restored");for(NSUInteger i=range.location;i<NSMaxRange(range);i++){KPComputeICBCommand*c=_commands[i];if(c.reusableContext&&(!c.GPUGenerated||c.reusableContext.retired||c.reusableContext.generation!=c.reusableGeneration))reject(@"Reusable consumer generation is not materialized/active");}if(encoder.dispatchType!=MTLDispatchTypeSerial)reject(@"Concurrent encoders are not qualified");NSMutableArray*records=[NSMutableArray new];NSMutableArray*indices=[NSMutableArray new];
 BOOL resident=NO;for(NSUInteger i=range.location;i<NSMaxRange(range);i++)if(((KPComputeICBCommand*)_commands[i]).residentOwners.count)resident=YES;
 if(resident){
  Ivar v=class_getInstanceVariable(object_getClass(encoder),"_commandBuffer");if(!v||ivar_getOffset(v)!=32)reject(@"Resident consumer command-buffer ABI differs");id<MTLCommandBuffer>cb=object_getIvar(encoder,v);
  NSMutableArray*owners=[NSMutableArray array];NSMutableArray*ordering=[NSMutableArray array];NSMutableArray*resources=[NSMutableArray array];
  for(NSUInteger i=range.location;i<NSMaxRange(range);i++){
   KPComputeICBCommand*c=_commands[i];if(c.reusableContext&&!c.GPUGenerated)reject(@"Reusable consumer has no materialized generation");NSString*bindingError=residentBindingError(c,_scope);if(bindingError)reject(bindingError);if(!c.record.residentDescriptorReady)reject(@"Resident ranges require every slot to be occupied and prepared");
   if(c.residentOwners.count){NSDictionary*proof=residentPredecessorOrder(c.residentCopyBuffer,cb);if(!proof)reject(@"Resident copy must precede execution in this CB or be committed on the same queue before this consumer is enqueued");[ordering addObject:proof];}
   [records addObject:c.record];[indices addObject:@(i)];for(KPRecordedNativeCompute*r in c.residentOwners.count?c.residentOwners:@[c.record])if(![owners containsObject:r])[owners addObject:r];
   for(id<MTLBuffer>r in c.GPUResourceOwners)if(![resources containsObject:r])[resources addObject:r];
  }
  for(NSUInteger i=range.location;i<NSMaxRange(range);i++){KPComputeICBCommand*c=_commands[i];if(c.reusableContext){NSError*e=nil;if(![c.reusableContext track:cb generation:c.reusableGeneration error:&e])reject(e.localizedDescription);}}
  for(id<MTLBuffer>r in resources)[encoder useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];if(resources.count){NSArray*keep=[resources copy];[cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)keep.count;}];}
  NSDictionary*proof=nil;NSError*error=nil;if(![records[0] encodeResidentSequence:records owners:owners encoder:encoder suppressElementIndexes:[NSIndexSet indexSet] evidence:&proof error:&error])reject(error.localizedDescription);
  [_scope.eventRows addObject:@{@"operation":@"executeCommandsInBuffer",@"location":@(range.location),@"length":@(range.length),@"executed_indices":indices,@"resident_GPU_descriptor":@YES,@"predecessor_order":ordering,@"extra_GPU_resource_owners":@(resources.count),@"evidence":proof}];return;
 }
 for(NSUInteger i=range.location;i<NSMaxRange(range);i++){KPComputeICBCommand*c=_commands[i];if(!c.hasDispatch)continue;NSDictionary*p=[_scope profileForPipeline:c.pipeline];if([p[@"binding_layout_v2"]boolValue]){NSUInteger localCount=volume(c.local,[p[@"max_local"]unsignedIntegerValue]),groupCount=volume(c.groups,[p[@"max_invocations"]unsignedIntegerValue]);NSUInteger invocations=localCount&&groupCount&&groupCount<=[p[@"max_invocations"]unsignedIntegerValue]/localCount?localCount*groupCount:0;NSDictionary*specs=p[@"binding_specs"];if(c.bindings.count!=specs.count||!invocations||invocations>[p[@"max_invocations"]unsignedIntegerValue])reject(@"Incomplete schema2 binding/grid contract");for(NSNumber*index in specs){NSDictionary*spec=specs[index],*binding=c.bindings[index];id<MTLBuffer>b=binding[@"buffer"];NSUInteger offset=[binding[@"offset"]unsignedIntegerValue],required=MAX([spec[@"minimum_bytes"]unsignedIntegerValue],invocations*[spec[@"per_invocation_bytes"]unsignedIntegerValue]);if(!b||b.device!=_scope.device||offset>b.length||offset%[spec[@"alignment"]unsignedIntegerValue]||required>b.length-offset)reject(@"Current schema2 buffer range is insufficient");}}}
 // Validate current length uniforms before using cached packets. Updating
 // parameter bytes does not call a command setter or invalidate its record.
 for(NSUInteger i=range.location;i<NSMaxRange(range);i++){KPComputeICBCommand*c=_commands[i];if(!c.hasDispatch)continue;NSDictionary*p=[_scope profileForPipeline:c.pipeline],*m=p[@"dynamic_threadgroup"];if(m){NSNumber*constantIndex=[p[@"binding_layout_v2"]boolValue]?p[@"constant_buffer_index"]:@2;NSDictionary*binding=c.bindings[constantIndex];id<MTLBuffer>b=binding[@"buffer"];NSUInteger offset=[m[@"parameter_word_offset"]unsignedIntegerValue],base=[binding[@"offset"]unsignedIntegerValue],length=[c.threadgroupLengths[m[@"index"]]unsignedIntegerValue];uint32_t words=0;if(b.storageMode==MTLStorageModePrivate||!b.contents||base>b.length||offset>b.length-base||b.length-base-offset<4)reject(@"Dynamic shared parameter bound is not CPU-readable");memcpy(&words,(const char*)b.contents+base+offset,4);if(!length||length%16||length<[m[@"min_bytes"]unsignedIntegerValue]||length>[m[@"max_bytes"]unsignedIntegerValue]||uint64_t(words)*4!=length)reject(@"Current shared parameter bound differs from cached command allocation");}}
 for(NSUInteger i=range.location;i<NSMaxRange(range);i++){KPComputeICBCommand*c=_commands[i];if(!c.hasDispatch)continue;if(![_scope profileForPipeline:c.pipeline]||c.bindings.count!=([[_scope profileForPipeline:c.pipeline][@"binding_specs"]count]?:3))reject(@"Incomplete or unregistered command state");if(!c.record)c.record=[_scope materialize:c];[records addObject:c.record];[indices addObject:@(i)];}
 NSMutableArray *barrierIndices=[NSMutableArray new];for(NSNumber *index in indices)if(((KPComputeICBCommand*)_commands[index.unsignedIntegerValue]).barrier)[barrierIndices addObject:index];
 NSDictionary*evidence=@{};if(records.count){NSError*error=nil;if(![records[0]encodeSequence:records repetitions:1 encoder:encoder suppressElementIndexes:[NSIndexSet indexSet] evidence:&evidence error:&error])reject(error.localizedDescription);}
 [_scope.eventRows addObject:@{@"operation":@"executeCommandsInBuffer",@"location":@(range.location),@"length":@(range.length),@"executed_indices":indices,@"evidence":evidence,@"barriers_requested_before_indices":barrierIndices,@"barrier_policy":@"Native WAIT_FOR_IDLE after every dispatch; stronger serial ordering even after clearBarrier",@"concurrent_record_execution":@NO,@"empty_slots_skipped":@(range.length-records.count),@"public_ICB_contract_complete":@NO}];
}
@end

@implementation KPRenderICBCommand
- (instancetype)init{if((self=[super init])){_vertexBindings=[NSMutableDictionary new];_fragmentBindings=[NSMutableDictionary new];}return self;}
- (void)setRenderPipelineState:(id<MTLRenderPipelineState>)pipeline{
    if(!_owner||![_owner.scope.renderEngine profileForPipeline:pipeline])reject(@"Render pipeline is not owned by this scope");_pipeline=pipeline;_record=nil;
}
- (void)setVertexBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset atIndex:(NSUInteger)index{
    if(!_owner||index>=_owner.maxVertexBuffers||offset%16||(buffer&&(buffer.device!=_owner.scope.device||offset>buffer.length))||(!buffer&&offset))reject(@"Vertex binding outside descriptor/device/range");
    if(buffer)_vertexBindings[@(index)]=@{@"buffer":buffer,@"offset":@(offset)};else[_vertexBindings removeObjectForKey:@(index)];_record=nil;
}
- (void)setFragmentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset atIndex:(NSUInteger)index{
    if(!_owner||index>=_owner.maxFragmentBuffers||offset%256||(buffer&&(buffer.device!=_owner.scope.device||offset>buffer.length))||(!buffer&&offset))reject(@"Fragment binding outside descriptor/device/range");if(buffer)_fragmentBindings[@(index)]=@{@"buffer":buffer,@"offset":@(offset)};else[_fragmentBindings removeObjectForKey:@(index)];_record=nil;
}
- (void)drawPrimitives:(MTLPrimitiveType)type vertexStart:(NSUInteger)start vertexCount:(NSUInteger)count instanceCount:(NSUInteger)instances baseInstance:(NSUInteger)base{
    BOOL extended=[_owner.scope.renderEngine maxVertexBindings]>0;
    if(!_owner||!(_owner.allowedTypes&MTLIndirectCommandTypeDraw)||type!=MTLPrimitiveTypeTriangle||!count||count%3||count>4096||!instances||instances>64||start>65536-count||base>65536-instances||(!extended&&(start||count!=3||instances>2||base)))reject(@"Direct render geometry outside supported profile");
    _kind=0;_indices=nil;_offset=0;_instances=instances;_vertexStart=start;_vertexCount=count;_baseInstance=base;_baseVertex=0;_hasDraw=YES;_record=nil;
}
- (void)drawIndexedPrimitives:(MTLPrimitiveType)type indexCount:(NSUInteger)count indexType:(MTLIndexType)indexType indexBuffer:(id<MTLBuffer>)indices indexBufferOffset:(NSUInteger)offset instanceCount:(NSUInteger)instances baseVertex:(NSInteger)vertexBase baseInstance:(NSUInteger)base{
    NSUInteger bytes=indexType==MTLIndexTypeUInt16?2:indexType==MTLIndexTypeUInt32?4:0;BOOL extended=_owner.maxVertexBuffers>0;
    if(!_owner||!(_owner.allowedTypes&MTLIndirectCommandTypeDrawIndexed)||type!=MTLPrimitiveTypeTriangle||!count||count%3||count>4096||!bytes||!indices||indices.device!=_owner.scope.device||offset%bytes||offset>indices.length||count*bytes>indices.length-offset||!instances||instances>64||base>65536-instances||vertexBase<-65536||vertexBase>65536||(!extended&&(count!=3||instances>2||vertexBase||base||_vertexBindings.count)))reject(@"Indexed render geometry outside supported profile");
    _kind=bytes==2?1:2;_indices=indices;_offset=offset;_instances=instances;_vertexStart=0;_vertexCount=count;_baseInstance=base;_baseVertex=vertexBase;_hasDraw=YES;_record=nil;
}
- (void)reset{_pipeline=nil;_indices=nil;_hasDraw=NO;_record=nil;_kind=_offset=_instances=_vertexStart=_vertexCount=_baseInstance=0;_baseVertex=0;[_vertexBindings removeAllObjects];[_fragmentBindings removeAllObjects];}
- (void)copyStateFrom:(KPRenderICBCommand*)s{_pipeline=s.pipeline;_indices=s.indices;_kind=s.kind;_offset=s.offset;_instances=s.instances;_vertexStart=s.vertexStart;_vertexCount=s.vertexCount;_baseInstance=s.baseInstance;_baseVertex=s.baseVertex;_vertexBindings=[s.vertexBindings mutableCopy];_fragmentBindings=[s.fragmentBindings mutableCopy];_hasDraw=s.hasDraw;_record=s.record;}
@end

@implementation KPRenderICB
- (id<MTLIndirectRenderCommand>)indirectRenderCommandAtIndex:(NSUInteger)i{bounds(NSMakeRange(i,1),self.size);return self.commands[i];}
- (id<MTLIndirectComputeCommand>)indirectComputeCommandAtIndex:(NSUInteger)i{reject(@"Render command slots cannot be used for compute");return nil;}
- (void)executeRenderRange:(NSRange)range encoder:(id<MTLRenderCommandEncoder>)encoder target:(id<MTLTexture>)target {
    bounds(range,self.size);KPCPUICBScope*scope=self.scope;if(scope.restored||!scope.renderEngine)reject(@"Inactive rendering scope");
    NSMutableArray*records=[NSMutableArray new],*indices=[NSMutableArray new];
    NSMutableIndexSet*changedBindings=[NSMutableIndexSet new],*changedFragmentBindings=[NSMutableIndexSet new];
    for(NSUInteger i=range.location;i<NSMaxRange(range);i++){
        KPRenderICBCommand*c=self.commands[i];if(!c.hasDraw)continue;NSDictionary*p=[scope.renderEngine profileForPipeline:c.pipeline];if(!p)reject(@"Render command has no owned pipeline");NSError*error=nil;
        KPScopeLink*passLink=objc_getAssociatedObject(encoder,&contextKey);if([p[@"depth_format"]unsignedIntegerValue]!=passLink.renderPass.depthAttachment.texture.pixelFormat||[p[@"stencil_format"]unsignedIntegerValue]!=passLink.renderPass.stencilAttachment.texture.pixelFormat)reject(@"Pipeline depth/stencil formats differ from observed render pass");
        if(([p[@"target_width"]unsignedIntegerValue]?:64)!=target.width||([p[@"target_height"]unsignedIntegerValue]?:48)!=target.height||([p[@"color_format"]unsignedIntegerValue]?:MTLPixelFormatRGBA32Float)!=target.pixelFormat)reject(@"Pipeline target extent/format differs from observed render pass");
        BOOL legacy=[p[@"legacy"]boolValue];BOOL valid=c.kind&&!legacy?[scope.renderEngine validateIndexedVertexBindings:c.vertexBindings pipeline:c.pipeline indexCount:c.vertexCount indexBuffer:c.indices indexOffset:c.offset kind:c.kind instances:c.instances baseVertex:c.baseVertex baseInstance:c.baseInstance error:&error]:[scope.renderEngine validateVertexBindings:c.vertexBindings pipeline:c.pipeline vertexStart:c.vertexStart vertexCount:c.vertexCount instances:c.instances baseInstance:c.baseInstance error:&error];
        if(!valid||(legacy&&c.baseVertex))reject(error.localizedDescription?:@"Legacy baseVertex must remain zero");
        for(NSNumber*j in c.vertexBindings)[changedBindings addIndex:j.unsignedIntegerValue];if(![scope.renderEngine validateFragmentBindings:c.fragmentBindings pipeline:c.pipeline error:&error])reject(error.localizedDescription);for(NSNumber*j in c.fragmentBindings)[changedFragmentBindings addIndex:j.unsignedIntegerValue];
        if(!c.record){c.record=legacy?[scope.renderEngine prepareInheritedDrawKind:c.kind indexBuffer:c.indices offset:c.offset instances:c.instances error:&error]:c.kind&&c.fragmentBindings.count?[scope.renderEngine prepareIndexedFragmentPipeline:c.pipeline vertexBindings:c.vertexBindings fragmentBindings:c.fragmentBindings indexCount:c.vertexCount indexBuffer:c.indices indexOffset:c.offset kind:c.kind instances:c.instances baseVertex:c.baseVertex baseInstance:c.baseInstance error:&error]:c.kind?[scope.renderEngine prepareIndexedVertexPipeline:c.pipeline bindings:c.vertexBindings indexCount:c.vertexCount indexBuffer:c.indices indexOffset:c.offset kind:c.kind instances:c.instances baseVertex:c.baseVertex baseInstance:c.baseInstance error:&error]:c.fragmentBindings.count?[scope.renderEngine prepareFragmentDrawPipeline:c.pipeline vertexBindings:c.vertexBindings fragmentBindings:c.fragmentBindings vertexStart:c.vertexStart vertexCount:c.vertexCount instances:c.instances baseInstance:c.baseInstance error:&error]:[scope.renderEngine prepareVertexDrawPipeline:c.pipeline bindings:c.vertexBindings vertexStart:c.vertexStart vertexCount:c.vertexCount instances:c.instances baseInstance:c.baseInstance error:&error];
            if(!c.record)reject(error.localizedDescription);NSDictionary*meta=[(id<KPOptionalRenderRecord>)c.record evidence];[scope.eventRows addObject:@{@"operation":@"materialize_CPU_render_command",@"index":@(i),@"record":meta,@"GPU_render_dispatches":@0}];}
        [records addObject:c.record];[indices addObject:@(i)];
    }
    KPScopeLink*link=objc_getAssociatedObject(encoder,&contextKey);NSDictionary*evidence=@{};
    if(records.count){NSError*error=nil;BOOL ok=NO;link.encodingRenderICB=YES;@try{ok=[scope.renderEngine encodeInheritedRecords:records encoder:encoder target:target evidence:&evidence error:&error];if(link.callerRenderPipeline)[encoder setRenderPipelineState:link.callerRenderPipeline];
        for(NSUInteger i=changedBindings.firstIndex;i!=NSNotFound;i=[changedBindings indexGreaterThanIndex:i]){
            NSDictionary*b=link.callerVertexBindings[@(i)];if(b[@"bytes"]){NSData*d=b[@"bytes"];[encoder setVertexBytes:d.bytes length:d.length atIndex:i];}
            else[encoder setVertexBuffer:b[@"buffer"] offset:[b[@"offset"]unsignedIntegerValue] atIndex:i];
        }
        for(NSUInteger i=changedFragmentBindings.firstIndex;i!=NSNotFound;i=[changedFragmentBindings indexGreaterThanIndex:i]){NSDictionary*b=link.callerFragmentBindings[@(i)];if(b[@"bytes"]){NSData*d=b[@"bytes"];[encoder setFragmentBytes:d.bytes length:d.length atIndex:i];}else[encoder setFragmentBuffer:b[@"buffer"] offset:[b[@"offset"]unsignedIntegerValue] atIndex:i];}}@finally{link.encodingRenderICB=NO;}if(!ok)reject([error.localizedDescription stringByAppendingString:@"; discard command buffer"]);}
    [scope.eventRows addObject:@{@"operation":@"execute_CPU_render_ICB",@"location":@(range.location),@"length":@(range.length),@"executed_indices":indices,@"empty_slots_skipped":@(range.length-records.count),@"caller_pipeline_restored":@(records.count&&link.callerRenderPipeline!=nil),@"caller_vertex_slots_restored":@(changedBindings.count),@"caller_fragment_slots_restored":@(changedFragmentBindings.count),@"evidence":evidence,@"full_ICB_contract":@NO}];
}
@end

namespace {
// The public selector belongs to Objective-C's new method family (+1).
// A plain C IMP defaults to +0 under ARC and would over-release at pool drain.
id createICB(id self,SEL selector,MTLIndirectCommandBufferDescriptor*d,NSUInteger count,MTLResourceOptions options) NS_RETURNS_RETAINED;
id createICB(id self,SEL selector,MTLIndirectCommandBufferDescriptor*d,NSUInteger count,MTLResourceOptions options){KPCPUICBScope*scope=scopeFor(self);if(!scope||scope.restored)reject(@"No active ICB prototype scope");BOOL ray=[d respondsToSelector:@selector(supportRayTracing)]&&d.supportRayTracing;BOOL dynamicStride=[d respondsToSelector:@selector(supportDynamicAttributeStride)]&&d.supportDynamicAttributeStride;MTLIndirectCommandType allowed=MTLIndirectCommandTypeDraw|MTLIndirectCommandTypeDrawIndexed;BOOL render=d.commandTypes&&!(d.commandTypes&~allowed),compute=d.commandTypes==MTLIndirectCommandTypeConcurrentDispatch;BOOL typeOK=render?scope.renderEngine!=nil:compute&&scope.pipeline!=nil&&scope.profiles.count>0;BOOL bindingsOK=render?(d.maxVertexBufferBindCount==0||d.maxVertexBufferBindCount==[scope.renderEngine maxVertexBindings])&&(d.maxFragmentBufferBindCount==0||d.maxFragmentBufferBindCount==[scope.renderEngine maxFragmentBindings])&&d.maxKernelBufferBindCount==0:d.maxKernelBufferBindCount==(scope.maxKernelBindings?:3);if(!d||!typeOK||!bindingsOK||d.inheritBuffers||d.inheritPipelineState||ray||dynamicStride||count<1||count>16||options!=MTLResourceStorageModeShared)reject(@"Descriptor/options outside CPU ICB profile");KPComputeICB*b=render?[KPRenderICB new]:[KPComputeICB new];if(render){((KPRenderICB*)b).allowedTypes=d.commandTypes;((KPRenderICB*)b).maxVertexBuffers=d.maxVertexBufferBindCount;((KPRenderICB*)b).maxFragmentBuffers=d.maxFragmentBufferBindCount;}b.scope=scope;b.commands=[NSMutableArray new];b.metadata=[scope.device newBufferWithLength:count*512 options:options];if(!b.metadata)return nil;memset(b.metadata.contents,0,b.metadata.length);for(NSUInteger i=0;i<count;i++){if(render){KPRenderICBCommand*c=[KPRenderICBCommand new];c.owner=(KPRenderICB*)b;[b.commands addObject:c];}else{KPComputeICBCommand*c=[KPComputeICBCommand new];c.owner=b;[b.commands addObject:c];}}[scope.eventRows addObject:@{@"operation":@"newIndirectCommandBuffer",@"command_domain":render?@"render":@"compute",@"size":@(count),@"metadata_bytes":@(b.metadata.length),@"kernel_execution_during_creation":@0,@"runtime_dynamic_stride_selector":@([d respondsToSelector:@selector(supportDynamicAttributeStride)])}];return b;}
void executeICB(id self,SEL selector,id buffer,NSRange range){KPCPUICBScope*scope=scopeFor(self);if(!scope||scope.restored||!scope.pipeline||![buffer isKindOfClass:[KPComputeICB class]]||[buffer isKindOfClass:[KPRenderICB class]]||((KPComputeICB*)buffer).scope!=scope)reject(@"ICB/encoder context mismatch");[(KPComputeICB*)buffer executeRange:range encoder:self];}
void copyResidentICB(id self,SEL selector,id source,NSRange range,id destination,NSUInteger index){
 KPCPUICBScope*scope=scopeFor(self);
 if(!scope||scope.restored||![source isKindOfClass:KPComputeICB.class]||![destination isKindOfClass:KPComputeICB.class]||[source isKindOfClass:KPRenderICB.class]||[destination isKindOfClass:KPRenderICB.class]||((KPComputeICB*)source).scope!=scope||((KPComputeICB*)destination).scope!=scope)reject(@"Resident copy requires compute ICBs from this scope");
 KPComputeICB*s=source,*d=destination;bounds(range,s.size);bounds(NSMakeRange(index,range.length),d.size);
 if(!range.length){[scope.eventRows addObject:@{@"operation":@"GPU_QMD_copy",@"length":@0,@"encoded_GPU_blits":@0}];return;}
 if(range.length>16||(s==d&&NSIntersectionRange(range,NSMakeRange(index,range.length)).length))reject(@"Resident copy needs bounded nonoverlapping occupied ranges");
 Ivar v=class_getInstanceVariable(object_getClass(self),"_commandBuffer");if(!v||ivar_getOffset(v)!=32)reject(@"Resident blit command-buffer ABI differs");id<MTLCommandBuffer>cb=object_getIvar(self,v);
 if(!cb||cb.commandQueue!=scope.queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)reject(@"Resident copy needs a retained recording CB from this queue");
 // Preflight the whole operation before a blit or CPU-state mutation. Owners
 // are records, never command objects; chains therefore do not create cycles.
 NSMutableArray*plans=[NSMutableArray array];NSMutableArray*retained=[NSMutableArray array];NSMutableArray*ordering=[NSMutableArray array];
 for(NSUInteger k=0;k<range.length;k++){
  KPComputeICBCommand*a=s.commands[range.location+k],*b=d.commands[index+k];if(a.reusableContext||b.reusableContext)reject(@"GPU copying reusable command state is not qualified");
  for(KPComputeICBCommand*c in @[a,b]){NSString*bindingError=residentBindingError(c,scope);if(bindingError)reject(bindingError);if(!c.record.residentDescriptorReady)reject(@"Resident copy requires prepared registered native profiles");}
  if(!sameResidentRegistration([scope profileForPipeline:a.pipeline],[scope profileForPipeline:b.pipeline]))reject(@"Resident copy registration domain differs");
  for(KPComputeICBCommand*c in @[a,b])if(c.residentOwners.count){NSDictionary*proof=residentPredecessorOrder(c.residentCopyBuffer,cb);if(!proof)reject(@"A prior source/destination copy must be ordered in this CB or committed on the same queue before this consumer is enqueued");[ordering addObject:proof];}
  NSMutableArray*owners=[NSMutableArray array];for(KPRecordedNativeCompute*r in @[b.record,a.record])if(![owners containsObject:r])[owners addObject:r];for(KPComputeICBCommand*c in @[a,b])for(KPRecordedNativeCompute*r in c.residentOwners)if(![owners containsObject:r])[owners addObject:r];if(owners.count>16)reject(@"Resident copy owner set exceeds its qualified bound");
  for(KPRecordedNativeCompute*r in owners){NSError*error=nil;if(![r validateResidentThreadgroupMemory:&error])reject(error.localizedDescription);}
  [plans addObject:@{@"source":a,@"destination":b,@"source_record":a.record,@"destination_record":b.record,@"owners":[owners copy]}];for(KPRecordedNativeCompute*r in owners)if(![retained containsObject:r])[retained addObject:r];
 }
 NSMutableArray*addresses=[NSMutableArray array];
 for(NSDictionary*plan in plans){KPComputeICBCommand*a=plan[@"source"],*b=plan[@"destination"];KPRecordedNativeCompute*src=plan[@"source_record"],*dst=plan[@"destination_record"];
  [(id<MTLBlitCommandEncoder>)self copyFromBuffer:src.descriptor sourceOffset:0 toBuffer:dst.descriptor destinationOffset:0 size:256];
  [b copyStateFrom:a];b.record=dst;b.residentOwners=plan[@"owners"];b.residentCopyBuffer=cb;
  [addresses addObject:@{@"source":@(src.descriptor.gpuAddress),@"destination":@(dst.descriptor.gpuAddress),@"owners":@(b.residentOwners.count),@"GPU_selected_command":@(a.GPUGenerated),@"CPU_shadow_function":[scope profileForPipeline:a.pipeline][@"function"],@"copied_function":a.GPUGenerated?(id)NSNull.null:[scope profileForPipeline:a.pipeline][@"function"],@"copied_groups":a.GPUGenerated?(id)NSNull.null:@(a.groups.width),@"copied_local":a.GPUGenerated?(id)NSNull.null:@(a.local.width),@"copied_dynamic_threadgroup_bytes":a.GPUGenerated?(id)NSNull.null:@(a.threadgroupLengths.count?[a.threadgroupLengths[@0]unsignedIntegerValue]:0),@"destination_original_function":dst.relocationEvidence[@"function"],@"destination_original_groups":dst.relocationEvidence[@"groups_shape"][0],@"destination_original_local":dst.relocationEvidence[@"local_shape"][0],@"destination_original_dynamic_threadgroup_bytes":dst.relocationEvidence[@"dynamic_threadgroup_length"]}];
 }
 NSArray*frozenOwners=[retained copy];[cb addCompletedHandler:^(id<MTLCommandBuffer>completed){(void)frozenOwners.count;}];
 [scope.eventRows addObject:@{@"operation":@"GPU_QMD_copy",@"source_location":@(range.location),@"destination_index":@(index),@"length":@(range.length),@"bytes":@(range.length*256),@"source_QMD_address":addresses[0][@"source"],@"destination_QMD_address":addresses[0][@"destination"],@"descriptor_pairs":addresses,@"predecessor_order":ordering,@"retained_owners":@(retained.count),@"encoded_GPU_blits":@(range.length),@"whole_range_preflight":@YES,@"CPU_shadow_updated_for_setters":@YES,@"CPU_shadow_is_execution_source":@NO,@"full_ICB_contract":@NO}];
}
#include "KeplerIndirectRenderExecution.inc"
void executeRenderICB(id self,SEL selector,id buffer,NSRange range){KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);KPCPUICBScope*scope=link.scope;if(!scope||scope.restored||!scope.renderEngine||![buffer isKindOfClass:[KPRenderICB class]]||((KPRenderICB*)buffer).scope!=scope||!link.renderTarget)reject(@"Render ICB/encoder context mismatch");[(KPRenderICB*)buffer executeRenderRange:range encoder:self target:link.renderTarget];}
void setCallerRenderPipeline(id self,SEL selector,id pipeline){KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);Class original=class_getSuperclass(object_getClass(self));Method method=class_getInstanceMethod(original,selector);((void(*)(id,SEL,id))method_getImplementation(method))(self,selector,pipeline);if(link&&!link.encodingRenderICB)link.callerRenderPipeline=pipeline;}
void setCallerVertexBuffer(id self,SEL selector,id buffer,NSUInteger offset,NSUInteger index){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);if(index>=31)reject(@"Vertex binding index exceeds native API range");
    Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);((void(*)(id,SEL,id,NSUInteger,NSUInteger))method_getImplementation(m))(self,selector,buffer,offset,index);
    if(link&&!link.encodingRenderICB)link.callerVertexBindings[@(index)]=buffer?@{@"buffer":buffer,@"offset":@(offset)}:@{@"offset":@0};
}
void setCallerVertexBuffers(id self,SEL selector,const id<MTLBuffer> __unsafe_unretained*buffers,const NSUInteger*offsets,NSRange range){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);if(range.location>31||range.length>31-range.location||range.length&&(!buffers||!offsets))reject(@"Vertex binding array range exceeds native API range");
    Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);using F=void(*)(id,SEL,const id<MTLBuffer> __unsafe_unretained*,const NSUInteger*,NSRange);((F)method_getImplementation(m))(self,selector,buffers,offsets,range);
    if(link&&!link.encodingRenderICB)for(NSUInteger i=0;i<range.length;i++)link.callerVertexBindings[@(range.location+i)]=buffers[i]?@{@"buffer":buffers[i],@"offset":@(offsets[i])}:@{@"offset":@0};
}
void setCallerVertexOffset(id self,SEL selector,NSUInteger offset,NSUInteger index){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);NSDictionary*b=link.callerVertexBindings[@(index)];
    if(index>=31||link&&!link.encodingRenderICB&&(!b[@"buffer"]||offset>[b[@"buffer"]length]))reject(@"Offset requires a tracked caller vertex buffer");
    Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);((void(*)(id,SEL,NSUInteger,NSUInteger))method_getImplementation(m))(self,selector,offset,index);
    if(link&&!link.encodingRenderICB)link.callerVertexBindings[@(index)]=@{@"buffer":b[@"buffer"],@"offset":@(offset)};
}
void setCallerVertexBytes(id self,SEL selector,const void*bytes,NSUInteger length,NSUInteger index){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);if(index>=31||length>4096||length&&!bytes)reject(@"Caller inline vertex data exceeds native range");
    NSData*copy=[NSData dataWithBytes:bytes length:length];Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);((void(*)(id,SEL,const void*,NSUInteger,NSUInteger))method_getImplementation(m))(self,selector,copy.bytes,length,index);
    if(link&&!link.encodingRenderICB)link.callerVertexBindings[@(index)]=@{@"bytes":copy};
}
void setCallerFragmentBuffer(id self,SEL selector,id buffer,NSUInteger offset,NSUInteger index){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);if(index>=31)reject(@"Fragment binding index exceeds native API range");
    Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);((void(*)(id,SEL,id,NSUInteger,NSUInteger))method_getImplementation(m))(self,selector,buffer,offset,index);
    if(link&&!link.encodingRenderICB)link.callerFragmentBindings[@(index)]=buffer?@{@"buffer":buffer,@"offset":@(offset)}:@{@"offset":@0};
}
void setCallerFragmentBuffers(id self,SEL selector,const id<MTLBuffer> __unsafe_unretained*buffers,const NSUInteger*offsets,NSRange range){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);if(range.location>31||range.length>31-range.location||range.length&&(!buffers||!offsets))reject(@"Fragment binding array range exceeds native API range");
    Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);using F=void(*)(id,SEL,const id<MTLBuffer> __unsafe_unretained*,const NSUInteger*,NSRange);((F)method_getImplementation(m))(self,selector,buffers,offsets,range);
    if(link&&!link.encodingRenderICB)for(NSUInteger i=0;i<range.length;i++)link.callerFragmentBindings[@(range.location+i)]=buffers[i]?@{@"buffer":buffers[i],@"offset":@(offsets[i])}:@{@"offset":@0};
}
void setCallerFragmentOffset(id self,SEL selector,NSUInteger offset,NSUInteger index){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);NSDictionary*b=link.callerFragmentBindings[@(index)];
    if(index>=31||link&&!link.encodingRenderICB&&(!b[@"buffer"]||offset>[b[@"buffer"]length]))reject(@"Offset requires a tracked caller fragment buffer");
    Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);((void(*)(id,SEL,NSUInteger,NSUInteger))method_getImplementation(m))(self,selector,offset,index);
    if(link&&!link.encodingRenderICB)link.callerFragmentBindings[@(index)]=@{@"buffer":b[@"buffer"],@"offset":@(offset)};
}
void setCallerFragmentBytes(id self,SEL selector,const void*bytes,NSUInteger length,NSUInteger index){
    KPScopeLink*link=objc_getAssociatedObject(self,&contextKey);if(index>=31||length>4096||length&&!bytes)reject(@"Caller inline fragment data exceeds native range");
    NSData*copy=[NSData dataWithBytes:bytes length:length];Method m=class_getInstanceMethod(class_getSuperclass(object_getClass(self)),selector);((void(*)(id,SEL,const void*,NSUInteger,NSUInteger))method_getImplementation(m))(self,selector,copy.bytes,length,index);
    if(link&&!link.encodingRenderICB)link.callerFragmentBindings[@(index)]=@{@"bytes":copy};
}
BOOL installRenderOverride(Class dynamic,Class original,SEL selector,IMP implementation){Method base=class_getInstanceMethod(original,selector),now=class_getInstanceMethod(dynamic,selector);return base&&now&&(method_getImplementation(now)==implementation||class_addMethod(dynamic,selector,implementation,method_getTypeEncoding(base)));}
}

@implementation KPCPUICBScope
- (instancetype)init{if((self=[super init]))_factoryLock=[NSObject new];return self;}
+ (instancetype)installOnDevice:(id<MTLDevice>)device queue:(id<MTLCommandQueue>)queue pipeline:(id<MTLComputePipelineState>)pipeline error:(NSError**)error {
 std::lock_guard<std::mutex>lock(installMutex);NSData*d=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];if(!KPKeplerDriverHashIsQualified(hash(d))||!KPKepler880MIdentity(device)||queue.device!=device||pipeline.device!=device||objc_getAssociatedObject(device,&contextKey)){fail(error,@"Device/driver/queue/pipeline or existing scope mismatch");return nil;}
 KPCPUICBScope*s=[self new];s.device=device;s.queue=queue;s.pipeline=pipeline;s.eventRows=[NSMutableArray new];s.adapted=[NSMutableArray new];s.profiles=[NSMutableDictionary new];s.namedPipelines=[NSMutableDictionary new];s.originalDeviceClass=object_getClass(device);s.profiles[[NSValue valueWithPointer:(__bridge const void*)pipeline]]=@{@"function":@"consume_grid",@"library_SHA256":@"b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d",@"static_threadgroup_bytes":@0};s.namedPipelines[@"consume_grid"]=pipeline;
 Class dynamic=scopedClass(deviceClasses,s.originalDeviceClass,@"KPICBDevice_",@selector(newIndirectCommandBufferWithDescriptor:maxCommandCount:options:),(IMP)createICB,error);if(!dynamic)return nil;linkScope(device,s);object_setClass(device,dynamic);[s.eventRows addObject:@{@"operation":@"scope_install",@"original_class":NSStringFromClass(s.originalDeviceClass),@"dynamic_class":NSStringFromClass(dynamic),@"cached_device_classes":@(deviceClasses.size()),@"capabilities_spoofed":@NO,@"scope":@"Own device object only; no shared-class method replacement"}];return s;
}
+ (instancetype)installOnDevice:(id<MTLDevice>)device queue:(id<MTLCommandQueue>)queue libraryURL:(NSURL*)url expectedSHA256:(NSString*)expected error:(NSError**)error {
 NSData*bytes=[NSData dataWithContentsOfURL:url];NSString*actual=hash(bytes);if(![actual isEqual:expected]||![actual isEqual:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd"]){fail(error,@"Native library identity is not a qualified snapshot");return nil;}
 id<MTLLibrary>library=libraryFromSnapshot(device,bytes,error);if(!library)return nil;NSMutableDictionary*named=[NSMutableDictionary new],*profiles=[NSMutableDictionary new];
 for(NSString*name in @[@"profile_integer",@"profile_fma",@"profile_shared"]){id<MTLFunction>function=[library newFunctionWithName:name];MTLComputePipelineReflection*reflection=nil;id<MTLComputePipelineState>pipeline=[device newComputePipelineStateWithFunction:function options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:error];if(!pipeline||reflection.arguments.count!=3||![[function name]isEqual:name]){fail(error,@"Native function/reflection is incomplete");return nil;}
  // The native reflection reports access1 (ReadWrite) for device pointers,
  // including output-only use. WriteOnly is enum2 in the SDK, not enum1.
  NSUInteger sizes[3]={16,4,16},alignments[3]={16,4,256};MTLDataType types[3]={MTLDataTypeUInt4,MTLDataTypeStruct,MTLDataTypeStruct};MTLArgumentAccess accesses[3]={MTLArgumentAccessReadWrite,MTLArgumentAccessReadWrite,MTLArgumentAccessReadOnly};NSString*argumentNames[3]={@"out",@"count",@"p"};NSMutableArray*rows=[NSMutableArray new];unsigned mask=0;
  for(MTLArgument*argument in reflection.arguments){NSUInteger i=argument.index;if(i>=3||mask&(1u<<i)||argument.type!=MTLArgumentTypeBuffer||!argument.active||argument.bufferDataSize!=sizes[i]||argument.bufferAlignment!=alignments[i]||argument.bufferDataType!=types[i]||argument.access!=accesses[i]||![argument.name isEqual:argumentNames[i]]){fail(error,@"Native buffer ABI differs from registered profile");return nil;}mask|=1u<<i;[rows addObject:@{@"index":@(i),@"size":@(argument.bufferDataSize),@"alignment":@(argument.bufferAlignment),@"type":@(argument.bufferDataType),@"access":@(argument.access)}];}
  BOOL shared=[name isEqual:@"profile_shared"];if(![pipeline respondsToSelector:@selector(staticThreadgroupMemoryLength)]||pipeline.staticThreadgroupMemoryLength!=(shared?512:0)||pipeline.threadExecutionWidth!=32){fail(error,@"Static shared memory or execution width differs");return nil;}
  named[name]=pipeline;profiles[[NSValue valueWithPointer:(__bridge const void*)pipeline]]=@{@"function":name,@"library_SHA256":actual,@"library_owner":library,@"static_threadgroup_bytes":@(shared?512:0),@"expected_register_count":@(shared?8:7),@"reflection":rows};
 }
 KPCPUICBScope*s=[self installOnDevice:device queue:queue pipeline:named[@"profile_integer"] error:error];if(!s)return nil;s.profiles=profiles;s.namedPipelines=named;[s.eventRows addObject:@{@"operation":@"registered_native_library",@"library_SHA256":actual,@"functions":@[@"profile_integer",@"profile_fma",@"profile_shared"],@"identity_source":@"Pipelines created here from verified library and named MTLFunctions; labels not trusted"}];return s;
}
+ (instancetype)installRenderingOnDevice:(id<MTLDevice>)device queue:(id<MTLCommandQueue>)queue libraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
    std::lock_guard<std::mutex>lock(installMutex);NSData*snapshot=[data copy];Class transport=NSClassFromString(@"KPNativeRenderDrawBatch");
    if(!transport||!KPKepler880MIdentity(device)||queue.device!=device||objc_getAssociatedObject(device,&contextKey)||!digestString(expected)||![hash(snapshot)isEqual:expected]){fail(error,@"Rendering module, queue, snapshot or scope mismatch");return nil;}
    id<KPCPURenderTransport>engine=[(id<KPCPURenderTransport>)[transport alloc]initWithQueue:queue libraryData:snapshot error:error];if(!engine)return nil;
    KPCPUICBScope*s=[self new];s.device=device;s.queue=queue;s.renderEngine=engine;s.profiles=[NSMutableDictionary new];s.namedPipelines=[NSMutableDictionary new];s.eventRows=[NSMutableArray new];s.adapted=[NSMutableArray new];s.originalDeviceClass=object_getClass(device);
    Class dynamic=scopedClass(deviceClasses,s.originalDeviceClass,@"KPICBDevice_",@selector(newIndirectCommandBufferWithDescriptor:maxCommandCount:options:),(IMP)createICB,error);if(!dynamic)return nil;linkScope(device,s);object_setClass(device,dynamic);
    [s.eventRows addObject:@{@"operation":@"scope_install_rendering",@"library_SHA256":expected,@"original_class":NSStringFromClass(s.originalDeviceClass),@"dynamic_class":NSStringFromClass(dynamic),@"cached_device_classes":@(deviceClasses.size()),@"capabilities_spoofed":@NO,@"shader_code_patched":@NO}];return s;
}
- (id<MTLRenderPipelineState>)renderPipeline{return [_renderEngine pipeline];}
- (id<MTLRenderPipelineState>)renderPipelineForName:(NSString*)name{return _restored?nil:[_renderEngine pipelineForName:name];}
- (BOOL)encodeFragmentArgumentBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset pipelineName:(NSString*)name bindingIndex:(NSUInteger)index resources:(NSDictionary*)resources error:(NSError**)error{if(_restored||!_renderEngine)return fail(error,@"Active render scope required");BOOL ok=[_renderEngine encodeFragmentArgumentBuffer:buffer offset:offset pipelineName:name bindingIndex:index resources:resources error:error];if(ok)[_eventRows addObject:@{@"operation":@"encode_native_fragment_argument_buffer",@"pipeline_name":name,@"binding_index":@(index),@"offset":@(offset),@"resource_count":@(resources.count),@"argument_bytes_encoded_by_native_API":@YES}];return ok;}
- (id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString*)name bindingIndex:(NSUInteger)index sources:(NSArray*)sources selectedBank:(NSUInteger)bank commandBuffer:(id<MTLCommandBuffer>)cb counter:(id<MTLBuffer>*)counter error:(NSError**)error {
    if(_restored||!_renderEngine){fail(error,@"Active rendering scope required");return nil;}
    id<MTLBuffer>b=[_renderEngine newPrivateFragmentArgumentBufferForPipeline:name bindingIndex:index sources:sources selectedBank:bank commandBuffer:cb counter:counter error:error];
    if(b)[_eventRows addObject:@{@"operation":@"create_Private_fragment_argument_buffer",@"pipeline_name":name,@"binding_index":@(index),@"offset":@256,@"source_tables":@(sources.count),@"selected_bank":@(bank),@"producer":sources.count==2?@"native_compute_selector":@"native_blit",@"storage_mode":@(b.storageMode),@"CPU_access_to_Private_contents":@NO,@"client_must_not_write_result":@YES}];return b;
}

- (BOOL)registerRenderVertexLibraryData:(NSData*)data expectedSHA256:(NSString*)expected manifestData:(NSData*)manifest expectedManifestSHA256:(NSString*)manifestSHA error:(NSError**)error {
    if(_restored||!_renderEngine)return fail(error,@"Active rendering scope required");
    if(![_renderEngine registerVertexLibraryData:data expectedSHA256:expected manifestData:manifest expectedManifestSHA256:manifestSHA error:error])return NO;
    [_eventRows addObject:@{@"operation":@"register_render_vertex_library",@"library_SHA256":expected,@"manifest_SHA256":manifestSHA,@"max_vertex_bindings":@([_renderEngine maxVertexBindings]),@"registration_is_GPU_qualification":@NO,@"loader":@"immutable_in_memory_bytes",@"identity_source":@"Named functions, owned PSO, reflected stage-in ABI and manifest; labels not trusted"}];return YES;
}
- (BOOL)registerArgumentTableSelectorLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
    if(_restored||!_renderEngine)return fail(error,@"Active rendering scope required");BOOL ok=[_renderEngine registerArgumentTableSelectorLibraryData:data expectedSHA256:expected error:error];if(ok)[_eventRows addObject:@{@"operation":@"register_argument_table_selector",@"library_SHA256":expected,@"independent_of_fragment_library":@YES,@"registration_is_GPU_execution":@NO}];return ok;
}
- (id<MTLBuffer>)newPrivateFragmentArgumentBufferForPipeline:(NSString*)name bindingIndex:(NSUInteger)index sources:(NSArray*)sources selectionBuffer:(id<MTLBuffer>)selection selectionOffset:(NSUInteger)offset commandBuffer:(id<MTLCommandBuffer>)cb counter:(id<MTLBuffer>*)counter error:(NSError**)error {
    if(_restored||!_renderEngine){fail(error,@"Active rendering scope required");return nil;}id<MTLBuffer>b=[_renderEngine newPrivateFragmentArgumentBufferForPipeline:name bindingIndex:index sources:sources selectionBuffer:selection selectionOffset:offset commandBuffer:cb counter:counter error:error];if(b)[_eventRows addObject:@{@"operation":@"create_GPU_selected_Private_fragment_table",@"pipeline_name":name,@"binding_index":@(index),@"offset":@256,@"source_tables":@(sources.count),@"selection_offset":@(offset),@"CPU_read_of_selection":@NO,@"selection_value_supplied_by_CPU":@NO}];return b;
}

- (BOOL)registerRenderingLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
    if(_restored||_renderEngine||!_pipeline||!_profiles.count)return fail(error,@"Active compute scope required, rendering already registered or restored");
    NSData*snapshot=[data copy];Class transport=NSClassFromString(@"KPNativeRenderDrawBatch");if(!transport||!digestString(expected)||![hash(snapshot)isEqual:expected])return fail(error,@"Rendering module or library identity mismatch");
    id<KPCPURenderTransport>engine=[(id<KPCPURenderTransport>)[transport alloc]initWithQueue:_queue libraryData:snapshot error:error];if(!engine)return NO;_renderEngine=engine;
    [_eventRows addObject:@{@"operation":@"register_render_domain",@"library_SHA256":expected,@"compute_domain_preserved":@YES,@"device_class_unchanged":@YES,@"capabilities_spoofed":@NO}];return YES;
}
- (id<MTLRenderCommandEncoder>)renderEncoderWithDescriptor:(MTLRenderPassDescriptor*)descriptor commandBuffer:(id<MTLCommandBuffer>)cb error:(NSError**)error {
    MTLRenderPassDescriptor*pass=[descriptor copy];id<MTLTexture>target=pass.colorAttachments[0].texture;
    if(_restored||!_renderEngine||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||target.device!=_device||![_renderEngine acceptsRenderTarget:target]||target.textureType!=MTLTextureType2D||target.sampleCount!=1||target.mipmapLevelCount!=1||pass.colorAttachments[0].level||pass.colorAttachments[0].slice||pass.colorAttachments[0].depthPlane||pass.colorAttachments[0].loadAction!=MTLLoadActionClear||pass.colorAttachments[0].storeAction!=MTLStoreActionStore||pass.visibilityResultBuffer){fail(error,@"Render pass outside registered native target profiles");return nil;}
    id<MTLTexture>depth=pass.depthAttachment.texture,stencil=pass.stencilAttachment.texture;
    if(depth&&(depth.device!=_device||depth.width!=target.width||depth.height!=target.height||depth.textureType!=MTLTextureType2D||depth.sampleCount!=1||depth.mipmapLevelCount!=1||(depth.pixelFormat!=MTLPixelFormatDepth32Float&&depth.pixelFormat!=MTLPixelFormatDepth32Float_Stencil8)||pass.depthAttachment.level||pass.depthAttachment.slice||pass.depthAttachment.depthPlane||pass.depthAttachment.loadAction!=MTLLoadActionClear||pass.depthAttachment.storeAction!=MTLStoreActionStore||!std::isfinite(pass.depthAttachment.clearDepth)||pass.depthAttachment.clearDepth<0||pass.depthAttachment.clearDepth>1)){fail(error,@"Depth attachment outside qualified profile");return nil;}
    if(stencil&&(stencil!=depth||stencil.pixelFormat!=MTLPixelFormatDepth32Float_Stencil8||pass.stencilAttachment.level||pass.stencilAttachment.slice||pass.stencilAttachment.depthPlane||pass.stencilAttachment.loadAction!=MTLLoadActionClear||pass.stencilAttachment.storeAction!=MTLStoreActionStore||pass.stencilAttachment.clearStencil>255)){fail(error,@"Stencil attachment must share the qualified combined depth texture");return nil;}
    for(NSUInteger i=1;i<8;i++)if(pass.colorAttachments[i].texture){fail(error,@"Multiple render targets are not qualified here");return nil;}
    id<MTLRenderCommandEncoder>e=[cb renderCommandEncoderWithDescriptor:pass];Class original=object_getClass(e),native=objc_getClass("NVMTLRenderCommandEncoder_KEPLER_A");if(!e||original!=native||class_getInstanceSize(original)!=128){if(e)[e endEncoding];fail(error,@"Native render encoder layout changed");return nil;}
    Class dynamic=nil;{std::lock_guard<std::mutex>lock(installMutex);dynamic=scopedClass(renderEncoderClasses,original,@"KPICBRenderEncoder_",@selector(executeCommandsInBuffer:withRange:),(IMP)executeRenderICB,error);if(dynamic&&(!installRenderOverride(dynamic,original,@selector(setRenderPipelineState:),(IMP)setCallerRenderPipeline)||!installRenderOverride(dynamic,original,@selector(executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:),(IMP)executeIndirectRenderICB)||!installRenderOverride(dynamic,original,@selector(setVertexBuffer:offset:atIndex:),(IMP)setCallerVertexBuffer)||!installRenderOverride(dynamic,original,@selector(setVertexBuffers:offsets:withRange:),(IMP)setCallerVertexBuffers)||!installRenderOverride(dynamic,original,@selector(setVertexBufferOffset:atIndex:),(IMP)setCallerVertexOffset)||!installRenderOverride(dynamic,original,@selector(setVertexBytes:length:atIndex:),(IMP)setCallerVertexBytes)||!installRenderOverride(dynamic,original,@selector(setFragmentBuffer:offset:atIndex:),(IMP)setCallerFragmentBuffer)||!installRenderOverride(dynamic,original,@selector(setFragmentBuffers:offsets:withRange:),(IMP)setCallerFragmentBuffers)||!installRenderOverride(dynamic,original,@selector(setFragmentBufferOffset:atIndex:),(IMP)setCallerFragmentOffset)||!installRenderOverride(dynamic,original,@selector(setFragmentBytes:length:atIndex:),(IMP)setCallerFragmentBytes)))dynamic=nil;}
    if(!dynamic){[e endEncoding];fail(error,@"Scoped render methods unavailable");return nil;}
    NSMutableIndexSet*expired=[NSMutableIndexSet new];for(NSUInteger i=0;i<_adapted.count;i++)if(!((KPAdaptedEncoder*)_adapted[i]).encoder)[expired addIndex:i];_releasedEncoderCount+=expired.count;[_adapted removeObjectsAtIndexes:expired];
    linkScope(e,self);KPScopeLink*link=objc_getAssociatedObject(e,&contextKey);link.renderTarget=target;link.renderPass=pass;link.callerVertexBindings=[NSMutableDictionary new];link.callerFragmentBindings=[NSMutableDictionary new];object_setClass(e,dynamic);KPAdaptedEncoder*r=[KPAdaptedEncoder new];r.encoder=e;r.originalClass=original;[_adapted addObject:r];
    // The observed descriptor is immutable and also leases its attachments
    // after scope restoration, until the command buffer completes.
    [cb addCompletedHandler:^(id<MTLCommandBuffer>done){(void)pass.colorAttachments[0].texture;}];
    [self.eventRows addObject:@{@"operation":@"adapt_render_encoder",@"native_constructor_observed":@YES,@"cached_render_encoder_classes":@(renderEncoderClasses.size()),@"scissor_state_inherited":@YES}];return e;
}
+ (instancetype)installOnDevice:(id<MTLDevice>)device queue:(id<MTLCommandQueue>)queue libraryURL:(NSURL*)url expectedSHA256:(NSString*)expected manifestURL:(NSURL*)manifestURL expectedManifestSHA256:(NSString*)manifestSHA error:(NSError**)error {
 return [self installOnDevice:device queue:queue libraryData:[NSData dataWithContentsOfURL:url] expectedSHA256:expected manifestData:[NSData dataWithContentsOfURL:manifestURL] expectedManifestSHA256:manifestSHA error:error];
}
+ (instancetype)installOnDevice:(id<MTLDevice>)device queue:(id<MTLCommandQueue>)queue libraryData:(NSData*)libraryData expectedSHA256:(NSString*)expected manifestData:(NSData*)manifestData expectedManifestSHA256:(NSString*)manifestSHA error:(NSError**)error {
 return [self installOnDevice:device queue:queue libraryData:libraryData expectedSHA256:expected manifestData:manifestData expectedManifestSHA256:manifestSHA nativeCASCertificates:nil expectedCertificateSHA256:nil error:error];
}
+ (instancetype)installOnDevice:(id<MTLDevice>)device queue:(id<MTLCommandQueue>)queue libraryData:(NSData*)libraryData expectedSHA256:(NSString*)expected manifestData:(NSData*)manifestData expectedManifestSHA256:(NSString*)manifestSHA nativeCASCertificates:(NSDictionary*)certificates expectedCertificateSHA256:(NSDictionary*)certificateHashes error:(NSError**)error {
 NSData*bytes=libraryData?[NSData dataWithBytes:libraryData.bytes length:libraryData.length]:nil,*manifestBytes=manifestData?[NSData dataWithBytes:manifestData.bytes length:manifestData.length]:nil;
 if(!digestString(expected)||!digestString(manifestSHA)||!bytes||!manifestBytes||manifestBytes.length>1048576||![hash(bytes)isEqual:expected]||![hash(manifestBytes)isEqual:manifestSHA]){fail(error,@"Native library/manifest content identity differs");return nil;}
 id decoded=[NSJSONSerialization JSONObjectWithData:manifestBytes options:0 error:error];if(![decoded isKindOfClass:[NSDictionary class]]){fail(error,@"Manifest is not a dictionary");return nil;}NSDictionary*manifest=decoded;id functions=manifest[@"functions"];
 if(!wholeNumber(manifest[@"schema"],1,2)||![manifest[@"library_SHA256"]isEqual:expected]||![functions isKindOfClass:[NSArray class]]||[functions count]<1||[functions count]>16){fail(error,@"Native registration manifest header differs");return nil;}
 NSMutableDictionary *certificateSnapshots=[NSMutableDictionary new];
 if(certificates||certificateHashes){
  if(![certificates isKindOfClass:NSDictionary.class]||![certificateHashes isKindOfClass:NSDictionary.class]||certificates.count<1||certificates.count>[functions count]||certificates.count!=certificateHashes.count){fail(error,@"Native CAS certificate map differs");return nil;}
  NSMutableSet *names=[NSMutableSet new];for(id spec in functions){if([spec isKindOfClass:NSDictionary.class]&&[spec[@"name"]isKindOfClass:NSString.class])[names addObject:spec[@"name"]];}
  for(id name in certificates){id input=certificates[name];NSString *pin=certificateHashes[name];if(![name isKindOfClass:NSString.class]||![names containsObject:name]||![input isKindOfClass:NSData.class]||![input length]||[input length]>1048576||!digestString(pin)){fail(error,@"Native CAS certificate identity/name differs");return nil;}NSData *snapshot=[NSData dataWithBytes:[input bytes] length:[input length]];if(![hash(snapshot)isEqual:pin]){fail(error,@"Native CAS certificate bytes differ");return nil;}certificateSnapshots[name]=snapshot;}
 }
 Class<KPOptionalNativeCASFactory> factory=certificateSnapshots.count?(Class<KPOptionalNativeCASFactory>)NSClassFromString(@"KPCertifiedNativeCASFactory"):nil;
 if(certificateSnapshots.count&&(!factory||![factory respondsToSelector:@selector(newPipelineForDevice:function:libraryData:expectedSHA256:certificateData:expectedCertificateSHA256:options:reflection:error:evidence:)])){fail(error,@"Optional native CAS module is not linked");return nil;}
 BOOL extended=[manifest[@"schema"]unsignedIntegerValue]==2;NSUInteger maxBindings=0;id<MTLLibrary>library=libraryFromSnapshot(device,bytes,error);if(!library)return nil;NSString*registration=[NSUUID UUID].UUIDString;NSMutableDictionary*named=[NSMutableDictionary new],*profiles=[NSMutableDictionary new];NSMutableArray*registered=[NSMutableArray new];
 for(id object in functions){if(![object isKindOfClass:[NSDictionary class]]){fail(error,@"Function specification is not a dictionary");return nil;}NSDictionary*spec=object;id name=spec[@"name"],buffers=spec[@"buffers"],memory=spec[@"dynamic_threadgroup"];
  if(![name isKindOfClass:[NSString class]]||![name length]||[name length]>256||named[name]||![buffers isKindOfClass:[NSArray class]]||([buffers count]<(extended?2:3)||[buffers count]>(extended?16:3))||!wholeNumber(spec[@"static_threadgroup_bytes"],0,49152)||!wholeNumber(spec[@"max_local"],1,1024)||!wholeNumber(spec[@"qmd_register_count"],1,63)){fail(error,@"Unsupported function/ABI/resource specification");return nil;}
  if(extended&&(!wholeNumber(spec[@"constant_buffer_index"],0,15)||!wholeNumber(spec[@"max_invocations"],1,65536))){fail(error,@"Schema2 requires one constant binding and bounded buffer compute");return nil;}
  NSDictionary *literalBank=spec[@"native_literal_bank_0"];
  if(literalBank&&(!extended||![literalBank isKindOfClass:NSDictionary.class]||!wholeNumber(literalBank[@"bytes"],256,1024)||![@[@256,@512,@1024]containsObject:literalBank[@"bytes"]]||![literalBank[@"address_relation"]isEqual:@"native_code_end_aligned_256"])){fail(error,@"Unqualified native literal-bank profile");return nil;}
  if(memory&&(![memory isKindOfClass:[NSDictionary class]]||!wholeNumber(memory[@"index"],0,0)||!wholeNumber(memory[@"min_bytes"],16,49152)||!wholeNumber(memory[@"max_bytes"],[memory[@"min_bytes"]unsignedIntegerValue],49152-[spec[@"static_threadgroup_bytes"]unsignedIntegerValue])||[memory[@"min_bytes"]unsignedIntegerValue]%16||[memory[@"max_bytes"]unsignedIntegerValue]%16||!wholeNumber(memory[@"parameter_word_offset"],0,508))){fail(error,@"Only bounded threadgroup argument0 with a length parameter is registered");return nil;}
  NSMutableDictionary*bufferSpecs=[NSMutableDictionary new];
  for(id argument in buffers){if(![argument isKindOfClass:[NSDictionary class]]||!wholeNumber(argument[@"index"],0,extended?15:2)||bufferSpecs[argument[@"index"]]){fail(error,@"Buffer ABI index/duplicate differs");return nil;}NSUInteger i=[argument[@"index"]unsignedIntegerValue];NSUInteger size=i==0?16:i==1?4:[argument[@"data_size"]unsignedIntegerValue];
   if(extended){NSUInteger alignment=[argument[@"alignment"]unsignedIntegerValue];BOOL constant=i==[spec[@"constant_buffer_index"]unsignedIntegerValue];BOOL active=!argument[@"active"]||[argument[@"active"]boolValue];if(![argument[@"name"]isKindOfClass:[NSString class]]||![argument[@"name"]length]||!wholeNumber(argument[@"data_size"],1,512)||!wholeNumber(argument[@"alignment"],1,256)||(alignment&(alignment-1))||!wholeNumber(argument[@"data_type"],1,127)||!wholeNumber(argument[@"access"],0,2)||!wholeNumber(argument[@"minimum_bytes"],1,65536)||!wholeNumber(argument[@"per_invocation_bytes"],0,64)||(argument[@"active"]&&!wholeNumber(argument[@"active"],0,1))||constant&&(!active||[argument[@"alignment"]unsignedIntegerValue]!=256||[argument[@"data_type"]unsignedIntegerValue]!=1||[argument[@"access"]unsignedIntegerValue]!=0)){fail(error,@"Invalid schema2 buffer ABI/range specification");return nil;}if(active)maxBindings=MAX(maxBindings,i+1);}
   else if(![argument[@"name"]isKindOfClass:[NSString class]]||![argument[@"name"]length]||!wholeNumber(argument[@"data_size"],i==2?16:size,i==2?512:size)||!wholeNumber(argument[@"alignment"],i==0?16:i==1?4:256,i==0?16:i==1?4:256)||!wholeNumber(argument[@"data_type"],i==0?36:1,i==0?36:1)||!wholeNumber(argument[@"access"],i==2?0:1,i==2?0:1)){fail(error,@"Only the native uint4/atomic counter/constant ABI is registered");return nil;}bufferSpecs[@(i)]=argument;
  }
  if(extended&&!bufferSpecs[spec[@"constant_buffer_index"]]){fail(error,@"Constant buffer index is absent from native ABI");return nil;}
  if(memory&&[memory[@"parameter_word_offset"]unsignedIntegerValue]+4>[bufferSpecs[extended?spec[@"constant_buffer_index"]:@2][@"data_size"]unsignedIntegerValue]){fail(error,@"Threadgroup length word lies outside reflected constants");return nil;}
  id<MTLFunction>fn=[library newFunctionWithName:name];MTLComputePipelineReflection*reflection=nil;NSDictionary *CASProof=nil;id<MTLComputePipelineState>pipeline=nil;
  if(fn&&certificateSnapshots[name])pipeline=[factory newPipelineForDevice:device function:fn libraryData:bytes expectedSHA256:expected certificateData:certificateSnapshots[name] expectedCertificateSHA256:certificateHashes[name] options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:error evidence:&CASProof];
  else if(fn)pipeline=[device newComputePipelineStateWithFunction:fn options:MTLPipelineOptionArgumentInfo|MTLPipelineOptionBufferTypeInfo reflection:&reflection error:error];
  if(certificateSnapshots[name]&&(![CASProof[@"gate_accepted"]boolValue]||![CASProof[@"constructor_restored"]boolValue]||![CASProof[@"native_import"][@"contract_verified"]boolValue]||![CASProof[@"function"]isEqual:name]||![CASProof[@"library_SHA256"]isEqual:expected]||![CASProof[@"certificate_SHA256"]isEqual:certificateHashes[name]])){fail(error,@"Certified native CAS pipeline identity/import differs");return nil;}
  if(!pipeline||reflection.arguments.count!=[buffers count]+(memory?1:0)||pipeline.threadExecutionWidth!=32||![pipeline respondsToSelector:@selector(staticThreadgroupMemoryLength)]||pipeline.staticThreadgroupMemoryLength!=[spec[@"static_threadgroup_bytes"]unsignedIntegerValue]||pipeline.maxTotalThreadsPerThreadgroup<[spec[@"max_local"]unsignedIntegerValue]){fail(error,@"Native function/reflection/static memory/limits differ");return nil;}
  NSMutableArray*rows=[NSMutableArray new];unsigned bufferMask=0,memoryMask=0,expectedMask=0;for(NSNumber*index in bufferSpecs)expectedMask|=1u<<index.unsignedIntegerValue;
  for(MTLArgument*a in reflection.arguments){if(a.type==MTLArgumentTypeBuffer){NSDictionary*b=bufferSpecs[@(a.index)];BOOL active=!b[@"active"]||[b[@"active"]boolValue];if(!b||bufferMask&(1u<<a.index)||a.active!=active||![a.name isEqual:b[@"name"]]||a.bufferDataSize!=[b[@"data_size"]unsignedIntegerValue]||a.bufferAlignment!=[b[@"alignment"]unsignedIntegerValue]||a.bufferDataType!=[b[@"data_type"]unsignedIntegerValue]||a.access!=[b[@"access"]unsignedIntegerValue]){fail(error,@"Reflected native buffer ABI differs from manifest");return nil;}bufferMask|=1u<<a.index;
   }else if(a.type==MTLArgumentTypeThreadgroupMemory){if(!memory||memoryMask||a.index!=0||!a.active||![a.name isEqual:memory[@"name"]]||a.threadgroupMemoryAlignment!=4||a.threadgroupMemoryDataSize!=4){fail(error,@"Reflected dynamic shared pointer differs from manifest");return nil;}memoryMask=1;
   }else{fail(error,@"Texture/sampler/other native ABI not registered");return nil;}
   [rows addObject:@{@"name":a.name,@"type":@(a.type),@"index":@(a.index),@"access":@(a.access),@"active":@(a.active)}];
  }
  if(bufferMask!=expectedMask||memoryMask!=(memory?1:0)){fail(error,@"Reflected argument coverage differs");return nil;}
  NSMutableDictionary*profile=[@{@"native_registration_v1":@YES,@"registration_id":registration,@"function":name,@"library_SHA256":expected,@"manifest_SHA256":manifestSHA,@"library_owner":library,@"pipeline_owner":pipeline,@"static_threadgroup_bytes":spec[@"static_threadgroup_bytes"],@"max_local":spec[@"max_local"],@"expected_register_count":spec[@"qmd_register_count"],@"reflection":rows}mutableCopy];if(extended){NSMutableDictionary *activeSpecs=[bufferSpecs mutableCopy];for(NSNumber *index in bufferSpecs)if(bufferSpecs[index][@"active"]&&![bufferSpecs[index][@"active"]boolValue])[activeSpecs removeObjectForKey:index];profile[@"binding_layout_v2"]=@YES;profile[@"binding_specs"]=[activeSpecs copy];profile[@"constant_buffer_index"]=spec[@"constant_buffer_index"];profile[@"max_invocations"]=spec[@"max_invocations"];profile[@"multidimensional_grid"]=@([spec[@"allow_multidimensional"]boolValue]);}if(memory)profile[@"dynamic_threadgroup"]=[memory copy];if(CASProof){profile[@"native_CAS_certificate_SHA256"]=certificateHashes[name];profile[@"native_CAS_import"]=CASProof;}
  if(literalBank){profile[@"native_literal_bank_0"]=[literalBank copy];profile[@"function_owner"]=fn;}
  named[name]=pipeline;profiles[[NSValue valueWithPointer:(__bridge const void*)pipeline]]=profile;[registered addObject:@{@"function":name,@"static_threadgroup_bytes":spec[@"static_threadgroup_bytes"],@"max_local":spec[@"max_local"],@"expected_register_count":spec[@"qmd_register_count"],@"dynamic_threadgroup":memory?:@{},@"reflection":rows,@"native_CAS_import":CASProof?:@{},@"native_literal_bank_0":literalBank?:@{}}];
 }
 KPCPUICBScope*scope=[self installOnDevice:device queue:queue pipeline:named[functions[0][@"name"]] error:error];if(!scope)return nil;scope.profiles=profiles;scope.namedPipelines=named;scope.maxKernelBindings=extended?maxBindings:3;[scope.eventRows addObject:@{@"operation":@"registered_manifest_library",@"library_SHA256":expected,@"manifest_SHA256":manifestSHA,@"functions":registered,@"registration_is_GPU_qualification":@NO,@"library_loader":@"in_memory_dispatch_data",@"caller_data_copied":@YES,@"manifest_schema":manifest[@"schema"],@"max_kernel_bindings":@(scope.maxKernelBindings),@"identity_source":@"Functions/PSO from the same immutable bytes verified by SHA, reflected ABI and manifest"}];return scope;
}
- (NSDictionary*)profileForPipeline:(id<MTLComputePipelineState>)pipeline {return pipeline?_profiles[[NSValue valueWithPointer:(__bridge const void*)pipeline]]:nil;}
- (id<MTLComputePipelineState>)pipelineForFunction:(NSString*)name{return _restored?nil:_namedPipelines[name];}
- (NSArray*)events{return [_eventRows copy];}
- (BOOL)adaptComputeEncoder:(id<MTLComputeCommandEncoder>)e error:(NSError**)error {@synchronized(_factoryLock){
 if(error)*error=nil;
 if(_restored||!_pipeline||!e||e.device!=_device)return fail(error,@"Encoder scope mismatch");
 Ivar cbVar=class_getInstanceVariable(object_getClass(e),"_commandBuffer");if(!cbVar||ivar_getOffset(cbVar)!=32)return fail(error,@"Encoder layout changed");id<MTLCommandBuffer>cb=object_getIvar(e,cbVar);if(cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued)return fail(error,@"Uncommitted recording queue required");
 KPScopeLink*existing=objc_getAssociatedObject(e,&contextKey);
 if(existing){if(existing.scope==self&&!existing.computeEncodingEnded&&existing.originalComputeClass==class_getSuperclass(object_getClass(e)))return YES;return fail(error,@"Encoder belongs to another scope, ended, or changed class");}
 Class original=object_getClass(e),dynamic=nil;{std::lock_guard<std::mutex>lock(installMutex);dynamic=scopedClass(encoderClasses,original,@"KPICBEncoder_",@selector(executeCommandsInBuffer:withRange:),(IMP)executeICB,error);if(dynamic&&!installNativeThreadLimitChecks(dynamic,original))dynamic=nil;}if(!dynamic)return fail(error,@"Native compute dispatch methods differ");
 NSMutableIndexSet*expired=[NSMutableIndexSet new];for(NSUInteger i=0;i<_adapted.count;i++)if(!((KPAdaptedEncoder*)_adapted[i]).encoder)[expired addIndex:i];_releasedEncoderCount+=expired.count;[_adapted removeObjectsAtIndexes:expired];linkScope(e,self);((KPScopeLink*)objc_getAssociatedObject(e,&contextKey)).originalComputeClass=original;object_setClass(e,dynamic);KPAdaptedEncoder*record=[KPAdaptedEncoder new];record.encoder=e;record.originalClass=original;[_adapted addObject:record];return YES;
}}

- (BOOL)prepareResidentComputeCommands:(id<MTLIndirectCommandBuffer>)buffer range:(NSRange)range error:(NSError**)error {
 if(_restored||![buffer isKindOfClass:KPComputeICB.class]||[buffer isKindOfClass:KPRenderICB.class]||((KPComputeICB*)buffer).scope!=self||range.location>buffer.size||range.length>buffer.size-range.location)return fail(error,@"Resident preparation context/range differs");
 KPComputeICB*icb=(KPComputeICB*)buffer;NSMutableArray*records=[NSMutableArray array];
 for(NSUInteger i=range.location;i<NSMaxRange(range);i++){KPComputeICBCommand*c=icb.commands[i];NSString*reason=residentBindingError(c,self);if(reason)return fail(error,reason);if(c.residentOwners.count)return fail(error,@"Preparing an already copied resident slot is unsupported");}
 for(NSUInteger i=range.location;i<NSMaxRange(range);i++){
  KPComputeICBCommand*c=icb.commands[i];
  @try{if(!c.record)c.record=[self materialize:c];}@catch(NSException*e){return fail(error,e.reason);}
  if(!c.record.residentDescriptorReady)[records addObject:c.record];
 }
 if(records.count){id<MTLCommandBuffer>cb=[_queue commandBuffer];for(KPRecordedNativeCompute*r in records){NSDictionary*proof=nil;if(![r initializeResidentDescriptorInCommandBuffer:cb evidence:&proof error:error])return NO;[_eventRows addObject:proof];}if(!complete(cb))return fail(error,@"Resident descriptor initialization did not complete");}
 [_eventRows addObject:@{@"operation":@"prepare_resident_compute_commands",@"location":@(range.location),@"length":@(range.length),@"user_kernel_dispatches":@0,@"GPU_initializers":@(records.count)}];return YES;
}
- (BOOL)enableGPUCommandSelectionWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
 NSString*pin=@"b6d3f29fc4f85dd020f96fff3fc5f2586548aad483ea2649172b56545a9e581c";
 NSData*snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
 if(_restored||![_device.name isEqual:@"NVIDIA GeForce GTX 880M"]||![expected isEqual:pin]||!snapshot||![hash(snapshot)isEqual:pin])return fail(error,@"GPU command selector identity or scope differs");
 if(_GPUSelectionLibrary)return YES;
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return NO;
 id<MTLComputePipelineState>producer=[_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"produce_command_choices"]error:error],selector=[_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"select_command_from_gpu"]error:error];
 if(!producer||!selector||producer.threadExecutionWidth!=32||selector.threadExecutionWidth!=32||producer.maxTotalThreadsPerThreadgroup<32||selector.maxTotalThreadsPerThreadgroup<64)return fail(error,@"GPU command selector pipeline limits differ");
 _GPUSelectionLibrary=library;_GPUChoiceProducer=producer;_GPUCommandSelector=selector;
 [_eventRows addObject:@{@"operation":@"enable_GPU_command_selection",@"library_SHA256":pin,@"caller_data_copied":@YES,@"arbitrary_selector_library_allowed":@NO}];return YES;
}
#include "KeplerCommandIRScope.inc"
#include "KeplerCommandIRv2Scope.inc"
#include "KeplerCommandIRFunctionScope.inc"
#include "KeplerCommandIRProducerScope.inc"
#include "KeplerCommandIRLibraryScope.inc"
- (BOOL)enableGPUCommandBindingsWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
 NSString*pin=@"ce99cdc66f55f4ce7069b9518ed1f074feea2bee6daded2d320098e29b43f290";
 NSData*snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
 if(_restored||!_GPUGridSelector||![expected isEqual:pin]||!snapshot||![hash(snapshot)isEqual:pin])return fail(error,@"GPU command bindings identity or geometry scope differs");
 if(_GPUBindingLibrary)return YES;
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return NO;
 id<MTLComputePipelineState>selector=[_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"generate_bound_command_from_gpu"]error:error];
 if(!selector||selector.threadExecutionWidth!=32||selector.maxTotalThreadsPerThreadgroup<64)return fail(error,@"GPU command bindings pipeline limits differ");
 _GPUBindingLibrary=library;_GPUBindingSelector=selector;
 [_eventRows addObject:@{@"operation":@"enable_GPU_command_bindings",@"library_SHA256":pin,@"caller_data_copied":@YES,@"arbitrary_selector_library_allowed":@NO}];return YES;
}
- (KPGPUCommandSelection*)newGPUCommandBindingsFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources input:(id<MTLBuffer>)input inputOffset:(NSUInteger)offset nonce:(uint32_t)nonce error:(NSError**)error {
 return [self newGPUCommandBindingPlanFromBuffer:source sourceRange:range destination:destination destinationRange:targetRange resources:resources input:input inputOffset:offset nonce:nonce IR:NO error:error];
}
- (KPGPUCommandSelection*)newGPUCommandBindingPlanFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange resources:(NSArray<NSDictionary*>*)resources input:(id<MTLBuffer>)input inputOffset:(NSUInteger)offset nonce:(uint32_t)nonce IR:(BOOL)IR error:(NSError**)error {
 if(_restored||!_GPUBindingSelector||![source isKindOfClass:KPComputeICB.class]||![destination isKindOfClass:KPComputeICB.class]||[source isKindOfClass:KPRenderICB.class]||[destination isKindOfClass:KPRenderICB.class]||((KPComputeICB*)source).scope!=self||((KPComputeICB*)destination).scope!=self||!range.length||range.length>8||range.location>source.size||range.length>source.size-range.location||!targetRange.length||targetRange.length>8||targetRange.location>destination.size||targetRange.length>destination.size-targetRange.location||!resources.count||resources.count>4||!input){fail(error,@"GPU bindings ranges/catalogue/scope differ");return nil;}
 NSUInteger maximum=0;NSMutableArray*blocked=[NSMutableArray arrayWithObject:input];
 for(unsigned pass=0;pass<2;pass++){KPComputeICB*icb=pass?(KPComputeICB*)destination:(KPComputeICB*)source;NSRange r=pass?targetRange:range;
  for(NSUInteger i=r.location;i<NSMaxRange(r);i++){KPComputeICBCommand*c=icb.commands[i];if(!c.hasDispatch||!c.record.residentDescriptorReady){fail(error,@"GPU bindings require original prepared commands");return nil;}if(!pass)maximum=MAX(maximum,c.groups.width*c.local.width);[blocked addObjectsFromArray:@[c.record.constants,c.record.descriptor]];for(NSDictionary*b in c.bindings.allValues)[blocked addObject:b[@"buffer"]];}
 }
 if(!maximum||maximum>4096){fail(error,@"GPU binding maximum invocation bound differs");return nil;}
 NSMutableArray*owners=[NSMutableArray new];NSMutableData*addresses=[NSMutableData dataWithLength:resources.count*16];
 for(NSUInteger i=0;i<resources.count;i++){NSDictionary*entry=resources[i];if(![entry isKindOfClass:NSDictionary.class]||entry.count!=4||![entry[@"outputOffset"]isKindOfClass:NSNumber.class]||![entry[@"counterOffset"]isKindOfClass:NSNumber.class]){fail(error,@"GPU binding catalogue entry shape differs");return nil;}
  id<MTLBuffer>out=entry[@"output"],counter=entry[@"counter"];NSUInteger oo=[entry[@"outputOffset"]unsignedIntegerValue],co=[entry[@"counterOffset"]unsignedIntegerValue];
  if(!out||!counter||![out conformsToProtocol:@protocol(MTLBuffer)]||![counter conformsToProtocol:@protocol(MTLBuffer)]||out.device!=_device||counter.device!=_device||out.storageMode!=MTLStorageModePrivate||counter.storageMode!=MTLStorageModePrivate||oo%16||co%4||oo>out.length||maximum*16>out.length-oo||co>counter.length||counter.length-co<4){fail(error,@"GPU binding buffers/offsets/extents differ");return nil;}
  for(id<MTLBuffer>buffer in @[out,counter]){uint64_t a=buffer.gpuAddress;if(!a||a>>40||buffer.length>((uint64_t(1)<<40)-a)){fail(error,@"GPU resource address span differs");return nil;}
   for(id<MTLBuffer>other in [blocked arrayByAddingObjectsFromArray:owners]){uint64_t b=other.gpuAddress;if(buffer==other||(a<b+other.length&&b<a+buffer.length)){fail(error,@"GPU resource catalogue aliases a command/input/other resource");return nil;}}
   [owners addObject:buffer];
  }
  uint64_t a=out.gpuAddress+oo,b=counter.gpuAddress+co;uint32_t row[4]={(uint32_t)a,(uint32_t)(a>>32),(uint32_t)b,(uint32_t)(b>>32)};memcpy((char*)addresses.mutableBytes+i*16,row,16);
 }
 KPGPUCommandSelection*plan=IR?[self newGPUCommandSelectionFromBuffer:source sourceRange:range destination:destination destinationRange:targetRange input:input inputOffset:offset nonce:nonce error:error]:[self newGPUCommandGeometryFromBuffer:source sourceRange:range destination:destination destinationRange:targetRange input:input inputOffset:offset nonce:nonce error:error];if(!plan)return nil;
 plan.resourceOwners=[owners copy];plan.resourceAddresses=[_device newBufferWithBytes:addresses.bytes length:addresses.length options:MTLResourceStorageModeShared];plan.constantTemplates=[_device newBufferWithLength:range.length*65536 options:MTLResourceStorageModePrivate];plan.generatedGeometry=[_device newBufferWithLength:128+targetRange.length*32 options:MTLResourceStorageModePrivate];
 if(!plan.resourceAddresses||!plan.constantTemplates||!plan.generatedGeometry){fail(error,@"GPU binding preparation allocation failed");return nil;}
 NSMutableArray*configs=[NSMutableArray new];for(NSUInteger i=0;i<targetRange.length;i++){id<MTLBuffer>c=[_device newBufferWithLength:256 options:MTLResourceStorageModeShared];if(!c){fail(error,@"GPU binding config allocation failed");return nil;}memset(c.contents,0,256);memcpy(c.contents,plan.selectorConfigs[i].contents,16);uint64_t a=plan.targetRecords[i].constants.gpuAddress;uint32_t words[4]={(uint32_t)resources.count,(uint32_t)a,(uint32_t)(a>>32),0};memcpy((char*)c.contents+16,words,16);[configs addObject:c];}plan.selectorConfigs=[configs copy];
 id<MTLCommandBuffer>cb=[_queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];if(!b){fail(error,@"GPU binding initializer missing");return nil;}
 for(NSUInteger i=0;i<range.length;i++){KPComputeICBCommand*c=((KPComputeICB*)source).commands[range.location+i];[b copyFromBuffer:c.record.constants sourceOffset:0 toBuffer:plan.constantTemplates destinationOffset:i*65536 size:65536];}
 [b fillBuffer:plan.generatedGeometry range:NSMakeRange(0,plan.generatedGeometry.length)value:0xa5];[b fillBuffer:plan.generatedGeometry range:NSMakeRange(64,targetRange.length*32)value:0];[b endEncoding];if(!complete(cb)){fail(error,@"GPU binding initializer failed");return nil;}plan.bindingGeneration=YES;if(IR)plan.gridPrefix=YES;
 [_eventRows addObject:@{@"operation":@"prepare_GPU_command_bindings",@"resource_entries":@(resources.count),@"extra_GPU_resource_owners":@(owners.count),@"constant_template_bytes":@(range.length*65536),@"CPU_selected_resource_supplied":@NO,@"CPU_descriptor_read":@NO,@"general_GPU_ICB_encoding":@NO}];return plan;
}
- (BOOL)enableGPUCommandGeometryWithLibraryData:(NSData*)data expectedSHA256:(NSString*)expected error:(NSError**)error {
 NSString*pin=@"f6cc04a4c2555a2555dc06a2f02687ffe5a63fb5304619b1d9662ec1f0176441";
 NSData*snapshot=data?[NSData dataWithBytes:data.bytes length:data.length]:nil;
 if(_restored||!_GPUCommandSelector||![expected isEqual:pin]||!snapshot||![hash(snapshot)isEqual:pin])return fail(error,@"GPU command geometry identity or selector scope differs");
 if(_GPUGridLibrary)return YES;
 id<MTLLibrary>library=libraryFromSnapshot(_device,snapshot,error);if(!library)return NO;
 id<MTLComputePipelineState>selector=[_device newComputePipelineStateWithFunction:[library newFunctionWithName:@"generate_grid_prefix_from_gpu"]error:error];
 if(!selector||selector.threadExecutionWidth!=32||selector.maxTotalThreadsPerThreadgroup<64)return fail(error,@"GPU command geometry pipeline limits differ");
 _GPUGridLibrary=library;_GPUGridSelector=selector;
 [_eventRows addObject:@{@"operation":@"enable_GPU_command_geometry",@"library_SHA256":pin,@"caller_data_copied":@YES,@"arbitrary_selector_library_allowed":@NO}];return YES;
}
- (KPGPUCommandSelection*)newGPUCommandGeometryFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange input:(id<MTLBuffer>)input inputOffset:(NSUInteger)offset nonce:(uint32_t)nonce error:(NSError**)error {
 if(!_GPUGridSelector||![source isKindOfClass:KPComputeICB.class]||![destination isKindOfClass:KPComputeICB.class]||((KPComputeICB*)source).scope!=self||((KPComputeICB*)destination).scope!=self||!range.length||range.length>8||range.location>source.size||range.length>source.size-range.location||!targetRange.length||targetRange.length>8||range.length+targetRange.length>16||targetRange.location>destination.size||targetRange.length>destination.size-targetRange.location){fail(error,@"GPU geometry scope/ranges differ");return nil;}
 for(unsigned pass=0;pass<2;pass++){KPComputeICB*icb=pass?(KPComputeICB*)destination:(KPComputeICB*)source;NSRange r=pass?targetRange:range;
  for(NSUInteger i=r.location;i<NSMaxRange(r);i++){KPComputeICBCommand*c=icb.commands[i];NSDictionary*p=[self profileForPipeline:c.pipeline];
   if(![p[@"library_SHA256"]isEqual:@"b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd"]||![@[@"shared_mix_s128",@"shared_mix_s1024",@"shared_mix_s4096"]containsObject:p[@"function"]]||!c.hasDispatch||!c.groups.width||c.groups.width>7||c.groups.height!=1||c.groups.depth!=1||c.local.height!=1||c.local.depth!=1){fail(error,@"GPU geometry requires certified prefix-safe 1D shared kernels with 1..7 groups");return nil;}
  }
 }
 KPGPUCommandSelection*plan=[self newGPUCommandSelectionFromBuffer:source sourceRange:range destination:destination destinationRange:targetRange input:input inputOffset:offset nonce:nonce error:error];if(!plan)return nil;
 plan.geometryLimits=[_device newBufferWithLength:range.length*16 options:MTLResourceStorageModeShared];plan.generatedGeometry=[_device newBufferWithLength:128+targetRange.length*16 options:MTLResourceStorageModePrivate];
 if(!plan.geometryLimits||!plan.generatedGeometry){fail(error,@"GPU geometry allocation failed");return nil;}memset(plan.geometryLimits.contents,0,plan.geometryLimits.length);
 for(NSUInteger i=0;i<range.length;i++){KPComputeICBCommand*c=((KPComputeICB*)source).commands[range.location+i];uint32_t v[4]={(uint32_t)c.groups.width,(uint32_t)c.local.width,0,0};memcpy((char*)plan.geometryLimits.contents+i*16,v,16);}
 id<MTLCommandBuffer>cb=[_queue commandBuffer];id<MTLBlitCommandEncoder>b=[cb blitCommandEncoder];if(!b){fail(error,@"GPU geometry initializer missing");return nil;}
 [b fillBuffer:plan.generatedGeometry range:NSMakeRange(0,plan.generatedGeometry.length)value:0xa5];[b fillBuffer:plan.generatedGeometry range:NSMakeRange(64,targetRange.length*16)value:0];[b endEncoding];if(!complete(cb)){fail(error,@"GPU geometry initializer failed");return nil;}plan.gridPrefix=YES;
 [_eventRows addObject:@{@"operation":@"prepare_GPU_command_geometry",@"prefix_limit":@7,@"CPU_resolved_grid_supplied":@NO,@"QMD_modified_words":@[@12],@"local_size_modified":@NO,@"general_GPU_ICB_encoding":@NO}];return plan;
}
- (KPGPUCommandSelection*)newGPUCommandSelectionFromBuffer:(id<MTLIndirectCommandBuffer>)source sourceRange:(NSRange)range destination:(id<MTLIndirectCommandBuffer>)destination destinationRange:(NSRange)targetRange input:(id<MTLBuffer>)input inputOffset:(NSUInteger)offset nonce:(uint32_t)nonce error:(NSError**)error {
 if(_restored||!_GPUCommandSelector||![source isKindOfClass:KPComputeICB.class]||![destination isKindOfClass:KPComputeICB.class]||[source isKindOfClass:KPRenderICB.class]||[destination isKindOfClass:KPRenderICB.class]||((KPComputeICB*)source).scope!=self||((KPComputeICB*)destination).scope!=self||!range.length||range.length>8||!targetRange.length||targetRange.length>8||range.length+targetRange.length>16||range.location>source.size||range.length>source.size-range.location||targetRange.location>destination.size||targetRange.length>destination.size-targetRange.location||(source==destination&&NSIntersectionRange(range,targetRange).length)||!input||input.device!=_device||input.storageMode!=MTLStorageModePrivate||offset%16||offset>input.length||input.length-offset<targetRange.length*128){fail(error,@"GPU command selection ranges/input/scope are outside the contract");return nil;}
 KPComputeICB*s=source,*d=destination;NSMutableArray*candidates=[NSMutableArray new],*targets=[NSMutableArray new],*commands=[NSMutableArray new],*owners=[NSMutableArray new];NSDictionary*domain=nil;
 for(unsigned pass=0;pass<2;pass++){NSRange r=pass?targetRange:range;KPComputeICB*icb=pass?d:s;
  for(NSUInteger i=r.location;i<NSMaxRange(r);i++){
   KPComputeICBCommand*c=icb.commands[i];NSString*reason=residentBindingError(c,self);if(reason||!c.record.residentDescriptorReady||c.residentOwners.count){fail(error,reason?:@"GPU selector requires original prepared command templates");return nil;}
   NSDictionary*p=[self profileForPipeline:c.pipeline];if(domain&&!sameResidentRegistration(domain,p)){fail(error,@"GPU selector template registration differs");return nil;}domain=p;
   if(![c.record validateResidentThreadgroupMemory:error])return nil;
   [(pass?targets:candidates)addObject:c.record];if(pass)[commands addObject:c];if(![owners containsObject:c.record])[owners addObject:c.record];
  }
 }
 KPGPUCommandSelection*plan=[KPGPUCommandSelection new];plan.scope=self;plan.targetICB=d;plan.targetCommands=[commands copy];plan.targetRecords=[targets copy];plan.owners=[owners copy];plan.input=input;plan.inputOffset=offset;plan.candidateCount=range.length;plan.eventRows=[NSMutableArray new];
 plan.templates=[_device newBufferWithLength:range.length*256 options:MTLResourceStorageModePrivate];plan.choices=[_device newBufferWithLength:128+targetRange.length*16 options:MTLResourceStorageModePrivate];plan.invocationCounts=[_device newBufferWithLength:128+targetRange.length*8 options:MTLResourceStorageModePrivate];
 uint32_t values[4]={nonce,(uint32_t)range.length,0,0};plan.producerConfig=[_device newBufferWithLength:256 options:MTLResourceStorageModeShared];if(!plan.templates||!plan.choices||!plan.invocationCounts||!plan.producerConfig){fail(error,@"GPU command selection resources could not be allocated");return nil;}memset(plan.producerConfig.contents,0,256);memcpy(plan.producerConfig.contents,values,16);
 NSMutableArray*configs=[NSMutableArray new];for(NSUInteger i=0;i<targetRange.length;i++){values[2]=(uint32_t)i;values[3]=(uint32_t)(targetRange.location+i);id<MTLBuffer>config=[_device newBufferWithLength:256 options:MTLResourceStorageModeShared];if(!config){fail(error,@"GPU selector configuration allocation failed");return nil;}memset(config.contents,0,256);memcpy(config.contents,values,16);[configs addObject:config];}plan.selectorConfigs=[configs copy];
 id<MTLCommandBuffer>init=[_queue commandBuffer];id<MTLBlitCommandEncoder>b=[init blitCommandEncoder];if(!b){fail(error,@"GPU command selection initializer failed");return nil;}
 for(NSUInteger i=0;i<candidates.count;i++)[b copyFromBuffer:((KPRecordedNativeCompute*)candidates[i]).descriptor sourceOffset:0 toBuffer:plan.templates destinationOffset:i*256 size:256];
 [b fillBuffer:plan.choices range:NSMakeRange(0,plan.choices.length)value:0xa5];[b fillBuffer:plan.choices range:NSMakeRange(64,targetRange.length*16)value:0];[b fillBuffer:plan.invocationCounts range:NSMakeRange(0,plan.invocationCounts.length)value:0xa5];[b fillBuffer:plan.invocationCounts range:NSMakeRange(64,targetRange.length*8)value:0];[b endEncoding];if(!complete(init)){fail(error,@"GPU selector template preparation did not complete");return nil;}
 [_eventRows addObject:@{@"operation":@"prepare_GPU_command_selection",@"candidate_count":@(range.length),@"destination_location":@(targetRange.location),@"destination_count":@(targetRange.length),@"template_bytes":@(range.length*256),@"CPU_descriptor_read":@NO,@"CPU_descriptor_upload":@NO,@"user_kernel_dispatches":@0,@"GPU_initialization_wait":@YES}];return plan;
}
- (BOOL)adaptBlitEncoder:(id<MTLBlitCommandEncoder>)e error:(NSError**)error {
 if(_restored||e.device!=_device||objc_getAssociatedObject(e,&contextKey))return fail(error,@"Blit scope mismatch");
 Ivar v=class_getInstanceVariable(object_getClass(e),"_commandBuffer");if(!v||ivar_getOffset(v)!=32)return fail(error,@"Blit command-buffer ABI differs");id<MTLCommandBuffer>cb=object_getIvar(e,v);
 if(!cb||cb.commandQueue!=_queue||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return fail(error,@"Blit copy requires retained uncommitted CB from scope queue");
 Class original=object_getClass(e),dynamic=nil;{
  std::lock_guard<std::mutex>lock(installMutex);uintptr_t key=(uintptr_t)(__bridge const void*)original;auto found=blitEncoderClasses.find(key);
  if(found!=blitEncoderClasses.end())dynamic=found->second;
  else{SEL selector=@selector(copyIndirectCommandBuffer:sourceRange:destination:destinationIndex:);Method method=class_getInstanceMethod(original,selector);const char*types=method?method_getTypeEncoding(method):protocol_getMethodDescription(@protocol(MTLBlitCommandEncoder),selector,YES,YES).types;
   if(!types)return fail(error,@"Public blit-copy selector ABI unavailable");NSString*name=[@"KPICBBlit_" stringByAppendingString:[[NSUUID UUID].UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@"_"]];dynamic=objc_allocateClassPair(original,name.UTF8String,0);
   if(!dynamic||!class_addMethod(dynamic,selector,(IMP)copyResidentICB,types))return fail(error,@"Cannot create scoped GPU-copy selector");objc_registerClassPair(dynamic);if(class_getInstanceSize(dynamic)!=class_getInstanceSize(original))return fail(error,@"Scoped blit instance layout differs");blitEncoderClasses[key]=dynamic;
  }
 }
 linkScope(e,self);object_setClass(e,dynamic);KPAdaptedEncoder*r=[KPAdaptedEncoder new];r.encoder=e;r.originalClass=original;[_adapted addObject:r];return YES;
}
- (KPRecordedNativeCompute*)materialize:(KPComputeICBCommand*)command {
 NSDictionary*profile=[self profileForPipeline:command.pipeline];BOOL extended=[profile[@"binding_layout_v2"]boolValue];NSNumber*constantIndex=extended?profile[@"constant_buffer_index"]:@2;
 id<MTLBuffer>out=command.bindings[@0][@"buffer"],counter=command.bindings[@1][@"buffer"],parameters=command.bindings[constantIndex][@"buffer"];
 if(!extended&&([command.bindings[@0][@"offset"]unsignedLongLongValue]!=64||[command.bindings[@1][@"offset"]unsignedLongLongValue]!=64||[command.bindings[@2][@"offset"]unsignedLongLongValue]!=0||out.length!=10368||counter.length!=132||parameters.length<512))reject(@"Binding profile is not qualified");
 id<MTLBuffer>nativeCB=queueBuffer(_queue,32),nativeQMD=queueBuffer(_queue,16);if(nativeCB.length!=393216||nativeQMD.length!=4096)reject(@"Native queue backing layout changed");
 NSUInteger maxLocal=[profile[@"max_local"]unsignedIntegerValue];if(!maxLocal)maxLocal=[profile[@"static_threadgroup_bytes"]unsignedIntegerValue]?128:1024;if(!profile||!volume(command.local,maxLocal))reject(@"Pipeline/local memory profile is not qualified");
 if(extended){NSMutableDictionary*instance=[profile mutableCopy];instance[@"binding_state_v2"]=[command.bindings copy];instance[@"groups_shape"]=@[@(command.groups.width),@(command.groups.height),@(command.groups.depth)];instance[@"local_shape"]=@[@(command.local.width),@(command.local.height),@(command.local.depth)];profile=instance;}
 NSDictionary*memory=profile[@"dynamic_threadgroup"];NSUInteger dynamicLength=memory?[command.threadgroupLengths[memory[@"index"]]unsignedIntegerValue]:0;
 if(memory){NSUInteger offset=[memory[@"parameter_word_offset"]unsignedIntegerValue],base=[command.bindings[constantIndex][@"offset"]unsignedIntegerValue];uint32_t words=0;if(parameters.storageMode==MTLStorageModePrivate||!parameters.contents||base>parameters.length||offset>parameters.length-base||parameters.length-base-offset<4)reject(@"Dynamic shared bound must be CPU-readable");memcpy(&words,(const char*)parameters.contents+base+offset,4);if(dynamicLength<[memory[@"min_bytes"]unsignedIntegerValue]||dynamicLength>[memory[@"max_bytes"]unsignedIntegerValue]||dynamicLength%16||uint64_t(words)*4!=dynamicLength)reject(@"Dynamic shared allocation does not match registered parameter bound");}
 if([profile[@"native_registration_v1"]boolValue]){NSMutableDictionary*instance=[profile mutableCopy];instance[@"dynamic_threadgroup_length"]=@(dynamicLength);profile=instance;}

 id<MTLCommandBuffer>c=[_queue commandBuffer];id<MTLComputeCommandEncoder>e=[c computeCommandEncoder];[e setComputePipelineState:command.pipeline];if(extended){for(NSNumber*index in [command.bindings.allKeys sortedArrayUsingSelector:@selector(compare:)]){NSDictionary*b=command.bindings[index];[e setBuffer:b[@"buffer"] offset:[b[@"offset"]unsignedIntegerValue] atIndex:index.unsignedIntegerValue];}}else{[e setBuffer:out offset:64 atIndex:0];[e setBuffer:counter offset:64 atIndex:1];[e setBuffer:parameters offset:0 atIndex:2];}if(memory)[e setThreadgroupMemoryLength:dynamicLength atIndex:0];Cursor before=cursor(e);[e dispatchThreadgroups:command.groups threadsPerThreadgroup:command.local];Cursor after=cursor(e);NSUInteger expectedBytes=memory?496:464;NSData*commands=before.push==after.push&&after.current>=before.current&&after.current-before.current==expectedBytes&&after.current<=before.end?readMemory(before.current,expectedBytes):nil;NSUInteger launch=expectedBytes-16;if(!commands||word(commands,launch)!=0x00000003200120afULL){[e endEncoding];reject(@"Native preparation profile changed");}uint32_t header=0,value=0;memcpy(&header,(const char*)commands.bytes+launch,4);header=(header&~0x1fffu)|(0x100/4);memcpy((void*)(before.current+launch),&header,4);memcpy((void*)(before.current+launch+4),&value,4);[e endEncoding];if(!complete(c))reject(@"Native NOP preparation failed");
 id<MTLBuffer>host=[_device newBufferWithLength:65536 options:MTLResourceStorageModeManaged];id<MTLCommandBuffer>read=[_queue commandBuffer];id<MTLBlitCommandEncoder>b=[read blitCommandEncoder];[b copyFromBuffer:nativeCB sourceOffset:0 toBuffer:host destinationOffset:0 size:65536];[b synchronizeResource:host];[b endEncoding];if(!complete(read))reject(@"Native state readback failed");NSData*snapshot=[NSData dataWithBytes:host.contents length:65536];NSError*error=nil;NSDictionary*registered=([profile[@"native_registration_v1"]boolValue]||[profile[@"library_SHA256"]isEqual:@"913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd"])?profile:nil;KPRecordedNativeCompute*r=[KPRecordedNativeCompute recordedCommands:commands queue:_queue pipeline:command.pipeline output:out counter:counter parameters:parameters nativeConstants:nativeCB nativeDescriptor:nativeQMD constantSnapshot:snapshot groups:command.groups.width local:command.local.width profile:registered error:&error];if(!r)reject(error.localizedDescription);
 id<MTLCommandBuffer>upload=[_queue commandBuffer];b=[upload blitCommandEncoder];[b copyFromBuffer:nativeCB sourceOffset:0 toBuffer:r.constants destinationOffset:0 size:65536];[b endEncoding];if(!complete(upload))reject(@"Dedicated constant copy failed");[_eventRows addObject:@{@"operation":@"materialize_CPU_command",@"user_kernel_invocations":@0,@"requires_GPU_NOP_and_blit_preparation":@YES,@"commands_SHA256":hash(commands),@"snapshot_SHA256":hash(snapshot),@"command_bytes":@(commands.length),@"dynamic_threadgroup_length":@(dynamicLength),@"relocation":r.relocationEvidence}];return r;
}
#include "KeplerIndirectRenderScope.inc"
#include "KeplerRenderStateCatalogueScope.inc"
#include "KeplerRenderCommandArgumentsScope.inc"
- (void)restore{@synchronized(_factoryLock){if(_restored)return;_restored=YES;NSUInteger liveFunctions=0;for(KPAdaptedFunction*r in _adaptedFunctions){id f=r.function;if(f){liveFunctions++;object_setClass(f,r.originalClass);objc_setAssociatedObject(f,&IRFunctionKey,nil,OBJC_ASSOCIATION_ASSIGN);}}[_adaptedFunctions removeAllObjects];[_functionLibraries removeAllObjects];restoreIRLibraries(self);if(liveFunctions)[_eventRows addObject:@{@"operation":@"restore_IRv2_functions",@"live_functions_restored":@(liveFunctions),@"cached_function_classes":@(functionClasses.size())}];NSUInteger live=0,expired=_releasedEncoderCount;for(KPAdaptedEncoder*r in _adapted){id e=r.encoder;if(!e){expired++;continue;}live++;object_setClass(e,r.originalClass);objc_setAssociatedObject(e,&contextKey,nil,OBJC_ASSOCIATION_ASSIGN);}[_adapted removeAllObjects];restoreAutomaticComputeFactories(self);object_setClass(_device,_originalDeviceClass);objc_setAssociatedObject(_device,&contextKey,nil,OBJC_ASSOCIATION_ASSIGN);_restored=YES;[_eventRows addObject:@{@"operation":@"scope_restore",@"device_class_restored":@(object_getClass(_device)==_originalDeviceClass),@"live_encoder_classes_restored":@(live),@"already_released_encoders":@(expired),@"cached_device_classes":@(deviceClasses.size()),@"cached_encoder_classes":@(encoderClasses.size()),@"system_modified":@NO}];}}
- (void)dealloc{[self restore];}
@end

BOOL KPCopyCPUICBCommands(id<MTLIndirectCommandBuffer>source,NSRange range,id<MTLIndirectCommandBuffer>destination,NSUInteger index,NSError**error){
 if(![source isKindOfClass:[KPComputeICB class]]||![destination isKindOfClass:[KPComputeICB class]]||[source isKindOfClass:[KPRenderICB class]]!=[destination isKindOfClass:[KPRenderICB class]]||((KPComputeICB*)source).scope!=((KPComputeICB*)destination).scope||range.location>source.size||range.length>source.size-range.location||index>destination.size||range.length>destination.size-index)return fail(error,@"CPU ICB copy type/context/range mismatch");
 BOOL render=[source isKindOfClass:[KPRenderICB class]];KPComputeICB*s=(KPComputeICB*)source,*d=(KPComputeICB*)destination;if(!render)for(NSUInteger k=0;k<range.length;k++)if(((KPComputeICBCommand*)s.commands[range.location+k]).reusableContext||((KPComputeICBCommand*)d.commands[index+k]).reusableContext)return fail(error,@"CPU copying reusable command state is not qualified");if(!render)for(NSUInteger i=range.location;i<NSMaxRange(range);i++)if(((KPComputeICBCommand*)s.commands[i]).GPUGenerated)return fail(error,@"GPU-selected command cannot be copied as a CPU snapshot");
 if(render&&((((KPRenderICB*)s).allowedTypes&~((KPRenderICB*)d).allowedTypes)||((KPRenderICB*)s).maxVertexBuffers>((KPRenderICB*)d).maxVertexBuffers||((KPRenderICB*)s).maxFragmentBuffers>((KPRenderICB*)d).maxFragmentBuffers))return fail(error,@"Destination render descriptor cannot hold source types");
 NSMutableArray*snapshots=[NSMutableArray new];for(NSUInteger i=0;i<range.length;i++){id c=render?[KPRenderICBCommand new]:[KPComputeICBCommand new];[c copyStateFrom:s.commands[range.location+i]];[snapshots addObject:c];}for(NSUInteger i=0;i<range.length;i++)[d.commands[index+i]copyStateFrom:snapshots[i]];
 [s.scope.eventRows addObject:@{@"operation":@"CPU_snapshot_copy",@"source_location":@(range.location),@"length":@(range.length),@"destination_index":@(index),@"GPU_timeline_copy":@NO}];return YES;
}
