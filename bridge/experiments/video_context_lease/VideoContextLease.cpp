// SPDX-License-Identifier: MIT
#include "VideoContextLease.h"
namespace kepler_video {
bool Lease::start(Handle service, bool associate) noexcept {
    if (started_ || closed_ || !service || !backend_.open || !backend_.associate || !backend_.close) return false;
    started_ = true;
    report_.context_open = backend_.open(backend_.user, service, 3, &context_);
    report_.context_returned = context_ != 0;
    if (report_.context_open != 0 || !context_) { close(); return false; }
    if (!associate) return true;
    report_.shared_open = backend_.open(backend_.user, service, 6, &shared_);
    report_.shared_returned = shared_ != 0;
    report_.distinct = shared_ && shared_ != context_;
    if (report_.shared_open != 0 || !report_.distinct) { close(); return false; }
    report_.association = backend_.associate(backend_.user, context_, shared_);
    if (report_.association != 0) { close(); return false; }
    return true;
}
bool Lease::close() noexcept {
    if (closed_) return (report_.context_close == NotCalled || report_.context_close == 0) &&
                         (report_.shared_close == NotCalled || report_.shared_close == 0);
    closed_ = true;
    // A duplicated port name is closed once; ownership is otherwise ambiguous.
    if (context_) { report_.context_close = backend_.close(backend_.user, context_); }
    if (shared_ && shared_ != context_) { report_.shared_close = backend_.close(backend_.user, shared_); }
    context_ = shared_ = 0;
    return (report_.context_close == NotCalled || report_.context_close == 0) &&
           (report_.shared_close == NotCalled || report_.shared_close == 0);
}
}
