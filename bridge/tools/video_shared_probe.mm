// SPDX-License-Identifier: MIT
// Bounded GeForce shared-client check: public IOKit open/close only, no external methods.
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <unistd.h>

static NSNumber *pciProperty(io_registry_entry_t entry, CFStringRef key) {
    CFTypeRef value = IORegistryEntrySearchCFProperty(entry, kIOServicePlane, key,
        kCFAllocatorDefault, kIORegistryIterateRecursively | kIORegistryIterateParents);
    NSNumber *result = nil;
    if (value && CFGetTypeID(value) == CFDataGetTypeID() && CFDataGetLength((CFDataRef)value) == 4) {
        const UInt8 *p = CFDataGetBytePtr((CFDataRef)value);
        result = @((uint32_t)p[0] | ((uint32_t)p[1] << 8) |
                   ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24));
    }
    if (value) CFRelease(value);
    return result;
}

int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 3 || (strcmp(argv[1], "inventory") && strcmp(argv[1], "shared"))) return 2;
    bool open = !strcmp(argv[1], "shared");
    const char *expectedClass = "nvAccelerator";
    uint32_t clientType = 6u;
    if (!argv[2][0] || strspn(argv[2], "0123456789") != strlen(argv[2])) return 2;
    errno = 0;
    char *end = nullptr;
    uint64_t target = strtoull(argv[2], &end, 10);
    if (errno || !end || *end || (open && !target)) return 2;
    NSMutableArray *rows = [NSMutableArray array];
    io_iterator_t iterator = IO_OBJECT_NULL;
    kern_return_t match = IOServiceGetMatchingServices(kIOMainPortDefault,
        IOServiceMatching(expectedClass), &iterator);
    io_service_t selected = IO_OBJECT_NULL;
    unsigned candidates = 0, inspected = 0;
    bool truncated = false;
    if (match == KERN_SUCCESS) {
        io_service_t service;
        while ((service = IOIteratorNext(iterator))) {
            if (++inspected > 16) { truncated = true; IOObjectRelease(service); break; }
            io_name_t name = {}, cls = {};
            uint64_t registry = 0;
            kern_return_t ns = IORegistryEntryGetName(service, name);
            kern_return_t cs = IOObjectGetClass(service, cls);
            kern_return_t rs = IORegistryEntryGetRegistryEntryID(service, &registry);
            NSNumber *vendor = pciProperty(service, CFSTR("vendor-id"));
            NSNumber *device = pciProperty(service, CFSTR("device-id"));
            bool candidate = !ns && !cs && !rs && registry == target &&
                !strcmp(cls, expectedClass) && vendor && device &&
                vendor.unsignedIntValue == 0x10de && device.unsignedIntValue == 0x1198;
            [rows addObject:@{@"name": @(name), @"class": @(cls), @"registry_ID": @(registry),
                @"name_status": @(ns), @"class_status": @(cs), @"registry_status": @(rs),
                @"vendor_ID": vendor ?: (id)[NSNull null], @"device_ID": device ?: (id)[NSNull null],
                @"candidate": @(candidate)}];
            if (candidate) {
                ++candidates;
                if (!selected) { IOObjectRetain(service); selected = service; }
            }
            IOObjectRelease(service);
        }
        IOObjectRelease(iterator);
    }
    NSMutableDictionary *result = [NSMutableDictionary dictionaryWithDictionary:@{
        @"mode": @(argv[1]), @"pid": @(getpid()), @"uid": @(getuid()), @"euid": @(geteuid()), @"matching_status": @(match), @"services": rows,
        @"requested_registry_ID": @(target),
        @"candidate_count": @(candidates), @"truncated": @(truncated),
        @"open_attempts": @0, @"connection_returned": @NO, @"close_attempts": @0,
        @"external_method_calls": @0, @"GPU_commands_submitted": @0,
        @"hardware_video_execution_proved": @NO, @"system_modified": @NO,
        @"user_client_type": @(clientType), @"special_exclusive_type_used": @NO,
        @"status": @"INVENTORY_ONLY"}];
    if (open) {
        result[@"status"] = @"TARGET_NOT_QUALIFIED";
        if (!match && !truncated && candidates == 1 && selected) {
            io_connect_t connection = IO_OBJECT_NULL;
            result[@"open_attempts"] = @1;
            kern_return_t status = IOServiceOpen(selected, mach_task_self(), clientType, &connection);
            result[@"open_status"] = @(status);
            result[@"connection_returned"] = @(connection != IO_OBJECT_NULL);
            if (connection) {
                result[@"close_attempts"] = @1;
                kern_return_t close = IOServiceClose(connection);
                result[@"close_status"] = @(close);
                result[@"status"] = !status && !close ? @"OPEN_CLOSED" : @"OPEN_OR_CLOSE_FAILED";
            } else {
                result[@"status"] = status ? @"OPEN_REFUSED" : @"INVALID_OPEN_RESULT";
            }
        }
    }
    if (selected) IOObjectRelease(selected);
    NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    if (!json) return 3;
    fwrite(json.bytes, 1, json.length, stdout); puts("");
    return [result[@"status"] isEqual:@"OPEN_OR_CLOSE_FAILED"] ||
        [result[@"status"] isEqual:@"INVALID_OPEN_RESULT"] ? 4 : 0;
} }
