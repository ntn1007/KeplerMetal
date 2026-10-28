// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

extern "C" __attribute__((noinline)) int kp_after_base(int x) { return x + 1; }
extern "C" __attribute__((noinline)) int kp_after_constructor(int x) { return x * 2; }
extern "C" __attribute__((noinline)) void kp_after_enumeration() { asm volatile("" ::: "memory"); }
extern "C" void kp_invoke_after_enumeration(void *);
int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) return 3;
    auto start = reinterpret_cast<void (*)(uintptr_t)>(dlsym(library, "KPCalibrationStart"));
    if (!start) return 4;
    uintptr_t base = reinterpret_cast<uintptr_t>(&kp_after_base);
    bool badptr = argc == 3 && !std::strcmp(argv[2], "badptr");
    if (argc == 3 && !std::strcmp(argv[2], "wrong")) ++base;
    else if (argc == 3 && !badptr) return 6;
    start(base);
    int result = kp_after_constructor(kp_after_base(10));
    uint32_t count = 7;
    kp_invoke_after_enumeration(badptr ? reinterpret_cast<void *>(1) : &count);
    if (dlclose(library)) return 5;
    std::printf("cpu_value=%d\n", result);
    return result == 22 ? 0 : 1;
}
