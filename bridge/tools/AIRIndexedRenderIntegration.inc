// SPDX-License-Identifier: MIT
static NSArray *airIndexedModes(){return @[@"indexed_gpu",@"indexed_native",@"indexed_reference",@"indexed_no_dispatch",@"indexed_no_dispatch_native",@"indexed_foreign",@"indexed_foreign_native",@"indexed_wrong_kind",@"indexed_wrong_kind_native",@"indexed_last",@"indexed_last_native",@"indexed_missing_table",@"indexed_missing_table_native",@"indexed_after_reset",@"indexed_after_reset_native",@"indexed_then_reset",@"indexed_then_reset_native",@"indexed_contracts"];}
static uint32_t airIndexSeed(unsigned trial){static const uint32_t seeds[]={80,88,96,104,64,112,80,88};return seeds[trial];}
static uint32_t airIndexOrder(NSString*mode){return[mode hasPrefix:@"indexed_last"]?3u:[mode hasPrefix:@"indexed_after_reset"]?2u:[mode hasPrefix:@"indexed_then_reset"]?1u:0u;}
static bool airAppliesReset(NSString*mode){return false;}
static bool airDispatchesReset(NSString*mode){return ![mode hasPrefix:@"indexed_no_dispatch"];}
static NSString *airProducerVariant(NSString*mode){return[mode isEqual:@"indexed_reference"]?@"reference":@"lowered";}
static void airIndexDrawArguments(unsigned trial,unsigned logical,NSString*mode,uint32_t&first,uint32_t&count,uint32_t&instances){
 unsigned gid=logical-1,slot=logical==1?1:3;uint32_t x=(gid*1664525u+airIndexSeed(trial))^slot;
 first=3u*((x>>3)&1u);count=3u*((x>>4)&3u);instances=(x>>6)&1u;
 if(airIndexOrder(mode)==3){first=3u-first;count=3;instances=1;}
}
static bool airIndexReferenceAccepted(unsigned trial,unsigned logical,NSString*mode){
 if(trial==7||(trial==1&&logical==1)||(trial==2&&logical==2)||[mode hasPrefix:@"indexed_foreign"]||[mode hasPrefix:@"indexed_wrong_kind"]||[mode hasPrefix:@"indexed_missing_table"]||airIndexOrder(mode)==1||airIndexOrder(mode)==2)return false;
 uint32_t first,count,instances;airIndexDrawArguments(trial,logical,mode,first,count,instances);return first<=6&&count<=6-first&&instances<=1;
}
