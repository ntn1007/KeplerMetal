// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

extern "C" __attribute__((noinline)) int kp_after_base(int x) { return x + 1; }
extern "C" __attribute__((noinline)) int kp_after_constructor(int x) { return x * 2; }
int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) return 3;
    auto start = reinterpret_cast<void (*)(uintptr_t)>(dlsym(library, "KPCalibrationStart"));
    if (!start) return 4;
    uintptr_t base = reinterpret_cast<uintptr_t>(&kp_after_base);
    if (argc == 3 && !std::strcmp(argv[2], "wrong")) ++base;
    else if (argc == 3) return 6;
    start(base);
    int result = kp_after_constructor(kp_after_base(10));
    if (dlclose(library)) return 5;
    std::printf("cpu_value=%d\n", result);
    return result == 22 ? 0 : 1;
}
