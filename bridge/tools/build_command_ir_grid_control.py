#!/usr/bin/env python3
"""Build a test-only shader-visible grid control from an exact runtime client."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--client',type=Path,required=True);p.add_argument('--library',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);client=a.client.resolve();inp=json.loads((client/'inputs.json').read_text())
for n,h in inp['source_hashes'].items():assert sha(client/n)==h
for n,h in inp['assets_SHA256'].items():assert sha(client/'assets'/n)==h
shutil.copytree(client/'assets',out/'assets');shutil.copytree(client/'runtime',out/'runtime')
for n in ['KeplerCPUICB.h','KeplerProgramImport.h','KeplerProgramImport.mm','KeplerProgramImport.o']:shutil.copyfile(client/n,out/n)
s=(client/'gpu_command_bindings_client.mm').read_text()
def replace(before,after):
 global s
 assert s.count(before)==1,before[:120];s=s.replace(before,after,1)
replace(' const unsigned statics[3]',
 ' id<MTLLibrary>gridLibrary=load(d,[assets stringByAppendingPathComponent:@"grid_witness.metallib"],&error);id<MTLComputePipelineState>gridPSO=[d newComputePipelineStateWithFunction:[gridLibrary newFunctionWithName:@"override_grid_witness"]error:&error];if(!gridPSO)return 3;\n const unsigned statics[3]')
replace('  if(split)[sbuf commit];if(completed)',
 '''  if(![mode isEqual:@"basic"])return 22;
  NSArray*nativeRecords=[plan valueForKey:@"targetRecords"];
  for(id native in nativeRecords){id<MTLBuffer>constants=[native valueForKey:@"constants"];uint32_t originalGroups=[specs[(t+1)%3][@"groups"]unsignedIntValue];
   id<MTLComputeCommandEncoder>patch=[sbuf computeCommandEncoder];[patch setComputePipelineState:gridPSO];[patch setBuffer:constants offset:0 atIndex:0];[patch setBytes:&originalGroups length:4 atIndex:1];[patch dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];[patch endEncoding];}
  if(split)[sbuf commit];if(completed)''')
(out/'gpu_command_bindings_client.mm').write_text(s);shutil.copyfile(ROOT/'src/command_ir_grid_witness_probe.metal',out/'grid_witness.metal');commands=[]
for label,cmd in [('metal',['xcrun','metal','-std=macos-metal2.0','-c',out/'grid_witness.metal','-o',out/'probe.air']),('metallib',['xcrun','metallib',out/'probe.air','-o',out/'assets/grid_witness.metallib']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/'gpu_command_bindings_client.mm',out/'KeplerProgramImport.o','-L',a.library.resolve(),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
inp.update(source_hashes={n:sha(out/n)for n in ['gpu_command_bindings_client.mm','KeplerCPUICB.h','KeplerProgramImport.h','KeplerProgramImport.mm','grid_witness.metal']},assets_SHA256={p.name:sha(p)for p in(out/'assets').iterdir()},executable_SHA256=sha(out/'application'),test_only_stale_group_witness=True)
(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'GPU_execution':False}))
