// SPDX-License-Identifier: MIT
#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>
#include <limits>
#include <mutex>
#include <thread>

// Process-local scope gate for the experimental repeat observers.
// One owner prepares and snapshots; readers are admitted for one epoch only.
// A drain timeout permanently poisons the instance. It never mutates driver state.
class KPRepeatGate {
public:
    using Ticket = uint64_t;
    KPRepeatGate() = default;
    KPRepeatGate(const KPRepeatGate&) = delete;
    KPRepeatGate& operator=(const KPRepeatGate&) = delete;

    bool reserve() {
        if (held_.test_and_set(std::memory_order_seq_cst)) return false;
        if (poisoned_.load(std::memory_order_seq_cst) || inflight_.load(std::memory_order_seq_cst) != 0 ||
            epoch_.load(std::memory_order_seq_cst) >= std::numeric_limits<Ticket>::max()-1) {
            held_.clear(std::memory_order_seq_cst); return false;
        }
        { std::lock_guard<std::mutex> lock(ownerMutex_); owner_ = std::this_thread::get_id(); }
        return true;
    }
    bool activate() {
        if (!owned() || (epoch_.load(std::memory_order_seq_cst) & 1)) return false;
        epoch_.fetch_add(1, std::memory_order_seq_cst);
        return true;
    }
    bool activeOwner() const { return owned() && (epoch_.load(std::memory_order_seq_cst) & 1); }
    Ticket ticket() const { return epoch_.load(std::memory_order_seq_cst); }
    bool enter(Ticket t) {
        if (!(t & 1)) return false;
        inflight_.fetch_add(1, std::memory_order_seq_cst);
        if (epoch_.load(std::memory_order_seq_cst) != t) {
            inflight_.fetch_sub(1, std::memory_order_seq_cst); return false;
        }
        return true;
    }
    void leave() { inflight_.fetch_sub(1, std::memory_order_seq_cst); }
    bool close(std::chrono::milliseconds timeout) {
        if (!owned() || !(epoch_.load(std::memory_order_seq_cst) & 1)) return false;
        epoch_.fetch_add(1, std::memory_order_seq_cst);
        const auto deadline = std::chrono::steady_clock::now() + timeout;
        while (inflight_.load(std::memory_order_seq_cst) != 0) {
            if (std::chrono::steady_clock::now() >= deadline) {
                poisoned_.store(true, std::memory_order_seq_cst); return false;
            }
            std::this_thread::yield();
        }
        return true;
    }
    bool release() {
        if (!owned() || (epoch_.load(std::memory_order_seq_cst) & 1) ||
            inflight_.load(std::memory_order_seq_cst) != 0) return false;
        { std::lock_guard<std::mutex> lock(ownerMutex_); owner_ = std::thread::id(); }
        held_.clear(std::memory_order_seq_cst);
        return true;
    }
    bool poisoned() const { return poisoned_.load(std::memory_order_seq_cst); }

private:
    bool owned() const { std::lock_guard<std::mutex> lock(ownerMutex_); return owner_ == std::this_thread::get_id(); }
    std::atomic_flag held_ = ATOMIC_FLAG_INIT;
    std::atomic<Ticket> epoch_{0};
    std::atomic<uint64_t> inflight_{0};
    std::atomic<bool> poisoned_{false};
    mutable std::mutex ownerMutex_;
    std::thread::id owner_{};
};
