// SPDX-License-Identifier: MIT
// CPU-only test of real KPComputeICBCommand's thread-grid conversion.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
static NSUInteger calls=0;static MTLSize lastGroups,lastLocal;
static void capture(id self,SEL sel,MTLSize groups,MTLSize local){(void)self;(void)sel;calls++;lastGroups=groups;lastLocal=local;}
static bool equal(MTLSize a,MTLSize b){return a.width==b.width&&a.height==b.height&&a.depth==b.depth;}
int main(){@autoreleasepool{
 Class base=NSClassFromString(@"KPComputeICBCommand");if(!base)return 1;
 Class subclass=objc_allocateClassPair(base,"KPUniformThreadContract",0);if(!subclass)return 2;
 SEL selector=@selector(concurrentDispatchThreadgroups:threadsPerThreadgroup:);Method method=class_getInstanceMethod(base,selector);
 if(!method||!class_addMethod(subclass,selector,(IMP)capture,method_getTypeEncoding(method)))return 3;objc_registerClassPair(subclass);
 id<MTLIndirectComputeCommand>c=(id<MTLIndirectComputeCommand>)[[subclass alloc]init];
 [c concurrentDispatchThreads:MTLSizeMake(24,12,8) threadsPerThreadgroup:MTLSizeMake(8,3,2)];
 if(calls!=1||!equal(lastGroups,MTLSizeMake(3,4,4))||!equal(lastLocal,MTLSizeMake(8,3,2)))return 4;
 [c concurrentDispatchThreads:MTLSizeMake(NSUIntegerMax,2,4) threadsPerThreadgroup:MTLSizeMake(1,1,2)];
 if(calls!=2||!equal(lastGroups,MTLSizeMake(NSUIntegerMax,2,2)))return 5;
 const MTLSize grids[]={MTLSizeMake(0,1,1),MTLSizeMake(1,0,1),MTLSizeMake(1,1,0),MTLSizeMake(1,1,1),MTLSizeMake(1,1,1),MTLSizeMake(1,1,1),MTLSizeMake(33,1,1),MTLSizeMake(32,3,1),MTLSizeMake(32,1,3)};
 const MTLSize locals[]={MTLSizeMake(1,1,1),MTLSizeMake(1,1,1),MTLSizeMake(1,1,1),MTLSizeMake(0,1,1),MTLSizeMake(1,0,1),MTLSizeMake(1,1,0),MTLSizeMake(32,1,1),MTLSizeMake(32,2,1),MTLSizeMake(32,1,2)};
 for(unsigned i=0;i<9;i++){BOOL rejected=NO;@try{[c concurrentDispatchThreads:grids[i] threadsPerThreadgroup:locals[i]];}@catch(NSException*x){(void)x;rejected=YES;}if(!rejected||calls!=2)return 6;}
 printf("{\"status\":\"PASS\",\"uniform_cases\":2,\"refusal_cases\":9,\"forwarded_calls\":2,\"GPU_execution\":false}\n");return 0;
}}
