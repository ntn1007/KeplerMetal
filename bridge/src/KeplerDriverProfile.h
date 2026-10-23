// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>

// Whole-file digests only. CMS normalization is a diagnostic, never admission.
static inline BOOL KPKeplerDriverHashIsQualified(NSString *digest) {
 return digest && ([digest isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"] ||
                   [digest isEqual:@"e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645"]);
}
