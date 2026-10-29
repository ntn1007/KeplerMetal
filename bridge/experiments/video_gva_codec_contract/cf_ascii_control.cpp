// SPDX-License-Identifier: MIT
// Original CPU-only CoreFoundation control; no vendor code or GPU invocation.
#include <CoreFoundation/CoreFoundation.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

static bool convert(const char *input, bool want_success, size_t expected_length) {
    CFStringRef text = CFStringCreateWithCString(kCFAllocatorDefault, input, kCFStringEncodingUTF8);
    if (!text) return false;
    unsigned char storage[34]; std::memset(storage, 0xa5, sizeof(storage));
    Boolean ok = CFStringGetCString(text, reinterpret_cast<char *>(storage + 1), 32, kCFStringEncodingASCII);
    bool valid = (bool)ok == want_success && storage[0] == 0xa5 && storage[33] == 0xa5;
    if (want_success) valid = valid && std::strlen(reinterpret_cast<char *>(storage + 1)) == expected_length &&
                                   std::memcmp(storage + 1, input, expected_length) == 0;
    CFRelease(text);
    return valid;
}

int main() {
    const std::string short_value = "KM-SYNTH";
    const std::string thirty_one(31, 'A'), thirty_two(32, 'A');
    const bool good = convert(short_value.c_str(), true, 8) && convert(thirty_one.c_str(), true, 31) &&
                      convert(thirty_two.c_str(), false, 0) && convert("\xc3\xa9", false, 0);
    if (!good) return 1;
    std::puts("{\"status\":\"PASS\",\"synthetic_31_ascii_bytes\":true,\"synthetic_32_ascii_bytes_refused\":true,\"synthetic_non_ascii_refused\":true,\"guards_intact\":true,\"GPU_execution\":false,\"vendor_execution\":false}");
    return 0;
}
