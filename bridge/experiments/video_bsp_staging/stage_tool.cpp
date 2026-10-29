// SPDX-License-Identifier: MIT
#include "H264Stream.h"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 4) return 2;
    char* end = nullptr;
    unsigned long chunk_size = std::strtoul(argv[3], &end, 10);
    if (!end || *end || !chunk_size) return 2;
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) return 3;
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(input)), {});
    if (input.bad()) return 3;
    std::vector<kepler::video::ByteChunk> chunks;
    for (size_t i = 0; i < data.size();) {
        size_t n = std::min<size_t>(chunk_size, data.size() - i);
        chunks.push_back({data.data() + i, n});
        i += n;
    }
    std::vector<uint8_t> result;
    if (kepler::video::stage_h264_stream(chunks.data(), chunks.size(), result) !=
        kepler::video::StagingStatus::ok) return 4;
    std::ofstream output(argv[2], std::ios::binary | std::ios::trunc);
    if (!output) return 5;
    output.write(reinterpret_cast<const char*>(result.data()), result.size());
    return output ? 0 : 5;
}
