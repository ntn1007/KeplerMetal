// SPDX-License-Identifier: MIT
// Separately compiled, process-owned test client; never use for other allocations.
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <atomic>
#include <cstddef>
#include <cstdint>
static std::atomic<uintptr_t> expected{0};
static std::atomic<size_t> expectedLength{0};
static std::atomic<unsigned> calls{0}, rejected{0};
static std::atomic<int> status{-1};
extern "C" bool KMClientConfigure(void* p,size_t n) {
 if(!p || n!=4096 || expected.load()!=0)return false;
 expectedLength.store(n); expected.store((uintptr_t)p); return true;
}
extern "C" void KMClientRelease(void* p,size_t n) {
 unsigned prior=calls.fetch_add(1);
 if(prior || (uintptr_t)p!=expected.load() || n!=expectedLength.load()) { rejected++; return; }
 status.store(mach_vm_deallocate(mach_task_self(),(mach_vm_address_t)(uintptr_t)p,n));
}
extern "C" unsigned KMClientCalls(){return calls.load();}
extern "C" unsigned KMClientRejected(){return rejected.load();}
extern "C" int KMClientStatus(){return status.load();}
