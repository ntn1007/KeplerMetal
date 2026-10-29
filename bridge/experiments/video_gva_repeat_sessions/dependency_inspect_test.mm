// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#include "video_dependency.h"
#include <cstdio>
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=2)return 1;
    for(unsigned i=0;i<3;i++){
        NSDictionary *r=KPVideoDependencyInspect(@(argv[1]));
        if(![r[@"status"]isEqual:@"COMPLETE"]||![r[@"public_query_controls_valid"]boolValue]||
           ![r[@"recorders_drained"]boolValue]||[r[@"pending"]unsignedIntValue]||
           [r[@"dropped"]unsignedIntValue]||[r[@"calls"]unsignedIntValue]!=2||
           [r[@"substitutions"]unsignedIntValue]||![r[@"profile"][@"scope_contract_valid"]boolValue]||
           [r[@"public_create_called"]boolValue])return 2;
    }
    std::puts("PASS three pinned-profile inspection scopes and six public IOKit controls");return 0;
}}
