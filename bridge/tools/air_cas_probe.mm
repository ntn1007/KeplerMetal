// Execute identical single-CAS AIR kernels via native Metal or a local NAK
// import. No driver files, OCLP settings or kernel interfaces are modified.
#import "KeplerProgramImport.h"
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>
#ifdef QUALIFIED_NATIVE_CAS_IMPORT
#include <CommonCrypto/CommonDigest.h>
static NSString *dataSHA(NSData *data) {
    if(!data||data.length>UINT32_MAX)return nil;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
    NSMutableString *hex=[NSMutableString string];for(unsigned char b:digest)[hex appendFormat:@"%02x",b];return hex;
}
static NSString *fileSHA(NSString *path) {
    return dataSHA(path?[NSData dataWithContentsOfFile:path]:nil);
}
static NSDictionary *semanticPolicy(NSDictionary *plan,unsigned component) {
    NSData *bytes=[NSData dataWithContentsOfFile:plan[@"policy"]?:@""];
    NSDictionary *policy=bytes?[NSJSONSerialization JSONObjectWithData:bytes options:0 error:nil]:nil;
    unsigned version=1;
#ifdef COMPILED_METALLIB_CAS_IMPORT
    version=2;
#endif
    bool valid=[policy[@"policy_version"]unsignedIntValue]==version&&[policy[@"qualified"]boolValue]&&
        [policy[@"AIR"][@"qualified"]boolValue]&&[policy[@"SASS"][@"qualified"]boolValue]&&
        [policy[@"SASS_only_repair_forbidden"]boolValue]&&
        [policy[@"AIR"][@"expected_output_component"]unsignedIntValue]==component&&
        [policy[@"SASS"][@"expected_output_component"]unsignedIntValue]==component;
    NSMutableDictionary *identities=[NSMutableDictionary dictionary];
    NSArray *pairs=@[@[@"library",@"test.metallib"],@[@"air",@"test.air"],@[@"typed_air",@"typed-air.json"],@[@"source",@"test.metal"],@[@"original_code",@"native.sass"]];
#ifdef COMPILED_METALLIB_CAS_IMPORT
    pairs=@[@[@"library",@"library.metallib"],@[@"typed_air",@"typed-air.json"],@[@"original_code",@"native.sass"]];
    valid=valid&&[plan[@"function"]isEqual:policy[@"function"]];
    NSData *libraryData=[NSData dataWithContentsOfFile:plan[@"library"]];
    uint64_t offset=[policy[@"embedded_AIR"][@"offset"]unsignedLongLongValue],length=[policy[@"embedded_AIR"][@"bytes"]unsignedLongLongValue];
    bool range=libraryData&&offset<=libraryData.length&&length<=libraryData.length-offset&&length>=20;
    NSData *module=range?[libraryData subdataWithRange:NSMakeRange(offset,length)]:nil;
    NSString *actualModule=dataSHA(module),*expectedModule=policy[@"embedded_AIR"][@"sha256"];
    bool moduleMatches=actualModule&&[actualModule isEqual:expectedModule];valid=valid&&range&&moduleMatches;
    identities[@"embedded_AIR"]=@{@"actual":actualModule?:@"",@"expected":expectedModule?:@"",@"matches":@(moduleMatches)};
#endif
    for(NSArray *pair in pairs) {
        NSString *actual=fileSHA(plan[pair[0]]),*expected=policy[@"hashes"][pair[1]];
        bool matches=actual&&expected&&[actual isEqual:expected];valid=valid&&matches;
        identities[pair[1]]=@{@"actual":actual?:@"",@"expected":expected?:@"",@"matches":@(matches)};
    }
    NSString *actualCode=fileSHA(plan[@"code"]),*expectedCode=policy[@"replacement_hashes"][plan[@"code_kind"]?:@""];
    bool codeMatches=actualCode&&expectedCode&&[actualCode isEqual:expectedCode];valid=valid&&codeMatches;
    identities[@"replacement"]=@{@"actual":actualCode?:@"",@"expected":expectedCode?:@"",@"matches":@(codeMatches)};
    if(![plan[@"intent"]isEqual:@"post_CAS_expected"])valid=false;
    return @{@"accepted":@(valid),@"identities":identities,@"expected_output_component":@(component),
             @"scope":@"AIR/SASS candidate diagnosis and exact input identities, followed by a byte-exact constructor gate. Not a general semantic proof or deployed compiler patch."};
}
#endif
// Exported only by the isolated bridge fork used for native repair experiments.
#ifdef PINNED_NATIVE_CAS_IMPORT
extern "C" id<MTLComputePipelineState> KPCreatePinnedNativeCASPipeline(
    id<MTLDevice>,NSURL*,NSString*,NSData*,NSData*,KeplerImportConfig,NSError**,NSDictionary**);
