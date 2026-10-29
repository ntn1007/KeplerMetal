// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>
#define KM_MAX_SERVICES 32
#define KM_MAX_EVENTS 1024
#define KM_UNKNOWN_SERVICE UINT32_MAX
struct KMService { char class_name[128], registry_name[128]; uint32_t type; };
struct KMEvent { uint32_t kind, selector, service; };
struct KMDetails { uint32_t service_count, event_count, dropped; struct KMService services[KM_MAX_SERVICES]; struct KMEvent events[KM_MAX_EVENTS]; };
