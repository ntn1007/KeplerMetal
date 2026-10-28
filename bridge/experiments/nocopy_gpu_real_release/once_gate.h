// SPDX-License-Identifier: MIT
// Test-only delivery arbitration; does not establish memory safety.
#pragma once
#include <atomic>
#include <cstddef>
#include <cstdint>
namespace kepler_witness {
enum class OnceResult { accepted, duplicate, invalid };
class OnceGate final {
 public:
  OnceGate(uintptr_t pointer, size_t length) : pointer_(pointer), length_(length) {}
  OnceGate(const OnceGate&) = delete;
  OnceGate& operator=(const OnceGate&) = delete;
  OnceResult accept(uintptr_t pointer,size_t length) {
    if (!pointer_ || !length_ || pointer!=pointer_ || length!=length_) return OnceResult::invalid;
    bool expected=false;
    return accepted_.compare_exchange_strong(expected,true) ? OnceResult::accepted : OnceResult::duplicate;
  }
 private:
  uintptr_t pointer_;size_t length_;std::atomic<bool> accepted_{false};
};
}
