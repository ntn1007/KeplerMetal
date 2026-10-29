// SPDX-License-Identifier: MIT
#include <cstdint>
extern "C" void KPGVAReady(uintptr_t);
extern "C" void KPCalibrationStart(uintptr_t base) { KPGVAReady(base); }
