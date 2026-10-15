#!/usr/bin/env python3
"""Observe native descriptor writes after qualified public indirect dispatches.
The original probe remains unchanged. This immutable source fork only adds
CPU encoding capture and public Metal copies of buffers already owned by queue.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[];cases=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-4000:]
base=(ROOT/'tools/indirect_compute_probe.mm').read_text()
helpers=r'''
#import <objc/runtime.h>
#include <mach/mach_vm.h>
#include <CommonCrypto/CommonDigest.h>
static NSData *snapshot(uintptr_t p,size_t bytes){if(!p||!bytes||bytes>65536)return nil;NSMutableData*d=[NSMutableData dataWithLength:bytes];mach_vm_size_t actual=0;return mach_vm_read_overwrite(mach_task_self(),p,bytes,(mach_vm_address_t)d.mutableBytes,&actual)==KERN_SUCCESS&&actual==bytes?d:nil;}
static uint64_t word(NSData*d,size_t offset){uint64_t r=0;if(offset+8<=d.length)memcpy(&r,(const char*)d.bytes+offset,8);return r;}
static NSString*hash(NSData*d){unsigned char digest[32];CC_SHA256(d.bytes,(CC_LONG)d.length,digest);NSMutableString*s=[NSMutableString new];for(unsigned char x:digest)[s appendFormat:@"%02x",x];return s;}
struct Cursor{uintptr_t push,current,end;};
static Cursor cursor(id<MTLComputeCommandEncoder>e){Cursor c={};Ivar v=class_getInstanceVariable(object_getClass(e),"m_compute");if(!v||ivar_getOffset(v)!=120||class_getInstanceSize(object_getClass(e))!=128)return c;uintptr_t impl=0;memcpy(&impl,(const char*)(__bridge const void*)e+120,8);c.push=word(snapshot(impl,64),32);NSData*s=snapshot(c.push,144);c.current=word(s,0);c.end=word(s,136);return c;}
static id<MTLBuffer>queueBuffer(id<MTLCommandQueue>q,unsigned offset){Ivar v=class_getInstanceVariable(object_getClass(q),"_queue");if(!v||ivar_getOffset(v)!=680||strncmp(ivar_getTypeEncoding(v),"^{CommandQueue=I{InternalTextures=@@@@@}",38))return nil;uintptr_t cpp=0;memcpy(&cpp,(const char*)(__bridge const void*)q+680,8);uintptr_t ptr=word(snapshot(cpp,64),offset);if(!ptr)return nil;id o=(__bridge id)(void*)ptr;return [o isKindOfClass:objc_getClass("NVMTLBuffer")]?o:nil;}
'''
base=base.replace('struct P{',helpers+'\nstruct P{',1)
base=base.replace('if(argc!=6)return 1;',r'''if(argc!=6)return 1;NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];if(![hash(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 11;''',1)
base=base.replace('unsigned totalBad=0;',r'''unsigned totalBad=0;id<MTLBuffer>qmd=queueBuffer(q,16),stateCB=queueBuffer(q,32);if(!qmd||!stateCB||qmd.length!=4096||stateCB.length!=393216)return 12;''',1)
needle='if(direct)[e dispatchThreadgroups:'
assert base.count(needle)==1
base=base.replace(needle,'Cursor start=cursor(e);\n  '+needle,1)
needle='[e endEncoding];\n  if(!done(c))'
assert base.count(needle)==1
base=base.replace(needle,r'''Cursor finish=cursor(e);
  if(!start.push||start.push!=finish.push||!start.current||finish.current<=start.current||finish.current>start.end||finish.current-start.current>65536)return 13;
  NSData*commands=snapshot(start.current,finish.current-start.current);NSString*commandFile=[@(argv[2]) stringByAppendingPathComponent:[NSString stringWithFormat:@"consumer-%u.commands.bin",iteration]];
  if(!commands||![commands writeToFile:commandFile atomically:YES])return 14;
  [e endEncoding];
  if(!done(c))''',1)
needle='id<MTLCommandBuffer>read=[q commandBuffer];'
base=base.replace(needle,r'''std::vector<uint8_t>qmdGuard(qmd.length+128,0xa5),cbGuard(stateCB.length+128,0xa5);
  id<MTLBuffer>hostQMD=[d newBufferWithBytes:qmdGuard.data() length:qmdGuard.size() options:MTLResourceStorageModeManaged],hostCB=[d newBufferWithBytes:cbGuard.data() length:cbGuard.size() options:MTLResourceStorageModeManaged];if(!hostQMD||!hostCB)return 15;
  id<MTLCommandBuffer>read=[q commandBuffer];''',1)
needle='[b synchronizeResource:hostOut];'
base=base.replace(needle,r'''[b copyFromBuffer:qmd sourceOffset:0 toBuffer:hostQMD destinationOffset:64 size:qmd.length];[b copyFromBuffer:stateCB sourceOffset:0 toBuffer:hostCB destinationOffset:64 size:stateCB.length];[b synchronizeResource:hostQMD];[b synchronizeResource:hostCB];
  [b synchronizeResource:hostOut];''',1)
needle='for(size_t i=64+actualN*16;'
base=base.replace(needle,r'''for(size_t i=0;i<64;i++){guardBad+=((const uint8_t*)hostQMD.contents)[i]!=0xa5;guardBad+=((const uint8_t*)hostQMD.contents)[hostQMD.length-64+i]!=0xa5;guardBad+=((const uint8_t*)hostCB.contents)[i]!=0xa5;guardBad+=((const uint8_t*)hostCB.contents)[hostCB.length-64+i]!=0xa5;}
  for(size_t i=64+actualN*16;''',1)
needle='@[@".count",hostCounter]'
base=base.replace(needle,'@[@".count",hostCounter],@[@".qmd",hostQMD],@[@".cb",hostCB]',1)
needle='@"GPU_dispatch":@YES}'
base=base.replace(needle,r'''@"GPU_dispatch":@YES,@"encoding_file":commandFile,@"encoding_SHA256":hash(commands),@"encoding_bytes":@(commands.length),@"qmd_GPU_address":@(qmd.gpuAddress),@"qmd_bytes":@(qmd.length),@"state_CB_GPU_address":@(stateCB.gpuAddress),@"state_CB_bytes":@(stateCB.length),@"args_GPU_address":@(args.gpuAddress)}''',1)
base=base.replace('@"scope":@"Native indirect compute primitive, not an ICB implementation or performance benchmark"','@"scope":@"Public native dispatch followed by public Metal readback of live queue-owned QMD/CB buffers; no packet writes, native memory writes, replay, ICB implementation or benchmark"',1)
source=out/'indirect_descriptor_readback.mm';source.write_text(base);exe=out/'indirect_descriptor_readback'
library=out/'indirect_compute_probe.metallib';library.write_bytes((ROOT/'results/indirect-compute-native-qualified'/library.name).read_bytes())
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(source),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
for local,groups in [(33,3),(128,5)]:
 for mode in ['direct','GPU_indirect','missing_producer']:
  name=f'{mode}-l{local}-g{groups}';dest=out/(name+'-outputs');dest.mkdir();execution=out/(name+'-execution')
  run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','20','--',str(library),str(dest),mode,str(local),str(groups)],name)
  process=json.loads((execution/'manifest.json').read_text());assert not process['SIGKILL_requested'] and not process['authoritative_ps_status'] and process['exit_code']==0
  result=json.loads((execution/'execution.stdout').read_text());cases.append({'name':name,'result':result,'process':process});(out/'results.json').write_text(json.dumps(cases,indent=2)+'\n');assert result['passed']
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
(out/'manifest.json').write_text(json.dumps({'source_SHA256':sha(source),'library_SHA256':sha(library),'original_probe_SHA256':sha(ROOT/'tools/indirect_compute_probe.mm'),'Qwen_job_ids':[],'system_modifications':False,'all_new_children_terminal':True},indent=2)+'\n');print('PASS completed 6 native GPU cases and descriptor readbacks')
