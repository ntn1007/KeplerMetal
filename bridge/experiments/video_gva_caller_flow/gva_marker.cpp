// SPDX-License-Identifier: MIT
// Own-process image marker; no vendor instructions are patched or called.
#include <CommonCrypto/CommonDigest.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <cstdint>
#include <cstring>
#include <unistd.h>

extern "C" void KPGVAReady(uintptr_t);
namespace {
bool activated = false;
bool readable(uintptr_t address, size_t length) {
    mach_vm_address_t begin = address;
    mach_vm_size_t span = 0;
    vm_region_basic_info_data_64_t info{};
    mach_msg_type_number_t count = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object = 0;
    kern_return_t result = mach_vm_region(mach_task_self(), &begin, &span,
        VM_REGION_BASIC_INFO_64, (vm_region_info_t)&info, &count, &object);
    if (object) mach_port_deallocate(mach_task_self(), object);
    return result == KERN_SUCCESS && (info.protection & VM_PROT_READ) &&
           address >= begin && length <= span && address - begin <= span - length;
}
bool hash_matches(uintptr_t base, size_t offset, size_t length, const unsigned char *wanted) {
    if (base > UINTPTR_MAX - offset || !readable(base + offset, length)) return false;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(reinterpret_cast<const void *>(base + offset), (CC_LONG)length, digest);
    return !std::memcmp(digest, wanted, sizeof(digest));
}
void added(const mach_header *header, intptr_t) {
    if (activated || !header || header->magic != MH_MAGIC_64) return;
    auto h = reinterpret_cast<const mach_header_64 *>(header);
    if (h->ncmds > 4096 || h->sizeofcmds > 16 * 1024 * 1024 ||
        !readable((uintptr_t)(h + 1), h->sizeofcmds)) return;
    const uint8_t *cursor = reinterpret_cast<const uint8_t *>(h + 1), *end = cursor + h->sizeofcmds;
    const uint8_t uuid[16] = {0xca,0x54,0x14,0xf3,0x69,0x37,0x3c,0x05,0x9e,0xa2,0xd8,0x2b,0x35,0xaf,0xd4,0xf0};
    bool matched = false;
    for (uint32_t i = 0; i < h->ncmds; ++i) {
        if ((size_t)(end - cursor) < sizeof(load_command)) return;
        auto lc = reinterpret_cast<const load_command *>(cursor);
        if (lc->cmdsize < sizeof(load_command) || lc->cmdsize > (size_t)(end - cursor)) return;
        if (lc->cmd == LC_UUID && lc->cmdsize >= sizeof(uuid_command))
            matched = !std::memcmp(reinterpret_cast<const uuid_command *>(lc)->uuid, uuid, sizeof(uuid));
        cursor += lc->cmdsize;
    }
    if (!matched || cursor != end) return;
    const unsigned char selector[32] = {0xcb,0x8e,0x85,0x19,0x7a,0x4b,0x37,0x27,0x0c,0xed,0x86,0xa0,0x70,0xfe,0xcb,0x85,0xbb,0x61,0xea,0x56,0xaa,0x98,0x89,0x29,0x96,0x65,0x8a,0x30,0x45,0x44,0xdb,0x0c};
    const unsigned char base[32] = {0xc4,0xef,0x1c,0x90,0xc5,0x2e,0x60,0x7a,0x30,0x7e,0x99,0x5c,0x03,0x68,0x90,0x37,0x6e,0xbf,0x95,0x9b,0xa9,0xad,0xe0,0x57,0x25,0xff,0x02,0xc5,0xcc,0x1b,0x72,0x73};
    const unsigned char init[32] = {0x80,0xad,0xc2,0x53,0x82,0xcc,0xad,0x97,0x1d,0x43,0x88,0xaf,0x6a,0xb6,0x16,0xae,0x65,0x20,0x0a,0xb9,0x34,0xd6,0x81,0x9a,0x7c,0xbd,0x54,0xc9,0xef,0xdb,0xa6,0x8f};
    const unsigned char enumeration[32] = {0x38,0x28,0x1d,0x04,0x7e,0xe2,0x61,0x12,0x75,0x50,0xcf,0xf9,0x64,0x95,0xd8,0xaa,0x7a,0x91,0x1f,0xe8,0x89,0xfb,0x6f,0x7a,0x6a,0xc2,0x99,0x2f,0x3b,0xbb,0x27,0x4c};
    const unsigned char context[32] = {0x2c,0xe4,0x5f,0xe6,0xc3,0xff,0xc5,0x91,0xe7,0x94,0xe4,0x66,0x55,0x39,0x3b,0xa2,0x84,0x85,0x40,0xf5,0x5c,0x89,0x1b,0xfb,0xf1,0xf1,0x89,0xe6,0xd0,0xe4,0xc9,0xe0};
    uintptr_t address = (uintptr_t)header;
    if (!hash_matches(address,115359,719,selector) || !hash_matches(address,117024,176,base) ||
        !hash_matches(address,232918,136,init) || !hash_matches(address,146236,112,enumeration) ||
        !hash_matches(address,262270,2452,context)) return;
    activated = true;
    static const char message[] = "KP_GVA_IMAGE_VALIDATED\n";
    (void)write(STDERR_FILENO, message, sizeof(message) - 1);
    KPGVAReady(address);
}
__attribute__((constructor)) void setup() { _dyld_register_func_for_add_image(added); }
}
