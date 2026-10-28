// SPDX-License-Identifier: MIT
// Own-process, nonprivileged bounded open/close experiment. This program has
// no path that submits an RM method, allocates a client or dispatches GPU work.
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach_vm.h>
#include <sys/sysctl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <dlfcn.h>
#include <unistd.h>
#include <cstring>
#include <cerrno>
#include <cstdlib>

#ifndef KM_LEASE_PATH
#error KM_LEASE_PATH must name the existing shared lab reservation file
#endif

static bool inheritedLease() {
    struct stat path{}, fdstat{};
    if (lstat(KM_LEASE_PATH, &path) || !S_ISREG(path.st_mode) || path.st_uid != getuid()) return false;
    int found = -1;
    for (int fd = 0; fd < 1024; ++fd) {
        if (!fstat(fd, &fdstat) && S_ISREG(fdstat.st_mode) &&
            fdstat.st_dev == path.st_dev && fdstat.st_ino == path.st_ino) {
            if (found != -1) return false;
            found = fd;
        }
    }
    return found >= 0 && !flock(found, LOCK_EX | LOCK_NB);
}

static NSString *sha(NSData *data) {
    if (!data || data.length > UINT32_MAX) return @"";
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, (CC_LONG)data.length, hash);
    NSMutableString *s = [NSMutableString string];
    for (unsigned char b : hash) [s appendFormat:@"%02x", b];
    return s;
}
static NSData *readable(uintptr_t address, size_t length) {
    mach_vm_address_t start = address; mach_vm_size_t size = 0;
    vm_region_basic_info_data_64_t info{};
    mach_msg_type_number_t count = VM_REGION_BASIC_INFO_COUNT_64; mach_port_t object = 0;
    auto kr = mach_vm_region(mach_task_self(), &start, &size, VM_REGION_BASIC_INFO_64,
                             (vm_region_info_t)&info, &count, &object);
    if (object) mach_port_deallocate(mach_task_self(), object);
    if (kr || !(info.protection & VM_PROT_READ) || address < start ||
        length > size || address - start > size - length) return nil;
    return [NSData dataWithBytes:(const void *)address length:length];
}
static bool pciProperty(io_registry_entry_t service, CFStringRef key, uint32_t expected) {
    CFTypeRef v = IORegistryEntrySearchCFProperty(service, kIOServicePlane, key,
        kCFAllocatorDefault, kIORegistryIterateRecursively | kIORegistryIterateParents);
    bool ok = v && CFGetTypeID(v) == CFDataGetTypeID() && CFDataGetLength((CFDataRef)v) == 4;
    if (ok) {
        const UInt8 *p = CFDataGetBytePtr((CFDataRef)v);
        ok = (uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) |
              (uint32_t(p[3]) << 24)) == expected;
    }
    if (v) CFRelease(v);
    return ok;
}
static int emit(NSDictionary *value) {
    NSData *json = [NSJSONSerialization dataWithJSONObject:value options:0 error:nil];
    if (!json) return 2;
    fwrite(json.bytes, 1, json.length, stdout); putchar('\n'); return 0;
}
int main(int argc, const char **argv) { @autoreleasepool {
    bool negative = argc == 3 && !strcmp(argv[1], "wrong-code-hash");
    bool openMode = argc == 3 && !strcmp(argv[1], "open");
    if (argc != 3 || (!negative && !openMode && strcmp(argv[1], "observe")) || getuid() != geteuid() || !getuid()) return 2;
    char *end = nullptr; errno = 0;
    unsigned long long requested = strtoull(argv[2], &end, 10);
    if (errno || end == argv[2] || *end || argv[2][0] == '-' || !requested) return 2;
    NSMutableDictionary *out = [@{@"status": @"PROFILE_REFUSED", @"mode": @(argv[1]),
        @"pid": @(getpid()), @"uid": @(getuid()), @"euid": @(geteuid()),
        @"files_checked": @0, @"resident_regions_checked": @0, @"registry_enumerated": @NO,
        @"open_attempts": @0, @"close_attempts": @0, @"RM_calls": @0, @"GPU_dispatches": @0} mutableCopy];
    if (!inheritedLease()) { out[@"status"] = @"LEASE_REQUIRED"; return emit(out); }
    out[@"lease_inherited"] = @YES;
    char uuid[128]{}; size_t uuidSize = sizeof(uuid);
    if (sysctlbyname("kern.uuid", uuid, &uuidSize, nullptr, 0) ||
        strcmp(uuid, "1291D44A-C0CD-3AC7-A9E4-CA2749B33959")) return emit(out);
    NSDictionary *files = @{
      @"/System/Library/Extensions/NVDAResman.kext/Contents/MacOS/NVDAResman": @"36396eaecd68ddbb0482f019f38ce55d01b10379ca829da7f19b3bd8f3e26808",
      @"/System/Library/Extensions/NVDAGK100Hal.kext/Contents/MacOS/NVDAGK100Hal": @"74575453948c834dba5f18e936a58f611f01c598955ecc0f1ff79a501971c99e",
      @"/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce": @"44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3",
      @"/System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2": @"37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8",
      @"/System/Library/Kernels/kernel": @"7004ebc1020a5c7e3f075c631507f31fdc0ce3fe02e9f01f42dce1d178770a08"};
    for (NSString *path in files) {
        if (![sha([NSData dataWithContentsOfFile:path]) isEqualToString:files[path]]) return emit(out);
        out[@"files_checked"] = @([out[@"files_checked"] unsignedIntValue] + 1);
    }
    Dl_info image{};
    if (!dladdr((void *)&IOConnectCallMethod, &image) || !image.dli_fbase || !image.dli_fname ||
        strcmp(image.dli_fname, "/System/Library/Frameworks/IOKit.framework/Versions/A/IOKit")) return emit(out);
    uintptr_t base = (uintptr_t)image.dli_fbase;
    const struct { const char *name; size_t offset, size; const char *hash; } regions[] = {
      {"IOConnectCallStructMethod", 15179, 64, "17a826f50a52d154b14b48e5018a98c24712f35313cff2bdab0d830b38a5e4a7"},
      {"IOConnectCallMethod", 10532, 293, "89593866f8f728564c03c6570dc0dbd20516b1b4ef0c156a00120366dc815167"},
      {nullptr, 10825, 929, "d6cb2836fa4265408028cf67bb0c61155dbbb8ca40fc457ee80d51b5074b3560"}};
    for (unsigned i = 0; i < 3; ++i) {
        const auto &f = regions[i];
        if (base > UINTPTR_MAX - f.offset || (f.name && dlsym(RTLD_DEFAULT, f.name) != (void *)(base + f.offset))) return emit(out);
        NSString *expected = negative && i == 0 ? @"invalid" : @(f.hash);
        if (![sha(readable(base + f.offset, f.size)) isEqualToString:expected]) return emit(out);
        out[@"resident_regions_checked"] = @(i + 1);
    }
    io_iterator_t it = 0; out[@"registry_enumerated"] = @YES;
    if (IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("NVDA"), &it)) return emit(out);
    io_service_t s = 0, chosen = 0; unsigned matches = 0, selected = 0, total = 0; bool truncated = false;
    while ((s = IOIteratorNext(it))) {
        if (++total > 16) { truncated = true; IOObjectRelease(s); break; }
        io_name_t cls{}; uint64_t id = 0;
        if (!IOObjectGetClass(s, cls) && !strcmp(cls, "NVDA") &&
            !IORegistryEntryGetRegistryEntryID(s, &id) && id &&
            pciProperty(s, CFSTR("vendor-id"), 0x10de) && pciProperty(s, CFSTR("device-id"), 0x1198)) {
            ++matches;
            if (id == requested) {
                io_registry_entry_t parent = 0; io_name_t name{}, parentClass{};
                if (!IORegistryEntryGetParentEntry(s, kIOServicePlane, &parent)) {
                    if (!IOObjectGetClass(parent, parentClass) && !strcmp(parentClass, "IONDRVDevice") &&
                        !IORegistryEntryGetName(parent, name) && !strcmp(name, "NVDA,Display-A")) {
                        ++selected;
                        if (!chosen) { chosen = s; IOObjectRetain(chosen); }
                    }
                    IOObjectRelease(parent);
                }
            }
        }
        IOObjectRelease(s);
    }
    IOObjectRelease(it);
    out[@"matching_NVDA_services"] = @(matches); out[@"selected_NVDA_services"] = @(selected);
    out[@"truncated"] = @(truncated);
    if (truncated || selected != 1) { if (chosen) IOObjectRelease(chosen); return emit(out); }
    out[@"registry_id"] = @(requested); out[@"parent_name"] = @"NVDA,Display-A";
    out[@"status"] = @"PROFILE_OBSERVED_NO_OPEN";
    if (openMode) {
        io_connect_t connection = IO_OBJECT_NULL;
        out[@"open_attempts"] = @1;
        kern_return_t kr = IOServiceOpen(chosen, mach_task_self(), 0x80000000u, &connection);
        out[@"open_status"] = @(kr); out[@"connection_returned"] = @(connection != IO_OBJECT_NULL);
        out[@"status"] = @"OPEN_UNCONFIRMED";
        if (connection != IO_OBJECT_NULL) {
            out[@"close_attempts"] = @1;
            kern_return_t closed = IOServiceClose(connection); out[@"close_status"] = @(closed);
            if (kr == KERN_SUCCESS && closed == KERN_SUCCESS) out[@"status"] = @"OPEN_CLOSED";
        } else if (kr != KERN_SUCCESS) out[@"status"] = @"OPEN_REFUSED_NO_CONNECTION";
    }
    IOObjectRelease(chosen);
    return emit(out);
} }
