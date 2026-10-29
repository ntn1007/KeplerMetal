// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
extern "C" __attribute__((noinline)) void kp_failure_path() { asm volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) void kp_gva_exit() { asm volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) void kp_vt_return() { asm volatile("" ::: "memory"); }
extern "C" void kp_invoke_error_path(int);
int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) return 3;
    auto start = reinterpret_cast<void (*)(uintptr_t)>(dlsym(library, "KPCalibrationStart"));
    if (!start) return 4;
    uintptr_t base = reinterpret_cast<uintptr_t>(&kp_failure_path);
    bool zero = argc == 3 && !std::strcmp(argv[2], "zero");
    if (argc == 3 && !std::strcmp(argv[2], "wrong")) ++base;
    else if (argc == 3 && !zero) return 6;
    start(base);
    kp_invoke_error_path(zero ? 0 : -12913);
    if (dlclose(library)) return 5;
    std::printf("cpu_value=22\n");
    return 0;
}
