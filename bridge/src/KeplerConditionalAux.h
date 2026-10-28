// SPDX-License-Identifier: MIT
// Exact conditional-CAS auxiliary-section identity; not a general ABI parser.
#pragma once
#include <CommonCrypto/CommonDigest.h>
#include <cstddef>
#include <cstring>

static bool KPConditionalAuxMatches(const void *bytes, size_t size, unsigned count) {
 if(!bytes||size!=12||count!=1)return false;
 unsigned char digest[CC_SHA256_DIGEST_LENGTH];
 CC_SHA256(bytes,(CC_LONG)size,digest);
 static const unsigned char expected[CC_SHA256_DIGEST_LENGTH]={
  0x6b,0x67,0x31,0xdc,0x94,0x64,0xfd,0x82,0x5d,0x2a,0xef,0xe8,0x2c,0x37,0x33,0x48,
  0x75,0x81,0x14,0x91,0xee,0x9c,0x77,0x4b,0xae,0x64,0x60,0xf0,0x00,0x89,0x49,0xef};
 return memcmp(digest,expected,sizeof digest)==0;
}
