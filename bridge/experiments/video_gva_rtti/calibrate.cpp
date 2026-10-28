// SPDX-License-Identifier: MIT
// CPU-only ABI reference using project-owned test classes; no vendor code.
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <typeinfo>

struct Flow { virtual ~Flow()=default; virtual int value() const {return 3;} };
struct Flow_QT0 : Flow { int value() const override {return 7;} };
int main(){
    static_assert(sizeof(void*)==8,"64-bit ABI required");
    Flow_QT0 object;const void *vptr=nullptr;
    std::memcpy(&vptr,static_cast<const void*>(&object),sizeof(vptr));
    const std::type_info *info=nullptr;
    std::memcpy(&info,static_cast<const char*>(vptr)-sizeof(void*),sizeof(info));
    const void *typeVptr=nullptr;const std::type_info *base=nullptr;
    std::memcpy(&typeVptr,static_cast<const void*>(info),sizeof(typeVptr));
    std::memcpy(&base,reinterpret_cast<const char*>(info)+2*sizeof(void*),sizeof(base));
    Dl_info symbol{};
    if(info!=&typeid(Flow_QT0)||!dladdr(typeVptr,&symbol)||!symbol.dli_sname||
       !std::strstr(symbol.dli_sname,"__si_class_type_info")||base!=&typeid(Flow)||
       std::strcmp(info->name(),"8Flow_QT0")||std::strcmp(base->name(),"4Flow")||object.value()!=7)return 1;
    std::puts("{\"status\":\"PASS\",\"vtable_minus_one_slot_is_typeinfo\":true,\"single_base_name\":\"Flow\",\"derived_name\":\"Flow_QT0\",\"GPU_execution\":false,\"vendor_execution\":false}");
}
