// SPDX-License-Identifier: MIT
// Shared test-only state: process lifetime and allocation are controlled by the host.
#pragma once
#include <atomic>
#include <cstddef>
#include <cstdint>
struct KMClientState {
 uintptr_t expected; size_t length; int (*covers)(uintptr_t,size_t);
 std::atomic<unsigned> *calls,*badArgs,*attempts,*duplicates,*unapproved;
 std::atomic<int> *before,*after,*status;
 std::atomic<bool> *authorized,*freed,*gpuCompleted;
};
using KMClientBlock=void (^)(void*,size_t);
extern "C" KMClientBlock KMClientMakeBlock(KMClientState*);
extern "C" unsigned KMClientCalls();
extern "C" unsigned KMClientRejected();
extern "C" int KMClientStatus();
