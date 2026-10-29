// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>
#define KM_MAX_SERVICES 32
#define KM_MAX_EVENTS 1024
#define KM_UNKNOWN_SERVICE UINT32_MAX
struct KMService { char class_name[128], registry_name[128]; uint32_t type; };
// Length flags distinguish an unavailable pointer read from a legitimate zero.
struct KMEvent {
    uint32_t kind, selector, service, flags, input_scalars;
    int32_t status;
    uint64_t ticket, input_struct, scalar_capacity, scalar_returned, struct_capacity, struct_returned;
    uint64_t caller_offset;
    char caller_image[128], caller_symbol[128];
};
struct KMDetails { uint32_t service_count, event_count, dropped; struct KMService services[KM_MAX_SERVICES]; struct KMEvent events[KM_MAX_EVENTS]; };
