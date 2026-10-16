// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>
extern "C" bool KPRegistryMetadataBegin(uintptr_t,uintptr_t);
extern "C" void KPRegistryMetadataControl(bool);
extern "C" NSDictionary *KPRegistryMetadataSnapshot();
