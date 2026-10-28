// SPDX-License-Identifier: MIT
// Observe the public experimental operation; never mutate native classes here.
#import <objc/message.h>
static bool witnessBlock(id cb,SEL s){@try{((void(*)(id,SEL))objc_msgSend)(cb,s);}@catch(NSException*x){return [x.name isEqual:@"KeplerAbandonedCommandBuffer"];}return false;}
