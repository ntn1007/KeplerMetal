// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
extern "C" __attribute__((noinline)) int kp_after_base(int x) { return x + 1; }
extern "C" void kp_cache_invoke(void *);
int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    if (argc == 3 && std::strcmp(argv[2], "wrong")) return 2;
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) return 3;
    auto marker = reinterpret_cast<void (*)(uintptr_t)>(dlsym(library, "KPCalibrationStart"));
    if (!marker) return 4;
    marker(reinterpret_cast<uintptr_t>(&kp_after_base) + (argc == 3 ? 1 : 0));
    alignas(8) unsigned char node[0x464] = {};
    node[8] = 'K'; node[0x463] = 0; kp_cache_invoke(node);
    node[8] = 0; node[0x463] = 1; kp_cache_invoke(node);
    node[8] = 'K'; node[0x463] = 1; kp_cache_invoke(node);
    kp_cache_invoke(reinterpret_cast<void *>(1));
    if (dlclose(library)) return 5;
    std::puts("CACHE_CPU_FINISHED");
    return 0;
}
