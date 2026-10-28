// SPDX-License-Identifier: MIT
#include "GuardedAliasBackend.h"
namespace kepler_video {
bool GuardedAliasBackend::configured() const noexcept {
 return metal_ && ops_.open && ops_.refs && ops_.equal && ops_.associate && ops_.closeContext && ops_.releaseShared;
}
int GuardedAliasBackend::openCallback(void *p,Handle service,uint32_t type,Handle *out) noexcept {
 auto&s=*static_cast<GuardedAliasBackend*>(p); if(!out)return GuardInvalid; *out=0;
 if(!s.configured()||!service){s.report_.rejected=true;return GuardInvalid;}
 if(type==3){if(s.context_attempted_){s.report_.rejected=true;return GuardRefused;}s.context_attempted_=true;}
 else if(type==6){
  if(!s.context_||s.context_closed_||s.shared_attempted_){s.report_.rejected=true;return GuardRefused;}s.shared_attempted_=true;
  s.report_.before_status=s.ops_.refs(s.ops_.user,s.metal_,&s.report_.before);
  if(s.report_.before_status||!s.report_.before){s.report_.rejected=true;return GuardRefused;}
 }else{s.report_.rejected=true;return GuardRefused;}
 Handle result=0;int status=s.ops_.open(s.ops_.user,service,type,&result);
 if(status){if(result)s.report_.ambiguous_output=true;return status;}
 if(!result)return GuardInvalid;
 if(type==3){if(result==s.metal_){s.report_.rejected=true;s.report_.unreleased=true;return GuardRefused;}s.context_=result;*out=result;return 0;}
 s.extra_=result;s.report_.opened_status=s.ops_.refs(s.ops_.user,s.metal_,&s.report_.opened);
 s.report_.same_name=result==s.metal_;s.report_.metal_self=s.ops_.equal(s.ops_.user,s.metal_,s.metal_);
 s.report_.extra_self=s.ops_.equal(s.ops_.user,result,result);
 s.report_.object_equal=s.report_.metal_self&&s.report_.extra_self&&s.ops_.equal(s.ops_.user,s.metal_,result);
 s.report_.qualified=allowsReferenceRelease({true,s.report_.same_name,s.report_.metal_self,s.report_.extra_self,s.report_.object_equal,s.report_.before_status,s.report_.opened_status,s.report_.before,s.report_.opened});
 if(!s.report_.qualified||result==s.context_){s.report_.rejected=true;s.report_.unreleased=true;return GuardRefused;}
 *out=result;return 0;
}
int GuardedAliasBackend::associateCallback(void *p,Handle context,Handle shared) noexcept {
 auto&s=*static_cast<GuardedAliasBackend*>(p);
 if(!s.configured()||!s.report_.qualified||s.context_closed_||s.shared_closed_||context!=s.context_||shared!=s.extra_){s.report_.rejected=true;return GuardRefused;}
 return s.ops_.associate(s.ops_.user,context,shared);
}
int GuardedAliasBackend::closeCallback(void *p,Handle handle) noexcept {
 auto&s=*static_cast<GuardedAliasBackend*>(p);
 if(!s.configured()){s.report_.rejected=true;return GuardInvalid;}
 if(handle&&handle==s.context_&&!s.context_closed_){s.context_closed_=true;int status=s.ops_.closeContext(s.ops_.user,handle);s.context_close_ok_=status==0;return status;}
 if(!handle||handle!=s.extra_||!s.report_.qualified||!s.context_closed_||s.shared_closed_){s.report_.rejected=true;return GuardRefused;}
 s.shared_closed_=true;if(!s.context_close_ok_){s.report_.rejected=true;s.report_.unreleased=true;return GuardRefused;}
 s.report_.before_close_status=s.ops_.refs(s.ops_.user,s.metal_,&s.report_.before_close);
 if(s.report_.before_close_status||s.report_.before_close!=s.report_.opened){s.report_.rejected=true;s.report_.unreleased=true;return GuardRefused;}
 int status=s.ops_.releaseShared(s.ops_.user,handle);
 if(status)s.report_.unreleased=true; // Error leaves ownership uncertain; no retry.
 s.report_.after_status=s.ops_.refs(s.ops_.user,s.metal_,&s.report_.after);
 if(!status&&(s.report_.after_status||s.report_.after!=s.report_.before)){s.report_.postcondition_failed=true;return GuardRefused;}
 return status;
}
}
