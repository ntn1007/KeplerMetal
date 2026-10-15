// CPU-only simulated constructor tests: no MTLDevice, no GPU or system hook.
#include "../src/KeplerProgramImport.mm"
@interface KPTestVariant:NSObject { @public id pad0,pad1,pad2;void *_variant;void *owned; }
@end
@implementation KPTestVariant
- (void)dealloc {free(owned);[super dealloc];}
@end
static int mode=0;
static id fakeInit(id self,SEL selector,const void *bytes,NSUInteger size,id device){
 (void)self;(void)selector;(void)device;if(mode==5)@throw [NSException exceptionWithName:@"simulated" reason:@"constructor exception" userInfo:nil];
 if(mode==3)return nil;std::vector<Section>table;if(!parse((const unsigned char*)bytes,size,table))return nil;
 Section code={},meta={};for(const auto&s:table){if(s.type==0x10005)code=s;if(s.type==0x10004)meta=s;}if(!code.size||meta.size!=232)return nil;
 KPTestVariant *object=[KPTestVariant new];object->owned=calloc(1,128);object->_variant=mode==4?(void*)1:object->owned;
 uint64_t length=code.size+(mode==1?64:0);memcpy((unsigned char*)object->owned+24,&length,8);put32((unsigned char*)object->owned,48,u32((const unsigned char*)bytes,meta.payload+28)+(mode==2?1:0));
 if(mode==6)((unsigned char*)bytes)[code.payload]^=1;
 return [object autorelease];
}
static std::vector<unsigned char> container(unsigned stage,bool after=false,unsigned nativeBytes=128){
 std::vector<unsigned char>b(8,0);put32(b.data(),0,8);size_t last=0;
 auto append=[&](uint32_t type,const std::vector<unsigned char>&data){size_t at=b.size();b.resize(at+16+data.size(),0);if(last){uint64_t next=at-last;memcpy(b.data()+last,&next,8);}put32(b.data(),at+8,type);put32(b.data(),at+12,(uint32_t)data.size());memcpy(b.data()+at+16,data.data(),data.size());last=at;};
 std::vector<unsigned char>s(4);put32(s.data(),0,stage);append(1,s);std::vector<unsigned char>m(232,0x3c);put32(m.data(),28,24);
 std::vector<unsigned char>c(nativeBytes,0x55);if(after){append(0x10005,c);append(0x10004,m);}else{append(0x10004,m);append(0x10005,c);}put32(b.data(),4,(uint32_t)b.size());return b;
}
int main(){@autoreleasepool{
 originalInit.store((IMP)fakeInit);NSMutableArray *cases=[NSMutableArray array];unsigned failures=0;NSData *code=[NSData dataWithBytes:std::vector<unsigned char>(64,0xa7).data() length:64];
 auto check=[&](NSString *name,bool pass){[cases addObject:@{@"name":name,@"pass":@(pass)}];if(!pass)failures++;};
 auto context=[&](){return Context{code,{24,576,576},[NSMutableArray array],[NSMutableArray array],false};};
 auto invoke=[&](Context&c,const std::vector<unsigned char>&b,int which){mode=which;activeContext=&c;id result=importInit(nil,@selector(init),b.data(),b.size(),nil);activeContext=nullptr;return result;};
 auto native=container(5);auto c=context();invoke(c,native,0);check(@"valid compute constructor",complete(c)&&c.targetImports==1&&c.verifiedImports==1);
 for(int i=1;i<=4;i++){c=context();invoke(c,native,i);check([NSString stringWithFormat:@"reject decoded/nil/pointer case %d",i],!complete(c)&&c.rejected);}
 c=context();invoke(c,native,0);invoke(c,native,1);check(@"later decoded failure cannot preserve success",!complete(c)&&c.rejected&&c.targetImports==2&&c.verifiedImports==1);
 c=context();invoke(c,native,0);auto bad=native;put32(bad.data(),4,0);invoke(c,bad,0);check(@"later invalid wire cannot preserve success",!complete(c)&&c.rejected);
 c=context();invoke(c,native,0);invoke(c,native,0);check(@"all matching variants accepted",complete(c)&&c.targetImports==2&&c.verifiedImports==2);
 for(unsigned n:{64u,192u}){c=context();auto reordered=container(5,true,n);invoke(c,reordered,0);check([NSString stringWithFormat:@"metadata after code, native size %u",n],complete(c)&&[c.events[0][@"metadata_bytes_preserved_except_import_fields"]boolValue]);}
 c=context();invoke(c,container(4),0);check(@"unmatched stage cannot qualify compute",!complete(c)&&!c.rejected&&c.targetImports==0);
 c=context();check(@"zero callbacks/cache cannot qualify import",!complete(c));
 c=context();invoke(c,native,6);check(@"constructor mutation of submitted SASS rejected",!complete(c)&&c.rejected);
 c=context();c.additionalVertex=code;c.vertexConfig={24,0,0};c.expectedStage=4;c.prefixBytes=80;
 auto vertex=container(0,false,208),fragment=container(4,false,208);invoke(c,vertex,0);invoke(c,fragment,0);check(@"paired vertex and fragment headers preserved",complete(c)&&c.vertexVerified&&[c.events[0][@"original_graphics_header_preserved"]boolValue]);
 c=context();c.additionalVertex=code;c.vertexConfig={24,0,0};c.expectedStage=4;c.prefixBytes=80;
 activeContext=&c;mode=5;bool threw=false;@try{importInit(nil,@selector(init),vertex.data(),vertex.size(),nil);}@catch(NSException*exception){(void)exception;threw=true;}check(@"nested exception restores parent context",threw&&activeContext==&c);activeContext=nullptr;
 NSError *error=nil;check(@"non-driver implementation profile rejected",!driverProfile((IMP)fakeInit,&error)&&error!=nil);
 NSDictionary *report=@{@"cases":cases,@"failures":@(failures),@"gpu_submission":@NO,@"scope":@"CPU simulation of constructor framing/metadata and rejection invariants; no hardware conformance claim"};NSData *json=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");return failures?10:0;
}}
