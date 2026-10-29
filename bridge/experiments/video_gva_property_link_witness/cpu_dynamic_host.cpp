// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

extern "C" __attribute__((noinline)) int kp_after_base(int x) { return x + 1; }
extern "C" __attribute__((noinline)) int kp_after_constructor(int x) { return x * 2; }
extern "C" __attribute__((noinline)) void kp_after_enumeration() { asm volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) void kp_list_entry() { asm volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) void kp_property_return() { asm volatile("" ::: "memory"); }
extern "C" void kp_invoke_after_enumeration(void *, uintptr_t, uint32_t, uintptr_t, uintptr_t);
int main(int argc, char **argv) {
    if (argc != 2 && argc != 3) return 2;
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) return 3;
    auto start = reinterpret_cast<void (*)(uintptr_t)>(dlsym(library, "KPCalibrationStart"));
    if (!start) return 4;
    uintptr_t base = reinterpret_cast<uintptr_t>(&kp_after_base);
    bool badptr = argc == 3 && !std::strcmp(argv[2], "badptr");
    bool emptyhead = argc == 3 && !std::strcmp(argv[2], "emptyhead");
    bool cycle = argc == 3 && !std::strcmp(argv[2], "cycle");
    bool present = argc == 3 && !std::strcmp(argv[2], "present");
    bool different = argc == 3 && !std::strcmp(argv[2], "different");
    if (argc == 3 && !std::strcmp(argv[2], "wrong")) ++base;
    else if (argc == 3 && !badptr && !emptyhead && !cycle && !present && !different) return 6;
    start(base);
    int result = kp_after_constructor(kp_after_base(10));
    uint32_t count = 7;
    alignas(8) unsigned char node1[0x464] = {}, node2[0x464] = {};
    uintptr_t next1 = reinterpret_cast<uintptr_t>(node2), next2 = cycle ? reinterpret_cast<uintptr_t>(node1) : 0;
    uint32_t class1 = 0x1080001, class2 = 0x1020000;
    std::memcpy(node1, &next1, sizeof(next1)); std::memcpy(node2, &next2, sizeof(next2));
    std::memcpy(node1 + 0x428, &class1, sizeof(class1)); std::memcpy(node2 + 0x428, &class2, sizeof(class2));
    node1[0x463] = 1; node2[0x461] = 1;
    kp_invoke_after_enumeration(badptr ? reinterpret_cast<void *>(1) : &count,
                                emptyhead ? 0 : reinterpret_cast<uintptr_t>(node1), emptyhead ? 0 : 1,
                                present ? 0x1234 : 0,
                                emptyhead ? 0 : reinterpret_cast<uintptr_t>(different ? node2 : node1));
    if (dlclose(library)) return 5;
    std::printf("cpu_value=%d\n", result);
    return result == 22 ? 0 : 1;
}
