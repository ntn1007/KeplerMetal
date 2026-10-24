// SPDX-License-Identifier: MIT
// Shared test recipes; candidate state/records are never read to encode draws.
static uint32_t airDrawSeed(unsigned trial){static const uint32_t seeds[]={80,88,96,80,104,112,16,80};return seeds[trial];}
static uint32_t airDrawOrder(NSString *mode){return[mode hasPrefix:@"draw_then_reset"]?1u:[mode hasPrefix:@"draw_after_reset"]?2u:0u;}
static bool airAppliesReset(NSString *mode){return false;}
static bool airDispatchesReset(NSString *mode){return ![mode hasPrefix:@"draw_no_dispatch"];}
static NSString *airProducerVariant(NSString *mode){return[mode isEqual:@"draw_reference"]?@"reference":@"lowered";}
static bool airDrawReferenceAccepted(unsigned trial,NSString *mode){
    uint32_t seed=airDrawSeed(trial),first=5u+3u*((seed>>3)&1u),count=3u*((seed>>4)&3u),instances=(seed>>6)&1u,base=(seed>>8)&3u;
    return trial!=6&&trial!=7&&!airDrawOrder(mode)&&first-5u<=6u&&count<=6u-(first-5u)&&instances<=1u&&base==0u;
}
