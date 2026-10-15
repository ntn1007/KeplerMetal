#import "KeplerNativeCommands.h"
#include <cstring>
static uint32_t get(NSData*d,NSUInteger o){uint32_t v=0;memcpy(&v,(const char*)d.bytes+o,4);return v;}
static void set(NSMutableData*d,NSUInteger o,uint32_t v){memcpy((char*)d.mutableBytes+o,&v,4);}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;NSData*original=[NSData dataWithContentsOfFile:@(argv[1])];if(original.length!=464&&original.length!=496)return 2;NSUInteger qmd=original.length==496?216:184;if(get(original,qmd+0x50)%256!=6)return 2;
 NSMutableArray*checks=[NSMutableArray new];
 for(NSString*name in @[@"exact",@"inactive_CB0",@"inactive_CB0_without_certificate",@"active_CB0",@"active_CB1",@"valid_mask",@"program",@"grid",@"shared",@"registers",@"packet_header",@"inactive_CB3"]){
  NSMutableData*a=[original mutableCopy],*b=[original mutableCopy];BOOL allow=![name isEqual:@"inactive_CB0_without_certificate"],expected=[name isEqual:@"exact"]||[name isEqual:@"inactive_CB0"];
  if(![name isEqual:@"exact"]){set(b,qmd+0x74,0x00123400);set(b,qmd+0x78,0x00800123);}
  if([name isEqual:@"active_CB0"]){set(a,qmd+0x50,get(a,qmd+0x50)|1);set(b,qmd+0x50,get(b,qmd+0x50)|1);}
  NSDictionary*offsets=@{@"active_CB1":@124,@"valid_mask":@80,@"program":@32,@"grid":@48,@"shared":@68,@"registers":@184,@"inactive_CB3":@140};
  if(offsets[name]){NSUInteger o=qmd+[offsets[name]unsignedIntegerValue];set(b,o,get(b,o)^1);}
  if([name isEqual:@"packet_header"])set(b,0,get(b,0)^4);
  NSDictionary*proof=nil;BOOL accepted=KPCompareResidentPrimer(a,b,allow,&proof);if(accepted!=expected)return 3;
  [checks addObject:@{@"case":name,@"expected_accepted":@(expected),@"accepted":@(accepted),@"proof":proof?:@{}}];
 }
 NSData*out=[NSJSONSerialization dataWithJSONObject:@{@"status":@"PASS",@"checks":checks,@"GPU_executed":@NO,@"Metal_device_created":@NO}options:NSJSONWritingPrettyPrinted error:nil];fwrite(out.bytes,1,out.length,stdout);puts("");return 0;
}}
