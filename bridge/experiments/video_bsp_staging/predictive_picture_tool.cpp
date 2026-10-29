// SPDX-License-Identifier: MIT
#include "VideoIdr.h"
#include "VideoPredictive.h"
#include <array>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>
using namespace kepler::video;
static bool load(const std::string& path, std::vector<uint8_t>& v) {
    std::ifstream f(path,std::ios::binary|std::ios::ate); if(!f) return false;
    const auto n=f.tellg(); if(n<=0 || n>0x00ffffef) return false;
    f.seekg(0); v.resize(static_cast<size_t>(n));
    return static_cast<bool>(f.read(reinterpret_cast<char*>(v.data()),v.size()));
}
int main(int argc,char** argv) {
    if(argc!=5) return 2;
    std::vector<uint8_t> sps,pps,sample;
    if(!load(argv[1],sps)||!load(argv[2],pps)) return 3;
    std::array<ReferenceState,6> completed{};
    for(unsigned i=0;i<6;i++) {
        char filename[32]; std::snprintf(filename,sizeof filename,"frame-%03u.avcc",i);
        if(!load(std::string(argv[3])+"/"+filename,sample)) return 3;
        ParsedBaselinePicture p;
        if(!parse_baseline_picture(sps.data(),sps.size(),pps.data(),pps.size(),sample.data(),sample.size(),p) || p.frame_num!=i) return 4;
        PictureProposal out;
        if(!i) {
            if(!prepare_baseline_idr(p,0,1,out)) return 5;
        } else {
            std::array<ReferenceState,17> slots{};
            std::array<PictureReference,2> refs{};
            const unsigned count=i==1?1:2, first=i-count, target=i%3;
            for(unsigned j=0;j<count;j++) {
                const unsigned frame=first+j, slot=frame%3;
                slots[slot]=completed[frame]; refs[j].identity=completed[frame].identity;
                refs[j].slot=static_cast<uint8_t>(slot); refs[j].top=refs[j].bottom=true;
                refs[j].frame_index=frame; refs[j].top_order=refs[j].bottom_order=static_cast<int32_t>(frame*2);
            }
            slots[target].identity=i+1;
            if(!prepare_baseline_p(p,slots,refs,static_cast<uint8_t>(count),static_cast<uint8_t>(target),i+1,out)) return 6;
            char file[32]; std::snprintf(file,sizeof file,"p-%03u.bin",i);
            std::ofstream f(std::string(argv[4])+"/"+file,std::ios::binary|std::ios::trunc);
            if(!f || !f.write(reinterpret_cast<const char*>(out.bytes.data()),out.bytes.size())) return 7;
            std::printf("{\"frame\":%u,\"poc\":%u,\"refs\":%u,\"target_slot\":%u,\"simple\":%u,\"caps\":%u}\n",
                        i,p.poc_lsb,count,target,unsigned(p.p_simple_reference_controls),out.caps);
        }
        // Deliberately simulated completion for this CPU-only fixture model.
        completed[i]=out.target_after;
    }
    return 0;
}
