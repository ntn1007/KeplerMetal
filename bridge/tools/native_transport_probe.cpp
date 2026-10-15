#include "IOKitKeplerBridge.h"
#include <cstdio>
int main(){KBInfo info;KBContext*c=kb_open(&info);if(!c)return 1;
 int submit=kb_submit_native(c,nullptr,0);
 printf("{\"registry_id\":%llu,\"pci_vendor\":%u,\"pci_device\":%u,\"opened_client_mask\":%u,\"shared_device_bytes\":%llu,\"shared_resource_bytes\":%llu,\"native_submission_supported\":%s,\"submit_result\":%d,\"scope\":\"direct IOKit connection and mappings, no GPU packet submitted\"}\n",(unsigned long long)info.registry_id,info.pci_vendor,info.pci_device,info.opened_client_mask,(unsigned long long)info.shared_device_bytes,(unsigned long long)info.shared_resource_bytes,info.native_submission_supported?"true":"false",submit);kb_close(c);return submit==KB_NATIVE_SUBMISSION_NOT_IMPLEMENTED?0:2;}
