// SPDX-License-Identifier: MIT
#include "repeat_gate.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <thread>
using namespace std::chrono_literals;

int main() {
    KPRepeatGate g;
    assert(!g.enter(g.ticket()));
    assert(g.reserve());
    std::atomic<bool> rejected{false};
    std::thread contender([&]{ rejected = !g.reserve(); }); contender.join(); assert(rejected);
    assert(g.activate());
    std::atomic<bool> nonOwnerClosed{true};
    std::thread stranger([&]{nonOwnerClosed = g.close(0ms);}); stranger.join(); assert(!nonOwnerClosed);
    auto old = g.ticket(); assert(g.enter(old)); g.leave();
    assert(g.close(100ms)); assert(g.release());
    assert(g.reserve()); assert(g.activate());
    // A delayed reader holding an old ticket cannot enter a later generation.
    assert(!g.enter(old)); assert(g.enter(g.ticket())); g.leave();
    assert(g.close(100ms)); assert(g.release());

    KPRepeatGate draining;
    assert(draining.reserve() && draining.activate());
    std::atomic<bool> entered{false}, mayExit{false};
    std::thread reader([&]{auto t=draining.ticket(); assert(draining.enter(t)); entered=true;
                           while(!mayExit.load()) std::this_thread::yield(); draining.leave();});
    while(!entered.load()) std::this_thread::yield();
    std::thread releaseReader([&]{std::this_thread::sleep_for(5ms);mayExit=true;});
    assert(draining.close(500ms)); reader.join(); releaseReader.join(); assert(draining.release());

    KPRepeatGate timeout;
    assert(timeout.reserve() && timeout.activate());
    auto t=timeout.ticket(); assert(timeout.enter(t));
    assert(!timeout.close(0ms)); assert(timeout.poisoned());
    timeout.leave(); assert(timeout.release()); assert(!timeout.reserve());
    KPRepeatGate stress;
    std::atomic<bool> running{true}; std::atomic<unsigned> reads{0};
    std::thread workers[4];
    for(auto &worker:workers) worker=std::thread([&]{
        while(running.load()) { auto ticket=stress.ticket();
            if(stress.enter(ticket)) { ++reads; stress.leave(); }
        }
    });
    for(unsigned i=0;i<300;i++) {
        while(!stress.reserve()) std::this_thread::yield();
        assert(stress.activate());
        std::this_thread::sleep_for(100us);
        assert(stress.close(500ms));
        while(!stress.release()) std::this_thread::yield();
    }
    running=false; for(auto &worker:workers) worker.join(); assert(reads>0);
    std::printf("PASS repeat epochs, contention, drain, timeout and 300 concurrent cycles (%u reads)\n", reads.load());
}
