// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
@interface PendingWitness : NSObject
- (instancetype)initWithDevice:(id<MTLDevice>)device directory:(NSString *)directory skip:(BOOL)skip;
- (BOOL)begin;
- (NSDictionary *)snapshot;
- (NSDictionary *)finish;
@end
