// CPU-only contract checks against observed driver payloads and damaged copies.
#include "../src/KeplerProgramImport.mm"
#include <cstdio>
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3)return 1;
 std::vector<unsigned char>padded,ordinary;
 auto load=[](const char*path){NSData*d=[NSData dataWithContentsOfFile:@(path)];const unsigned char*b=(const unsigned char*)d.bytes;return d?std::vector<unsigned char>(b,b+d.length):std::vector<unsigned char>{};};
 padded=load(argv[1]);ordinary=load(argv[2]);if(padded.size()<32||ordinary.size()<32)return 2;
 unsigned failures=0;NSMutableArray*cases=[NSMutableArray array];
 auto check=[&](NSString*name,const std::vector<unsigned char>&b,bool expected){std::vector<Section>sections;bool valid=parse(b.data(),b.size(),sections);bool pass=valid==expected;if(!pass)failures++;[cases addObject:@{@"name":name,@"expected_valid":@(expected),@"actual_valid":@(valid),@"pass":@(pass)}];};
 check(@"observed stencil vertex with 4-byte zero padding",padded,true);
 check(@"observed fragment container without terminal padding",ordinary,true);
 auto damaged=padded;damaged.back()=1;check(@"nonzero terminal padding",damaged,false);
 damaged=padded;put32(damaged.data(),0,10);check(@"unknown container version",damaged,false);
 damaged=padded;put32(damaged.data(),4,(uint32_t)damaged.size()-1);check(@"wrong declared total",damaged,false);
 damaged=padded;put32(damaged.data(),20,0xffffffff);check(@"first section exceeds input",damaged,false);
 damaged=padded;uint64_t next=1;memcpy(damaged.data()+8,&next,8);check(@"overlapping linked section",damaged,false);
 damaged=padded;next=damaged.size()+1;memcpy(damaged.data()+8,&next,8);check(@"next link outside input",damaged,false);
 damaged=padded;damaged.resize(damaged.size()+8,0);put32(damaged.data(),4,(uint32_t)damaged.size());check(@"extra aligned trailing block",damaged,false);
 check(@"too short input",std::vector<unsigned char>(7,0),false);
 NSDictionary*result=@{@"cases":cases,@"failures":@(failures),@"gpu_submission":@NO,@"scope":@"CPU-only real-container and corruption checks"};NSData*json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");return failures?10:0;
}}
