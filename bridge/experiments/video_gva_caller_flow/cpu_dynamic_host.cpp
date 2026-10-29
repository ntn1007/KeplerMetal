// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
extern "C" __attribute__((noinline)) void kp_after_dispatch() { asm volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) void kp_failure_path() { asm volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) void kp_nonempty_path() { asm volatile("" ::: "memory"); }
extern "C" void kp_invoke_after_dispatch(void *, int, int);
int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) return 3;
    auto start = reinterpret_cast<void (*)(uintptr_t)>(dlsym(library, "KPCalibrationStart"));
    if (!start) return 4;
    uintptr_t base = reinterpret_cast<uintptr_t>(&kp_after_dispatch);
    bool badptr = argc == 3 && !std::strcmp(argv[2], "badptr");
    bool success = argc == 3 && !std::strcmp(argv[2], "success");
    if (argc == 3 && !std::strcmp(argv[2], "wrong")) ++base;
    else if (argc == 3 && !badptr && !success) return 6;
    start(base);
    uint32_t count = success ? 1 : 0;
    kp_invoke_after_dispatch(badptr ? reinterpret_cast<void *>(1) : &count, success ? 0 : 1, success);
    if (dlclose(library)) return 5;
    std::printf("cpu_value=22\n");
    return 0;
}
