// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>

// Transport-independent lifecycle; this does not submit video commands.
namespace kepler_video {
using Handle = uint32_t;
constexpr int NotCalled = INT32_MIN;
// An open callback may report a nonzero output only when that handle is
// owned and must be closed, including when the callback returns an error.
struct Backend {
    void *user;
    int (*open)(void *, Handle, uint32_t, Handle *);
    int (*associate)(void *, Handle, Handle);
    int (*close)(void *, Handle);
};
struct Report {
    int context_open = NotCalled, shared_open = NotCalled, association = NotCalled;
    int context_close = NotCalled, shared_close = NotCalled;
    bool context_returned = false, shared_returned = false, distinct = false;
};
class Lease final {
public:
    explicit Lease(Backend backend) noexcept : backend_(backend) {}
    ~Lease() noexcept { close(); }
    Lease(const Lease &) = delete;
    Lease &operator=(const Lease &) = delete;
    bool start(Handle service, bool associate) noexcept;
    bool close() noexcept;
    const Report &report() const noexcept { return report_; }
private:
    Backend backend_;
    Report report_{};
    Handle context_ = 0, shared_ = 0;
    bool started_ = false, closed_ = false;
};
}
