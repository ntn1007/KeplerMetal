#!/usr/bin/env python3
"""Observe real encoder method ownership and disassemble bounded driver ranges.
Only uncommitted encoders/resources; no command stream patch or ICB fabrication.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,label,allowed=(0,),timeout=45):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode in allowed,r.stderr[-4000:];return r
base=(ROOT/'tools/icb_contract_probe.mm').read_text();source=base[:base.index('int main()')]+'''int main(){@autoreleasepool{
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if([x.name containsString:@"880M"]){d=x;break;}if(!d)return 2;
 NSMutableArray*rows=[NSMutableArray new];id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];
 id<MTLComputeCommandEncoder>compute=[cb computeCommandEncoder];
 for(NSString*s in @[@"dispatchThreadgroups:threadsPerThreadgroup:",@"dispatchThreadgroupsWithIndirectBuffer:indirectBufferOffset:threadsPerThreadgroup:",@"dispatchThreads:threadsPerThreadgroup:",@"executeCommandsInBuffer:withRange:",@"executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:",@"useResource:usage:"])[rows addObject:methodInfo(compute,s)];[compute endEncoding];
 MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:1 height:1 mipmapped:NO];td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget;
 id<MTLTexture>target=[d newTextureWithDescriptor:td];if(!target)return 3;
 MTLRenderPassDescriptor*pd=[MTLRenderPassDescriptor renderPassDescriptor];pd.colorAttachments[0].texture=target;pd.colorAttachments[0].loadAction=MTLLoadActionClear;pd.colorAttachments[0].storeAction=MTLStoreActionStore;
 id<MTLRenderCommandEncoder>render=[cb renderCommandEncoderWithDescriptor:pd];if(!render)return 4;
 for(NSString*s in @[@"drawPrimitives:vertexStart:vertexCount:instanceCount:baseInstance:",@"drawPrimitives:indirectBuffer:indirectBufferOffset:",@"drawIndexedPrimitives:indexType:indexBuffer:indexBufferOffset:indirectBuffer:indirectBufferOffset:",@"executeCommandsInBuffer:withRange:",@"executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:",@"useResource:usage:"])[rows addObject:methodInfo(render,s)];[render endEncoding];
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"methods":rows,@"GPU_dispatch":@NO,@"command_buffer_committed":@NO,@"ICB_created":@NO};
 NSData*b=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);puts("");return 0;
}}
'''
src=out/'indirect_transport_probe.mm';src.write_text(source);exe=out/'indirect_transport_probe'
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(src),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
execution=out/'execution';run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','20'],'observe')
process=json.loads((execution/'manifest.json').read_text());assert not process['SIGKILL_requested'] and not process['authoritative_ps_status']
methods=json.loads((execution/'execution.stdout').read_text());assert not methods['GPU_dispatch'] and not methods['command_buffer_committed'];(out/'methods.json').write_text(json.dumps(methods,indent=2)+'\n')
images={};records=[]
for number,row in enumerate(methods['methods']):
 if not row['responds']:continue
 path=Path(row['image']);data=path.read_bytes();assert data[:4]==b'\xcf\xfa\xed\xfe'
 count=struct.unpack_from('<I',data,16)[0];off=32;uuid=None
 for i in range(count):
  kind,length=struct.unpack_from('<II',data,off)
  if kind==0x1b:uuid=data[off+8:off+24].hex()
  off+=length
 assert row['image_UUID']==uuid;images[str(path)]={'sha256':sha(path),'UUID':uuid}
 start=int(row['image_offset'],16);prefix=data[start:start+6]
 # At most 8KiB of each selected method, enough to trace calls and resource
 # addresses while avoiding unbounded whole-image dumps. Not a CFG proof.
 stop=start+(6 if prefix==bytes.fromhex('554889e55dc3') else 8192)
 label=f'method-{number:02d}';r=run(['xcrun','llvm-objdump','-d','--start-address='+hex(start),'--stop-address='+hex(stop),str(path)],label)
 records.append({**row,'prefix':prefix.hex(),'six_byte_noop':prefix==bytes.fromhex('554889e55dc3'),
                 'disassembly':str(out/(label+'.stdout')),'requested_stop':hex(stop),'image_SHA256':sha(path)})
(out/'analysis.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'images':images,'methods':records,'GPU_dispatch':False,
 'scope':'Loaded IMP ownership/UUID plus bounded static ranges; downstream calls and packet meanings remain hypotheses until separately validated.'},indent=2)+'\n')
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());print(json.dumps({'methods':len(records),'noops':sum(r['six_byte_noop'] for r in records),'GPU_dispatch':False},indent=2))
