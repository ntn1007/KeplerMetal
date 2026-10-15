#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>

// Explicit adapted-application API. Result buffers contain these 16-byte
// records. A record can feed a later operation with stride16, entirely on GPU.
// Packed input slots use stride8. No CPU arithmetic or intermediate readback
// is performed by this library. Arithmetic and conversions to binary64 use
// nearest-even. Conversions from binary64 select an explicit rounding mode.
// FromSigned64/FromUnsigned64 interpret the whole slot as an integer;
// FromFloat32Bits interprets its low32bits as IEEE binary32 and ignores the
// high32bits. Dense stride4 float arrays are outside the current input ABI.
typedef struct { double value; uint32_t index; uint32_t stamp; } KPBinary64Record;
// The same16-byte layout for typed conversion results. Integer bits are64-bit
// two's-complement/unsigned; binary32 bits occupy the low word, high word zero.
typedef struct { uint64_t bits; uint32_t index; uint32_t stamp; } KPBitPatternRecord;
typedef NS_ENUM(NSUInteger, KPBinary64Operation) {
    KPBinary64Add, KPBinary64Multiply, KPBinary64FMA,
    KPBinary64Divide, KPBinary64SquareRoot,
    KPBinary64FromSigned64, KPBinary64FromUnsigned64, KPBinary64FromFloat32Bits,
    KPBinary64ToFloat32Nearest, KPBinary64ToFloat32TowardZero,
    KPBinary64ToFloat32TowardPositiveInfinity, KPBinary64ToFloat32TowardNegativeInfinity,
    KPBinary64ToSigned64Nearest, KPBinary64ToSigned64TowardZero,
    KPBinary64ToSigned64TowardPositiveInfinity, KPBinary64ToSigned64TowardNegativeInfinity,
    KPBinary64ToUnsigned64Nearest, KPBinary64ToUnsigned64TowardZero,
    KPBinary64ToUnsigned64TowardPositiveInfinity, KPBinary64ToUnsigned64TowardNegativeInfinity
};

@interface KPBinary64Input : NSObject
+ (instancetype)inputWithBuffer:(id<MTLBuffer>)buffer offset:(NSUInteger)offset
                         stride:(NSUInteger)stride;
@property(nonatomic,readonly) id<MTLBuffer> buffer;
@property(nonatomic,readonly) NSUInteger offset;
@property(nonatomic,readonly) NSUInteger stride;
@end

@interface KPBinary64Library : NSObject
// Carrier and the entire build-pinned program set are copied before checking
// SHA256s. Packages have15/24/60programs according to their supported operations.
// Keys: add-l32,...,to_u64_rm-l1024. qualification lists available operations
// and output contracts. Float32 output follows IEEE rounding/overflow and
// quiet-NaN classification. Integer output saturates after rounding; NaN→0.
// Reverse-conversion outputs use KPBitPatternRecord, not its bits as a double.
// Wrong/unknown/missing bytes fail before importing
// any program. Pipeline creation restores the NVIDIA constructor and shares
// its import mutex with the SDK's certified native-CAS module.
+ (instancetype)libraryWithDevice:(id<MTLDevice>)device
                      carrierData:(NSData *)carrier
                         programs:(NSDictionary<NSString *,NSData *> *)programs
                            error:(NSError **)error;
// Input counts: sqrt/conversions1, fma3, other2. Local sizes32/128/1024, count
// 0..1048576 (larger counts not qualified). Output offset and inputs align8.
// Output/input overlap, wrong device/storage/ranges and unsupported strides
// are refused before creating an encoder. Inputs use Shared/Private resources;
// Managed, memoryless and Untracked are outside this contract. Records stride16.
// The caller owns commit/wait and must abandon a CB after any encoding error.
// Default retained-reference command buffers only. Sequential use; no GPU/CPU
// concurrency or untracked cross-queue synchronization is qualified here.
- (BOOL)encodeOperation:(KPBinary64Operation)operation
          commandBuffer:(id<MTLCommandBuffer>)commandBuffer
                 inputs:(NSArray<KPBinary64Input *> *)inputs
                 output:(id<MTLBuffer>)output outputOffset:(NSUInteger)offset
                  count:(NSUInteger)count threadsPerGroup:(NSUInteger)local
                  stamp:(uint32_t)stamp error:(NSError **)error
               evidence:(NSDictionary **)evidence;
@property(nonatomic,readonly) NSDictionary *qualification;
@end
