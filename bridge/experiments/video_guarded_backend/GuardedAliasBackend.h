// SPDX-License-Identifier: MIT
#pragma once
#include "VideoContextLease.h"
#include "SharedAliasGuard.h"

namespace kepler_video {
// Caller retains the borrowed Metal connection and serializes the whole lease,
// including every other participant capable of changing its Mach references.
// This adapter cannot enforce that external contract or close TOCTOU races.
struct GuardOps {
    void *user;
    int (*open)(void *, Handle, uint32_t, Handle *);
    int (*refs)(void *, Handle, uint32_t *);
    bool (*equal)(void *, Handle, Handle);
    int (*associate)(void *, Handle, Handle);
    int (*closeContext)(void *, Handle);
    int (*releaseShared)(void *, Handle);
};
struct GuardReport {
    int before_status=NotCalled, opened_status=NotCalled, before_close_status=NotCalled, after_status=NotCalled;
    uint32_t before=0, opened=0, before_close=0, after=0;
    bool same_name=false, metal_self=false, extra_self=false, object_equal=false;
    bool qualified=false, rejected=false, ambiguous_output=false, unreleased=false, postcondition_failed=false;
};
constexpr int GuardRefused = -32001, GuardInvalid = -32002;
class GuardedAliasBackend final {
public:
    GuardedAliasBackend(GuardOps ops, Handle metal) noexcept : ops_(ops), metal_(metal) {}
    GuardedAliasBackend(const GuardedAliasBackend&)=delete;
    GuardedAliasBackend& operator=(const GuardedAliasBackend&)=delete;
    Backend backend() noexcept { return {this, openCallback, associateCallback, closeCallback}; }
    const GuardReport& report() const noexcept { return report_; }
private:
    static int openCallback(void*,Handle,uint32_t,Handle*) noexcept;
    static int associateCallback(void*,Handle,Handle) noexcept;
    static int closeCallback(void*,Handle) noexcept;
    bool configured() const noexcept;
    GuardOps ops_; Handle metal_=0, context_=0, extra_=0;
    bool context_attempted_=false, shared_attempted_=false, context_closed_=false, context_close_ok_=false, shared_closed_=false;
    GuardReport report_{};
};
}
