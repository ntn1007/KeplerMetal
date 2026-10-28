// SPDX-License-Identifier: MIT
// Test-only synchronization. Neither event proves safe deallocation.
#pragma once
#include <mutex>
namespace kepler_witness {
enum class Decision { waiting, deliver, duplicate, rejected };
class RaceGate final {
 public:
  Decision root() { std::lock_guard<std::mutex> lock(mu_);if(root_)return Decision::duplicate;root_=true;return evaluate(); }
  Decision root_returned() { std::lock_guard<std::mutex> lock(mu_);if(rootReturned_)return Decision::duplicate;rootReturned_=true;return evaluate(); }
  Decision result(bool ok) { std::lock_guard<std::mutex> lock(mu_);if(result_)return Decision::duplicate;result_=true;ok_=ok;return evaluate(); }
 private:
  Decision evaluate() {
   if(result_&&!ok_)return Decision::rejected;
   if(!root_||!rootReturned_||!result_)return Decision::waiting;
   if(delivered_)return Decision::duplicate;
   delivered_=true;return Decision::deliver;
  }
  std::mutex mu_;bool root_=false,rootReturned_=false,result_=false,ok_=false,delivered_=false;
};
}
