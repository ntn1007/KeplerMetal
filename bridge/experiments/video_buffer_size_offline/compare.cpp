// SPDX-License-Identifier: MIT
// Executes only a hash-checked, position-restored CPU helper supplied locally.
// It never opens an IOKit connection or accesses a GPU.
#include <array>
#include <CommonCrypto/CommonDigest.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <sys/mman.h>
#include <unistd.h>

static void put64(uint8_t* p, uint64_t v) { std::memcpy(p,&v,8); }
static void put32(uint8_t* p, uint32_t v) { std::memcpy(p,&v,4); }
static uint64_t align_up(uint64_t v, uint64_t page) { return (v+page-1)&~(page-1); }
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    std::array<uint8_t,145> code{}; std::ifstream f(argv[1],std::ios::binary|std::ios::ate);
    if(!f || f.tellg()!=static_cast<std::streamoff>(code.size())) return 3;
    f.seekg(0); if(!f.read(reinterpret_cast<char*>(code.data()),code.size())) return 4;
    constexpr std::array<uint8_t,CC_SHA256_DIGEST_LENGTH> pinned={
        0x1e,0x5a,0x4c,0x35,0xd4,0xb2,0x8e,0x5d,0xca,0x9e,0x0b,0x5c,0x33,0xc4,0x0e,0x6a,
        0x70,0x6b,0x2b,0x04,0x47,0x52,0x3f,0xb9,0xcf,0xb2,0x75,0xe1,0xba,0xc1,0x95,0x4f};
    std::array<uint8_t,CC_SHA256_DIGEST_LENGTH> digest{};
    CC_SHA256(code.data(),static_cast<CC_LONG>(code.size()),digest.data());
    if(digest!=pinned) return 9;
    constexpr size_t map_size=0x70000, entry=0x9ede, global_page_slot=0x6a108;
    auto* image=static_cast<uint8_t*>(mmap(nullptr,map_size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0));
    if(image==MAP_FAILED) return 5;
    uint64_t page=4096; const uint64_t* page_ptr=&page;
    std::memcpy(image+entry,code.data(),code.size()); std::memcpy(image+global_page_slot,&page_ptr,sizeof page_ptr);
    if(mprotect(image,map_size,PROT_READ|PROT_EXEC)!=0) return 6;
    using Fn=void (*)(void*,uint32_t,uint64_t); auto fn=reinterpret_cast<Fn>(image+entry);
    constexpr uint64_t initial=65536, maximum=524288;
    constexpr uint64_t edge[]={0,57343,57344,57345,65535,65536,122879,122880,122881,131072,516095,516096,516097,524288,0xffffffff};
    for(unsigned i=0;i<4096;++i) {
        const uint32_t slot=i&1; page=(i&2)?16384:4096;
        const uint64_t request=i<sizeof(edge)/sizeof(edge[0])?edge[i]:(uint64_t(i)*7919)%1100000;
        alignas(8) std::array<uint8_t,0x1000> actual; actual.fill(0xa5);
        const size_t base=0x6e0+slot*0x90;
        put64(actual.data()+base+0x18,initial); put64(actual.data()+base+0x20,maximum);
        put32(actual.data()+base+0x7c,2);
        auto expected=actual;
        uint64_t value=initial, previous=0, threshold=request+8192;
        if(value<threshold && value<maximum) {
            do { previous=value; value*=2; } while(value<threshold && value<maximum);
        }
        const uint64_t output=align_up(value<maximum?value:maximum,page);
        const uint64_t other=previous>8192?align_up(previous,page)-8192:0;
        put64(expected.data()+base,output); put64(expected.data()+base+8,other);
        fn(actual.data(),slot,request);
        if(actual!=expected) { std::fprintf(stderr,"mismatch case %u slot %u\n",i,slot); return 7; }
    }
    if(munmap(image,map_size)) return 8;
    std::puts("PASS: 4096 original CPU helper comparisons and guarded context bytes");
}
