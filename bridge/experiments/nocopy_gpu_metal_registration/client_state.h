// SPDX-License-Identifier: MIT
// Independent client block ABI used by the explicitly adapted lab host.
#pragma once
#include <cstddef>
using KMClientBlock=void (^)(void*,size_t);
extern "C" KMClientBlock KMClientMakeBlock(void*,size_t);
extern "C" unsigned KMClientCalls();
extern "C" unsigned KMClientRejected();
extern "C" int KMClientStatus();
