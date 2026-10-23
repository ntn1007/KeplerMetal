// SPDX-License-Identifier: MIT
#import "KeplerCPUICB.h"
#import "KeplerFP64.h"
#import "KeplerNativeCAS.h"
#import "KeplerNativeCommands.h"
#import "KeplerNativeRenderDraws.h"
#import "KeplerProgramImport.h"
#import "KeplerDriverProfile.h"
#include <cstdio>

// The linker loads the whole archive. No device, resource, queue or pipeline
// is created, and no GPU method is invoked by this executable.
int main() {
    @autoreleasepool {
        if (!KPKeplerDriverHashIsQualified(@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054") ||
            !KPKeplerDriverHashIsQualified(@"e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645") ||
            KPKeplerDriverHashIsQualified(nil) || KPKeplerDriverHashIsQualified(@"") ||
            KPKeplerDriverHashIsQualified(@"2b89839c") ||
            KPKeplerDriverHashIsQualified(@"0000000000000000000000000000000000000000000000000000000000000000")) return 1;
    }
    std::puts("KeplerMetal full archive link: PASS; GPU execution: NOT RUN");
    return 0;
}
