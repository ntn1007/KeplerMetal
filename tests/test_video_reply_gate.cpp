// SPDX-License-Identifier: MIT
#include "../bridge/experiments/video_reply_gate/reply_gate.h"
#include <cassert>
#include <initializer_list>
#include <limits>
using kepler_video::ReplyDisposition;
using kepler_video::checkReply;
int main(){
  for(size_t returned: {size_t(0),size_t(47),size_t(48),size_t(50)})
    assert(checkReply(0,49,returned,1)==ReplyDisposition::reject_length);
  assert(checkReply(0,49,49,1)==ReplyDisposition::accept);
  assert(checkReply(0,48,48,0)==ReplyDisposition::accept);
  assert(checkReply(-1,49,48,1)==ReplyDisposition::backend_failure);
  assert(checkReply(0,48,48,1)==ReplyDisposition::reject_profile);
  assert(checkReply(0,4097,4097,4049)==ReplyDisposition::reject_profile);
  assert(checkReply(0,0,0,std::numeric_limits<size_t>::max())==ReplyDisposition::reject_profile);
}
