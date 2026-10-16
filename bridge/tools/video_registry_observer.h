// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>
extern "C" {
NSString *KPRegistryLibraryKind();
void *KPRegistryOriginal(unsigned);
void *KPRegistryTail(unsigned);
bool KPRegistrySetSyntheticTarget(void *);
bool KPRegistryEnable(bool);
NSDictionary *KPRegistrySnapshot();
uint64_t KPRegistryTestFlagsCall(void *,uint64_t);
uint64_t KPRegistryTestFlagsOriginal();
}
