#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <vector>
#include <cstdint>
#include <cstring>
#include <chrono>
struct Params{uint32_t seed,n,local,groups,variant;};
static void emit(NSDictionary*d){NSData*b=[NSJSONSerialization dataWithJSONObject:d options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");fflush(stdout);}
static NSDictionary* complete(id<MTLCommandBuffer>c){[c commit];[c waitUntilCompleted];return @{ @"status":@(c.status),@"error":c.error.description?:@"",@"error_code":@(c.error.code),@"gpu_seconds":@(c.GPUEndTime-c.GPUStartTime)};}
static bool ok(NSDictionary*d){return [d[@"status"]intValue]==MTLCommandBufferStatusCompleted;}
static id<MTLBuffer> buffer(id<MTLDevice>d,id<MTLCommandQueue>q,const void*b,size_t n,NSString*mode,NSMutableArray*stages){
 MTLResourceOptions o=[mode isEqual:@"private"]?MTLResourceStorageModePrivate:([mode isEqual:@"managed"]?MTLResourceStorageModeManaged:MTLResourceStorageModeShared);
 id<MTLBuffer>r=[d newBufferWithLength:n options:o];if(!r)return nil;
 if(o==MTLResourceStorageModePrivate){id<MTLBuffer>h=[d newBufferWithBytes:b length:n options:MTLResourceStorageModeShared];id<MTLCommandBuffer>c=[q commandBuffer];id<MTLBlitCommandEncoder>e=[c blitCommandEncoder];[e copyFromBuffer:h sourceOffset:0 toBuffer:r destinationOffset:0 size:n];[e endEncoding];NSDictionary*s=complete(c);[stages addObject:@{@"upload":s}];if(!ok(s))return nil;}
 else{memcpy(r.contents,b,n);if(o==MTLResourceStorageModeManaged)[r didModifyRange:NSMakeRange(0,n)];}return r;
}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;NSDictionary*c=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[1])] options:0 error:nil];NSString*out=@(argv[2]);
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 NSMutableDictionary*r=[@{@"device":d.name,@"registry_id":@(d.registryID),@"case":c,@"argument_tier_raw":@(d.argumentBuffersSupport),@"argument_tier2_declared":@(d.argumentBuffersSupport==MTLArgumentBuffersTier2),@"native_only":@YES,@"linked_import_library":@NO}mutableCopy];
 NSError*err=nil;id<MTLLibrary>lib=nil;
 if(c[@"runtime_language"]){MTLCompileOptions*options=[MTLCompileOptions new];options.languageVersion=(MTLLanguageVersion)[c[@"runtime_language"]unsignedIntegerValue];options.fastMathEnabled=NO;NSString*text=[NSString stringWithContentsOfFile:c[@"source"] encoding:NSUTF8StringEncoding error:&err];lib=text?[d newLibraryWithSource:text options:options error:&err]:nil;}
 else lib=[d newLibraryWithURL:[NSURL fileURLWithPath:c[@"library"]] error:&err];if(!lib){r[@"failure_stage"]=@"library";r[@"error"]=err.description?:@"nil library";emit(r);return 3;}
 id<MTLFunction>f=[lib newFunctionWithName:@"test"];id<MTLComputePipelineState>pipe=f?[d newComputePipelineStateWithFunction:f error:&err]:nil;if(!pipe){r[@"failure_stage"]=@"pipeline";r[@"error"]=err.description?:@"nil function/pipeline";emit(r);return 4;}
 r[@"thread_execution_width"]=@(pipe.threadExecutionWidth);r[@"pipeline_max_threads"]=@(pipe.maxTotalThreadsPerThreadgroup);r[@"static_shared_bytes"]=@(pipe.staticThreadgroupMemoryLength);
 NSString*kind=c[@"kind"],*op=c[@"op"],*mode=c[@"storage"]?:@"private";bool ab=[kind hasPrefix:@"argument"],gpuab=[kind hasPrefix:@"argument_gpu"],tex=[kind isEqual:@"argument_mixed"]||[kind isEqual:@"argument_gpu_mixed"],simd=[kind isEqual:@"simd"],cas=[kind isEqual:@"cas"];
 unsigned local=[c[@"local"]unsignedIntValue],groups=[c[@"groups"]unsignedIntValue],n=local*groups,N=[c[@"resources"]unsignedIntValue],cols=4;
 if(!local||local>pipe.maxTotalThreadsPerThreadgroup||!groups||groups>16||N>96){r[@"failure_stage"]=@"configuration";emit(r);return 5;}
 id<MTLCommandQueue>q=[d newCommandQueue];NSMutableArray*stages=[NSMutableArray new],*runs=[NSMutableArray new];
 id<MTLArgumentEncoder>ae=ab?[f newArgumentEncoderWithBufferIndex:0]:nil;
 if(ab&&(!ae||!ae.encodedLength)){r[@"failure_stage"]=@"argument_encoder";emit(r);return 6;}if(ab)r[@"argument_encoded_length"]=@(ae.encodedLength);
 id<MTLComputePipelineState>producer=nil;if(gpuab){id<MTLFunction>pf=[lib newFunctionWithName:@"produce"];producer=pf?[d newComputePipelineStateWithFunction:pf error:&err]:nil;if(!producer){r[@"failure_stage"]=@"producer_pipeline";r[@"error"]=err.description?:@"nil";emit(r);return 7;}}
 for(unsigned iteration=0;iteration<3;iteration++){@autoreleasepool{
 Params p={0x1234u+iteration*37u,n,local,groups,[c[@"variant"]unsignedIntValue]};size_t bytes=n*cols*4+128;std::vector<uint8_t>initial(bytes,0xa5);
 id<MTLBuffer>output=buffer(d,q,initial.data(),bytes,mode,stages);if(!output){r[@"failure_stage"]=@"allocation_upload";emit(r);return 8;}
 id<MTLBuffer>params=[d newBufferWithBytes:&p length:sizeof p options:MTLResourceStorageModeShared];NSMutableArray*pool=[NSMutableArray new],*textures=[NSMutableArray new],*samplers=[NSMutableArray new];id<MTLBuffer>args=nil,destination=nil,counters=nil;
 std::vector<unsigned>binding(N);
 if(ab){args=[d newBufferWithLength:ae.encodedLength options:MTLResourceStorageModeManaged];if(!args){r[@"failure_stage"]=@"argument_buffer_allocation";emit(r);return 8;}[ae setArgumentBuffer:args offset:0];
 for(unsigned slot=0;slot<N;slot++){std::vector<uint32_t>v(96,0xabababab);for(unsigned j=0;j<64;j++)v[16+j]=(slot+1)*65536+j*17;id<MTLBuffer>b=buffer(d,q,v.data(),v.size()*4,@"private",stages);if(!b){r[@"failure_stage"]=@"input_buffer";emit(r);return 8;}[pool addObject:b];}
 for(unsigned i=0;i<N;i++){binding[i]=iteration==0?i:(iteration==1?(i+3)%N:N-1-i);[ae setBuffer:pool[binding[i]] offset:64 atIndex:i];}
 if(tex){for(unsigned slot=0;slot<N;slot++){MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:8 height:8 mipmapped:NO];td.storageMode=MTLStorageModeManaged;td.usage=MTLTextureUsageShaderRead;id<MTLTexture>t=[d newTextureWithDescriptor:td];if(!t){r[@"failure_stage"]=@"texture_allocation";emit(r);return 8;}float pixels[64];for(unsigned j=0;j<64;j++)pixels[j]=(slot+1)*1024+j;[t replaceRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0 withBytes:pixels bytesPerRow:32];[textures addObject:t];}
 for(unsigned i=0;i<N;i++)[ae setTexture:textures[binding[i]] atIndex:N+i];
 for(unsigned s=0;s<2;s++){MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];sd.minFilter=MTLSamplerMinMagFilterNearest;sd.magFilter=MTLSamplerMinMagFilterNearest;sd.sAddressMode=s?MTLSamplerAddressModeRepeat:MTLSamplerAddressModeClampToEdge;sd.tAddressMode=sd.sAddressMode;sd.supportArgumentBuffers=YES;id<MTLSamplerState>sam=[d newSamplerStateWithDescriptor:sd];if(!sam){r[@"failure_stage"]=@"sampler_allocation";emit(r);return 8;}[samplers addObject:sam];[ae setSamplerState:sam atIndex:2*N+s];}}
 [args didModifyRange:NSMakeRange(0,args.length)];
 if(gpuab){std::vector<uint8_t>zero(ae.encodedLength);destination=buffer(d,q,zero.data(),zero.size(),@"private",stages);}
 }
 if(cas){std::vector<uint32_t>v(n);for(unsigned i=0;i<n;i++)v[i]=p.seed+(i/local)*0x10001u;counters=buffer(d,q,v.data(),v.size()*4,mode,stages);}
 id<MTLCommandBuffer>compute=[q commandBuffer];
 if(gpuab&&tex){id<MTLBlitCommandEncoder>b=[compute blitCommandEncoder];[b copyFromBuffer:args sourceOffset:0 toBuffer:destination destinationOffset:0 size:args.length];[b endEncoding];}
 if(gpuab){id<MTLComputeCommandEncoder>e=[compute computeCommandEncoder];[e setComputePipelineState:producer];[e setBuffer:args offset:0 atIndex:0];[e setBuffer:destination offset:0 atIndex:1];[e setBuffer:params offset:0 atIndex:2];for(id<MTLBuffer>b in pool)[e useResource:b usage:MTLResourceUsageRead];for(id<MTLTexture>t in textures)[e useResource:t usage:MTLResourceUsageRead];[e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(N,1,1)];[e endEncoding];}
 id<MTLComputeCommandEncoder>e=[compute computeCommandEncoder];[e setComputePipelineState:pipe];if(ab){[e setBuffer:gpuab?destination:args offset:0 atIndex:0];for(id<MTLBuffer>b in pool)[e useResource:b usage:MTLResourceUsageRead];for(id<MTLTexture>t in textures)[e useResource:t usage:MTLResourceUsageRead];}else [e setBuffer:params offset:0 atIndex:0];
 [e setBuffer:output offset:64 atIndex:1];[e setBuffer:params offset:0 atIndex:2];if(cas)[e setBuffer:counters offset:0 atIndex:3];[e dispatchThreadgroups:MTLSizeMake(groups,1,1) threadsPerThreadgroup:MTLSizeMake(local,1,1)];[e endEncoding];NSDictionary*cs=complete(compute);[stages addObject:@{@"compute":cs}];
 id<MTLBuffer>host=[d newBufferWithLength:bytes options:MTLResourceStorageModeManaged];id<MTLCommandBuffer>read=[q commandBuffer];id<MTLBlitCommandEncoder>be=[read blitCommandEncoder];[be copyFromBuffer:output sourceOffset:0 toBuffer:host destinationOffset:0 size:bytes];[be synchronizeResource:host];[be endEncoding];NSDictionary*rs=complete(read);[stages addObject:@{@"readback":rs}];
 if(!ok(cs)||!ok(rs)){r[@"failure_stage"]=!ok(cs)?@"compute":@"readback";r[@"stages"]=stages;r[@"runs"]=runs;emit(r);return 9;}
 NSString*dump=[out stringByAppendingPathComponent:[NSString stringWithFormat:@"output-%u.bin",iteration]];[[NSData dataWithBytes:host.contents length:bytes]writeToFile:dump atomically:YES];
 const uint32_t*v=(const uint32_t*)((const uint8_t*)host.contents+64);unsigned bad=0,guards=0,successes=0;for(size_t i=0;i<64;i++){if(((uint8_t*)host.contents)[i]!=0xa5)guards++;if(((uint8_t*)host.contents)[bytes-64+i]!=0xa5)guards++;}
 for(unsigned i=0;i<n;i++){uint32_t expected[4]={};unsigned tid=i%local,g=i/local,width=pipe.threadExecutionWidth,base=(tid/width)*width,active=std::min(width,local-base),lane=tid%width;
 if(ab){unsigned requested=(i*13+p.seed)%N;unsigned logical=gpuab?(requested+p.seed%N)%N:requested;unsigned slot=binding[logical],j=(i*7+p.seed)&63;expected[0]=(slot+1)*65536+j*17;
 if(tex){unsigned requestedTexture=(i*5+p.seed)%N;unsigned ts=binding[gpuab?(requestedTexture+p.seed%N)%N:requestedTexture],x=(i*3+p.seed)%16,y=(i*5+p.seed)%16,s=(i+p.seed)&1;x=s?x%8:std::min(x,7u);y=s?y%8:std::min(y,7u);expected[1]=(ts+1)*1024+y*8+x;}else expected[1]=requested;
 expected[2]=p.seed;expected[3]=i;}
 else if(simd){auto value=[&](unsigned t){return (g*local+t)*17%97+((p.seed%97)+1);};uint32_t ans=0;
 if([op isEqual:@"sum"]||[op isEqual:@"sum_float"]||[op isEqual:@"sum_divergent"]){for(unsigned t=base;t<base+active;t++)if(![op isEqual:@"sum_divergent"]||(t&1))ans+=value(t);if([op isEqual:@"sum_divergent"]&&!(tid&1))ans=0xdead0000u;}
 else if([op isEqual:@"min"]){ans=UINT32_MAX;for(unsigned t=base;t<base+active;t++)ans=std::min(ans,value(t));}
 else if([op isEqual:@"max"]){for(unsigned t=base;t<base+active;t++)ans=std::max(ans,value(t));}
 else if([op isEqual:@"prefix"]){for(unsigned t=base;t<tid;t++)ans+=value(t);}
 else if([op isEqual:@"shuffle"]){ans=value(base);}
 else if([op isEqual:@"xor"]){ans=value(base+(lane^1));}
 else if([op isEqual:@"ballot"]){for(unsigned t=0;t<active;t++)if((base+t)&1)ans|=1u<<t;}
 else if([op isEqual:@"all"]){ans=1;for(unsigned t=base;t<base+active;t++)ans&=(value(t)>50);}
 else if([op isEqual:@"any"]){for(unsigned t=base;t<base+active;t++)ans|=(value(t)>50);}
 else if([op isEqual:@"control"]){ans=value(tid);}
 expected[0]=ans;expected[1]=lane;expected[2]=width;expected[3]=i;}
 else if(cas){uint32_t init=p.seed+g*0x10001u,replacement=p.seed^0x55667788u;bool shared=[c[@"address_space"]isEqual:@"threadgroup"],contended=[c[@"contended"]boolValue];
 if([op isEqual:@"add"]){expected[0]=contended?v[i*4]:init;expected[1]=1;expected[2]=init+(contended?local:1);expected[3]=i; if(contended&&(v[i*4]<init||v[i*4]>=init+local))bad++;}
 else if([op isEqual:@"load_store"]){expected[0]=init;expected[1]=p.variant?0:1;expected[2]=p.variant?init:replacement;expected[3]=i;}
 else{bool succeeded=v[i*4+1]!=0;if(succeeded)successes++;expected[0]=p.variant?init:((!contended||succeeded)?init:replacement);expected[1]=p.variant?0:((!contended)?1:v[i*4+1]);expected[2]=p.variant?init:replacement;expected[3]=i;}
 (void)shared;}
 for(unsigned k=0;k<cols;k++)if(v[i*cols+k]!=expected[k])bad++;
 }
 if(cas&&[op isEqual:@"weak"]&&![c[@"variant"]boolValue]&&[c[@"contended"]boolValue]&&successes!=groups)bad++;
 NSDictionary*run=@{@"iteration":@(iteration),@"seed":@(p.seed),@"elements":@(n),@"columns":@(cols),@"output_file":dump,@"mismatches":@(bad),@"guard_mismatches":@(guards),@"cas_successes":@(successes),@"compute":cs,@"readback":rs};[runs addObject:run];
 if(bad||guards){r[@"failure_stage"]=@"numeric_validation";r[@"runs"]=runs;r[@"stages"]=stages;emit(r);return 10;}
 }}
 r[@"runs"]=runs;r[@"stages"]=stages;r[@"passed"]=@YES;emit(r);return 0;
}}
