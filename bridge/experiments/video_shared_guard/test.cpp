// SPDX-License-Identifier: MIT
#include "SharedAliasGuard.h"
#include <cassert>
#include <limits>
using namespace kepler_video;
int main(){
 AliasEvidence good{true,true,true,true,true,0,0,1,2};assert(allowsReferenceRelease(good));
 auto v=good;v.extra_acquired=false;assert(!allowsReferenceRelease(v));v=good;v.same_name=false;assert(!allowsReferenceRelease(v));
 v=good;v.metal_self_equal=false;assert(!allowsReferenceRelease(v));v=good;v.extra_self_equal=false;assert(!allowsReferenceRelease(v));
 v=good;v.object_equal=false;assert(!allowsReferenceRelease(v));v=good;v.before_status=1;assert(!allowsReferenceRelease(v));
 v=good;v.opened_status=1;assert(!allowsReferenceRelease(v));v=good;v.before_refs=0;v.opened_refs=1;assert(!allowsReferenceRelease(v));
 v=good;v.opened_refs=3;assert(!allowsReferenceRelease(v));v=good;v.before_refs=std::numeric_limits<uint32_t>::max();v.opened_refs=0;assert(!allowsReferenceRelease(v));
}
