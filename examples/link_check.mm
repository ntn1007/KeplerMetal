// SPDX-License-Identifier: MIT
#import "KeplerCPUICB.h"
#import "KeplerFP64.h"
#import "KeplerNativeCAS.h"
#import "KeplerNativeCommands.h"
#import "KeplerNativeRenderDraws.h"
#import "KeplerProgramImport.h"
#include <cstdio>

// The linker loads the whole archive. No device, resource, queue or pipeline
// is created, and no GPU method is invoked by this executable.
int main() {
    std::puts("KeplerMetal full archive link: PASS; GPU execution: NOT RUN");
    return 0;
}
