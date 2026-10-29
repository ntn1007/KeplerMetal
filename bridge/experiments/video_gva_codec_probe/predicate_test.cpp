// SPDX-License-Identifier: MIT
#include "predicate.h"
#include <cassert>
#include <cstdio>
int main(){
    assert(KPCodecProbeAllowed("synthetic",true,150812,true,true,true,true,0));
    assert(!KPCodecProbeAllowed("off",true,150812,true,true,true,true,0));
    assert(!KPCodecProbeAllowed(nullptr,true,150812,true,true,true,true,0));
    assert(!KPCodecProbeAllowed("synthetic",false,150812,true,true,true,true,0));
    assert(!KPCodecProbeAllowed("synthetic",true,150813,true,true,true,true,0));
    assert(!KPCodecProbeAllowed("synthetic",true,150812,false,true,true,true,0));
    assert(!KPCodecProbeAllowed("synthetic",true,150812,true,false,true,true,0));
    assert(!KPCodecProbeAllowed("synthetic",true,150812,true,true,false,true,0));
    assert(!KPCodecProbeAllowed("synthetic",true,150812,true,true,true,false,0));
    assert(!KPCodecProbeAllowed("synthetic",true,150812,true,true,true,true,1));
    std::puts("PASS one synthetic property predicate and nine refusals");
}
