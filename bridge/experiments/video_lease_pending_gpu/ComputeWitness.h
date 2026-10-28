// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
struct ComputeResult { bool attempted=false,library=false,function=false,pipeline=false,queue=false,buffer=false,submitted=false,completed=false,written=false; unsigned errors=0,guardErrors=0; };
ComputeResult runCompute(id<MTLDevice> device, NSString *directory, NSString *phase, uint32_t seed, bool skip);
NSDictionary *computeDict(const ComputeResult &r);
