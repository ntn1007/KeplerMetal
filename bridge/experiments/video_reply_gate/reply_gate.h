// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>
#include <cstdint>

// This checks lengths only; it cannot establish resource validity or ownership.
namespace kepler_video {
constexpr size_t header_bytes=48, max_reply_bytes=4096;
enum class ReplyDisposition { backend_failure, accept, reject_length, reject_profile };
inline ReplyDisposition checkReply(int32_t backendStatus,size_t capacity,size_t reported,size_t privateBytes){
    if(backendStatus!=0)return ReplyDisposition::backend_failure;
    if(privateBytes>max_reply_bytes-header_bytes || capacity!=header_bytes+privateBytes)return ReplyDisposition::reject_profile;
    return reported==capacity?ReplyDisposition::accept:ReplyDisposition::reject_length;
}
}