#ifdef COMPILED_METALLIB_CAS_IMPORT
extern "C" id<MTLComputePipelineState> KPCreatePreservingNativeCASPipeline(
    id<MTLDevice>,NSURL*,NSString*,NSData*,NSData*,NSError**,NSDictionary**);
#endif
#endif
struct Params {uint32_t seed,n,local,groups,variant;};
struct ImportABI {uint64_t addresses[4];uint32_t grid[3],block[3];};
static_assert(sizeof(Params)==20 && sizeof(ImportABI)==56,"Explicit resource ABI");
static void emit(NSDictionary *d) {
    NSData *b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];
    if(b)fwrite(b.bytes,1,b.length,stdout);puts("");fflush(stdout);
}
static NSDictionary *finish(id<MTLCommandBuffer> command) {
    [command commit];[command waitUntilCompleted];
    return @{@"status":@(command.status),@"error":command.error.description?:@"",
             @"reported_GPU_seconds":@(command.GPUEndTime-command.GPUStartTime)};
}
static bool complete(NSDictionary *state) {return [state[@"status"]intValue]==MTLCommandBufferStatusCompleted;}
int main(int argc,char **argv) {@autoreleasepool {
    if(argc!=3)return 1;
    NSDictionary *plan=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])] options:0 error:nil];
    NSString *directory=@(argv[2]),*mode=plan[@"mode"],*space=plan[@"space"],*function=plan[@"function"]?:@"test";
    bool nak=[mode isEqual:@"air_nak"],control=[mode isEqual:@"carrier_control"];
    bool nativeImported=[mode isEqual:@"native_replay"]||[mode isEqual:@"native_trampoline"]||[mode isEqual:@"native_repaired"]||[mode isEqual:@"negative_native_pin"]||[mode isEqual:@"negative_semantic_policy"];
    NSString *layout=plan[@"layout"]?:@"standard",*intent=plan[@"intent"]?:@"post_CAS_expected";
    bool permuted=[layout isEqual:@"permuted"],noise=[layout isEqual:@"noise"],originalCompare=[intent isEqual:@"original_comparand"];
    if(!permuted&&!noise&&![layout isEqual:@"standard"])return 1;
    if(!originalCompare&&![intent isEqual:@"post_CAS_expected"])return 1;
    unsigned local=plan[@"local"]?[plan[@"local"]unsignedIntValue]:1;
    unsigned groups=plan[@"groups"]?[plan[@"groups"]unsignedIntValue]:1;
    bool contended=[plan[@"contended"]boolValue];unsigned n=local*groups;
    bool requireNativeLockLoop=[plan[@"require_native_lock_loop"]boolValue];
    if(!local||local>1024||!groups||groups>3)return 1;
    if((!nak&&!control&&!nativeImported&&![mode isEqual:@"native"])||(![space isEqual:@"device"]&&![space isEqual:@"threadgroup"])||[plan[@"variant"]unsignedIntValue]>1)return 1;
    id<MTLDevice>device=nil;
    for(id<MTLDevice>d in MTLCopyAllDevices())if([d.name containsString:@"880M"]){device=d;break;}
    if(!device)return 2;
    NSMutableDictionary *result=[NSMutableDictionary dictionaryWithDictionary:@{
        @"device":device.name,@"registry_id":@(device.registryID),@"mode":mode,@"space":space,
        @"variant":plan[@"variant"],@"single_CAS_no_retry":@YES,@"local":@(local),@"groups":@(groups),@"contended":@(contended),
        @"layout":layout,@"intent":intent,@"oracle_native_lock_loop_one_winner":@(requireNativeLockLoop),
        @"scope":@"own-process function-level execution, including targeted native-output repairs; no installed-driver repair or global Metal-family qualification"}];
    NSError *error=nil;NSDictionary *proof=nil;id<MTLComputePipelineState>pipeline=nil;
    if(nativeImported) {
#ifdef QUALIFIED_NATIVE_CAS_IMPORT
        NSDictionary *policy=semanticPolicy(plan,permuted?1:0);result[@"semantic_policy"]=policy;
        if(![policy[@"accepted"]boolValue]){result[@"failure_stage"]=@"semantic_policy";result[@"GPU_dispatch"]=@NO;emit(result);return 12;}
#endif
#ifdef PINNED_NATIVE_CAS_IMPORT
#ifdef COMPILED_METALLIB_CAS_IMPORT
        pipeline=KPCreatePreservingNativeCASPipeline(device,[NSURL fileURLWithPath:plan[@"library"]],function,
                  [NSData dataWithContentsOfFile:plan[@"original_code"]],[NSData dataWithContentsOfFile:plan[@"code"]],&error,&proof);
#else
        pipeline=KPCreatePinnedNativeCASPipeline(device,[NSURL fileURLWithPath:plan[@"library"]],@"test",
                  [NSData dataWithContentsOfFile:plan[@"original_code"]],[NSData dataWithContentsOfFile:plan[@"code"]],
                  {24,576,576},&error,&proof);
#endif
#else
        return 3;
#endif
    } else if(nak) {
        NSDictionary *info=plan[@"info"];
        if([info[@"sm"]unsignedIntValue]!=30||[info[@"buffer_slots"]unsignedIntValue]!=4||
           [info[@"grid_offset"]unsignedIntValue]!=32||[info[@"push_bytes"]unsignedIntValue]!=56||
           [info[@"constant_bank"]unsignedIntValue]!=2||[info[@"scratch_bytes"]unsignedIntValue]||
           [info[@"crs_bytes"]unsignedIntValue]||[info[@"shared_bytes"]unsignedIntValue]>512||
           ![info[@"local_size"]isEqual:@[@(local),@1,@1]])return 3;
        unsigned regs=std::max(24u,[info[@"registers"]unsignedIntValue]);
        pipeline=KPCreatePipeline(device,[NSURL fileURLWithPath:plan[@"carrier"]],@"cas_carrier",
                    [NSData dataWithContentsOfFile:plan[@"code"]],{regs,576,576},&error,&proof);
    } else {
        id<MTLLibrary>library=[device newLibraryWithURL:[NSURL fileURLWithPath:control?plan[@"carrier"]:plan[@"library"]] error:&error];
        id<MTLFunction>entry=[library newFunctionWithName:control?@"cas_carrier":function];
        if(entry)pipeline=[device newComputePipelineStateWithFunction:entry error:&error];
        [entry release];[library release];
    }
    if(!pipeline) {result[@"failure_stage"]=@"pipeline";result[@"error"]=error.description?:@"nil";result[@"import"]=proof?:@{};emit(result);return 4;}
    result[@"import"]=proof?:@{};result[@"pipeline_static_shared_bytes"]=@(pipeline.staticThreadgroupMemoryLength);
    result[@"pipeline_max_threads"]=@(pipeline.maxTotalThreadsPerThreadgroup);
    if(pipeline.maxTotalThreadsPerThreadgroup<local||
       (nak&&pipeline.staticThreadgroupMemoryLength<[plan[@"info"][@"shared_bytes"]unsignedIntValue]))return 5;
    id<MTLCommandQueue>queue=[[device newCommandQueue]autorelease];if(!queue)return 5;
    NSMutableArray *runs=[NSMutableArray array];unsigned totalBad=0,totalGuards=0;
    for(unsigned iteration=0;iteration<3;iteration++) {@autoreleasepool {
        Params p={0x1234u+37u*iteration,n,local,groups,[plan[@"variant"]unsignedIntValue]};
        const size_t bytes=n*16+128;std::vector<uint8_t>canary(bytes,0xa5);
        std::vector<uint32_t>counterInitial(n);for(unsigned i=0;i<n;i++)counterInitial[i]=p.seed+(i/local)*0x10001u;
        id<MTLBuffer>output=[[device newBufferWithLength:bytes options:MTLResourceStorageModePrivate]autorelease];
        id<MTLBuffer>staging=[[device newBufferWithBytes:canary.data() length:bytes options:MTLResourceStorageModeManaged]autorelease];
        id<MTLBuffer>counter=[[device newBufferWithLength:n*4 options:MTLResourceStorageModePrivate]autorelease];
        id<MTLBuffer>initial=[[device newBufferWithBytes:counterInitial.data() length:n*4 options:MTLResourceStorageModeShared]autorelease];
        id<MTLBuffer>parameters=[[device newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared]autorelease];
        if(!output||!staging||!counter||!initial||!parameters||!output.gpuAddress||!counter.gpuAddress||!parameters.gpuAddress)return 6;
        id<MTLCommandBuffer>upload=[queue commandBuffer];id<MTLBlitCommandEncoder>blit=[upload blitCommandEncoder];
        [blit copyFromBuffer:staging sourceOffset:0 toBuffer:output destinationOffset:0 size:bytes];
        [blit copyFromBuffer:initial sourceOffset:0 toBuffer:counter destinationOffset:0 size:n*4];[blit endEncoding];
        NSDictionary *uploaded=finish(upload);if(!complete(uploaded)){result[@"failure_stage"]=@"upload";result[@"command"]=uploaded;emit(result);return 7;}
        ImportABI abi={{parameters.gpuAddress,output.gpuAddress+64,0,counter.gpuAddress},{n,1,1},{local,1,1}};
        id<MTLBuffer>mirror=[[device newBufferWithBytes:&abi length:sizeof abi options:MTLResourceStorageModeShared]autorelease];if(!mirror)return 6;
        id<MTLCommandBuffer>compute=[queue commandBuffer];id<MTLComputeCommandEncoder>encoder=[compute computeCommandEncoder];
        [encoder setComputePipelineState:pipeline];[encoder setBuffer:(nak||control)?mirror:parameters offset:0 atIndex:0];
        [encoder setBuffer:output offset:64 atIndex:1];
        if(!nak&&!control)[encoder setBuffer:counter offset:0 atIndex:3];
        [encoder useResource:parameters usage:MTLResourceUsageRead];[encoder useResource:counter usage:MTLResourceUsageRead|MTLResourceUsageWrite];
        [encoder dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[encoder endEncoding];
        NSDictionary *computed=finish(compute);if(!complete(computed)){result[@"failure_stage"]=@"compute";result[@"command"]=computed;emit(result);return 8;}
        id<MTLCommandBuffer>read=[queue commandBuffer];blit=[read blitCommandEncoder];
        [blit copyFromBuffer:output sourceOffset:0 toBuffer:staging destinationOffset:0 size:bytes];[blit synchronizeResource:staging];[blit endEncoding];
        NSDictionary *readback=finish(read);if(!complete(readback)){result[@"failure_stage"]=@"readback";result[@"command"]=readback;emit(result);return 9;}
        const uint8_t *raw=(const uint8_t*)staging.contents;const uint32_t *v=(const uint32_t*)(raw+64);
        unsigned bad=0,guards=0;for(size_t i=0;i<64;i++){guards+=raw[i]!=0xa5;guards+=raw[bytes-64+i]!=0xa5;}
        std::vector<unsigned>successes(groups,0);
        for(unsigned i=0;i<n;i++)if(v[4*i+(permuted?2:1)]==1)successes[i/local]++;
        for(unsigned i=0;i<n;i++) {
            const uint32_t *row=v+4*i;unsigned g=i/local;
            uint32_t expected=row[permuted?1:0],swapped=row[permuted?2:1],final=row[permuted?3:2],index=row[permuted?0:3];
            uint32_t initialValue=p.seed+g*0x10001u,replacement=p.seed^0x55667788u;
            if(control){bad+=row[0]!=(n^0x7a11beefu);bad+=row[1]!=0;bad+=row[2]!=0xdeadbeef;bad+=row[3]!=i;continue;}
            uint32_t wantedIndex=noise?(i^((p.seed*0x9e3779b9u)^(i*17u))):i;
            bad+=swapped>1;bad+=p.variant&&swapped!=0;bad+=index!=wantedIndex;
            if(originalCompare)bad+=expected!=(initialValue^(p.variant?1u:0u));
            else if(!contended||p.variant||swapped)bad+=expected!=initialValue;
            else if(nak||requireNativeLockLoop)bad+=expected!=replacement; // Qualified preserved native lock loop, not a generic weak-CAS guarantee.
            else bad+=expected!=initialValue&&expected!=replacement; // Allow weak spurious failures before a winner.
            uint32_t finalValue=contended?(successes[g]?replacement:initialValue):(swapped?replacement:initialValue);
            bad+=final!=finalValue;
        }
        if(contended&&!p.variant&&!control)for(unsigned g=0;g<groups;g++)bad+=(nak||requireNativeLockLoop)?(successes[g]!=1):(successes[g]>1);
        NSString *path=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"output-%u.bin",iteration]];
        if(![[NSData dataWithBytes:raw length:bytes]writeToFile:path atomically:YES])return 11;
        [runs addObject:@{@"seed":@(p.seed),@"iteration":@(iteration),@"output_file":path,
            @"values":@[@(v[0]),@(v[1]),@(v[2]),@(v[3])],@"elements":@(n),@"mismatches":@(bad),@"guard_mismatches":@(guards),
            @"compute":computed,@"readback":readback}];totalBad+=bad;totalGuards+=guards;
        if(guards)break;
    }}
    result[@"runs"]=runs;result[@"mismatches"]=@(totalBad);result[@"guard_mismatches"]=@(totalGuards);
    result[@"passed"]=@(!totalBad&&!totalGuards);result[@"GPU_dispatch"]=@YES;
    result[@"reported_process_allocated_bytes"]=@(device.currentAllocatedSize);
    result[@"performance_benchmark"]=@NO;emit(result);[pipeline release];return totalBad||totalGuards?10:0;
}}
