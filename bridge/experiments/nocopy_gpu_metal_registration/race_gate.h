// SPDX-License-Identifier: MIT
// Explicitly registered work only; cannot detect missing client registrations.
#pragma once
#include <cstdint>
#include <mutex>
#include <unordered_map>
namespace kepler_witness {
enum class Decision { waiting, deliver, duplicate, rejected };
class RaceGate final {
 public:
  uint64_t register_work() {
   std::lock_guard<std::mutex> lock(mu_);
   if(sealed_||root_||rootReturned_||validated_||failed_||works_.size()>=4096)return 0;
   const auto id=++next_; works_.emplace(id,false);return id;
  }
  Decision seal() { std::lock_guard<std::mutex> lock(mu_);if(sealed_)return Decision::duplicate;sealed_=true;return evaluate(); }
  Decision complete(uint64_t id,bool ok) {
   std::lock_guard<std::mutex> lock(mu_);auto it=works_.find(id);
   if(it==works_.end())return Decision::rejected;
   if(it->second)return Decision::duplicate;
   it->second=true;completed_++;if(!ok)failed_=true;return evaluate();
  }
  Decision root() { std::lock_guard<std::mutex> lock(mu_);if(root_)return Decision::duplicate;root_=true;return evaluate(); }
  Decision root_returned() { std::lock_guard<std::mutex> lock(mu_);if(rootReturned_)return Decision::duplicate;rootReturned_=true;return evaluate(); }
  Decision result(bool ok) { std::lock_guard<std::mutex> lock(mu_);if(validated_)return Decision::duplicate;validated_=true;if(!ok)failed_=true;return evaluate(); }
 private:
  Decision evaluate() {
   if(failed_)return Decision::rejected;
   if(!sealed_||!root_||!rootReturned_||!validated_||completed_!=works_.size())return Decision::waiting;
   if(delivered_)return Decision::duplicate;
   delivered_=true;return Decision::deliver;
  }
  std::mutex mu_;std::unordered_map<uint64_t,bool> works_;uint64_t next_=0;size_t completed_=0;
  bool sealed_=false,root_=false,rootReturned_=false,validated_=false,failed_=false,delivered_=false;
};
}
