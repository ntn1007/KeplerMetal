// SPDX-License-Identifier: MIT
// CPU-only test of the exact auxiliary-section digest gate.
#include "KeplerConditionalAux.h"
#include <cstdint>
#include <cstdio>

int main() {
 // Three observed offsets, encoded as little-endian words.
 unsigned char table[12]={0x98,0x02,0,0,0xb8,0x02,0,0,0x30,0x03,0,0};
 if(!KPConditionalAuxMatches(table,sizeof table,1))return 1;
 for(unsigned i=0;i<sizeof table;i++){
  table[i]^=1;if(KPConditionalAuxMatches(table,sizeof table,1))return 2;table[i]^=1;
 }
 if(KPConditionalAuxMatches(nullptr,sizeof table,1)||KPConditionalAuxMatches(table,11,1)||
    KPConditionalAuxMatches(table,13,1)||KPConditionalAuxMatches(table,12,0)||
    KPConditionalAuxMatches(table,12,2))return 3;
 std::puts("PASS: pinned section, 12 byte mutations, missing/duplicate/length refusals");
 return 0;
}
