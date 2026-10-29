// SPDX-License-Identifier: MIT
#include "VideoIdr.h"
#include <cstdio>
#include <fstream>
#include <vector>
static bool load(const char* path,std::vector<uint8_t>& v) {
    std::ifstream f(path,std::ios::binary|std::ios::ate); if(!f) return false;
    const auto n=f.tellg(); if(n<=0 || n>0x00ffffef) return false;
    f.seekg(0); v.resize(static_cast<size_t>(n));
    return static_cast<bool>(f.read(reinterpret_cast<char*>(v.data()),v.size()));
}
int main(int argc,char** argv) {
    if(argc!=5) return 2;
    std::vector<uint8_t> sps,pps,sample;
    if(!load(argv[1],sps)||!load(argv[2],pps)||!load(argv[3],sample)) return 3;
    kepler::video::ParsedBaselinePicture p;
    if(!kepler::video::parse_baseline_picture(sps.data(),sps.size(),pps.data(),pps.size(),sample.data(),sample.size(),p)) return 4;
    kepler::video::PictureProposal out;
    if(!kepler::video::prepare_baseline_idr(p,0,1,out)) return 5;
    std::ofstream f(argv[4],std::ios::binary|std::ios::trunc);
    if(!f || !f.write(reinterpret_cast<const char*>(out.bytes.data()),out.bytes.size())) return 6;
    std::printf("{\"is_idr\":%u,\"is_reference\":%u,\"chroma_qp_offset\":%d,\"constrained_intra\":%u,"
                "\"delta_poc_bottom\":%d,\"no_output_prior\":%u,\"long_term\":%u,\"caps\":%u}\n",
                unsigned(p.is_idr),unsigned(p.is_reference),int(p.chroma_qp_offset),unsigned(p.constrained_intra),
                p.delta_poc_bottom,unsigned(p.idr_no_output_prior),unsigned(p.idr_long_term),out.caps);
}
