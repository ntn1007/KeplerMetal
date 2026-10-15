#!/usr/bin/env python3
"""Add a matched8-byte native binding control to a frozen dataflow client."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--client',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();client=a.client.resolve();library=a.library.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');inp=json.loads((client/'inputs.json').read_text());assert sha(library/'libKeplerMetal.a')==inp['static_library_SHA256']
for n,h in inp['source_hashes'].items():assert sha(client/n)==h
for n,h in inp['assets_SHA256'].items():assert sha(client/'assets'/n)==h
for n,h in inp['runtime_SHA256'].items():assert sha(client/'runtime'/n)==h
shutil.copytree(client,out);source=out/'command_ir_dataflow_client.mm';s=source.read_text();anchor='||split||bad||[mode isEqual:@"refusals"]';assert s.count(anchor)==1;s=s.replace(anchor,'||split||bad||[mode hasPrefix:@"descriptor_"]||[mode isEqual:@"refusals"]')
anchor='#endif\n  if(consumerPresent){';assert s.count(anchor)==1
code='''#endif
#if !KP_DATAFLOW_NATIVE
  if([mode hasPrefix:@"descriptor_"]){
   BOOL negative=[mode isEqual:@"descriptor_negative"];if(!negative&&![mode isEqual:@"descriptor_positive"])return 23;
   id<MTLBuffer>source=[plan valueForKey:negative?@"constantTemplates":@"commandIRNativeBindings"];NSArray*targets=[plan valueForKey:@"targetRecords"];id<MTLBlitCommandEncoder>control=[main blitCommandEncoder];
   for(NSUInteger stage=1;stage<3;stage++){NSUInteger off=negative?stage*65536+32:(stage*3+stage)*128+32;[control copyFromBuffer:source sourceOffset:off toBuffer:[targets[stage]valueForKey:@"constants"]destinationOffset:32 size:8];}
   [control endEncoding];
  }
#endif
  if(consumerPresent){'''
s=s.replace(anchor,code);source.write_text(s)
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=0','-I',str(out),str(source),str(out/'KeplerProgramImport.o'),'-L',str(library),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'control-build.stdout').write_text(r.stdout);(out/'control-build.stderr').write_text(r.stderr);(out/'control-build.json').write_text(json.dumps({'argv':cmd,'exit_code':r.returncode,'generator_SHA256':sha(__file__),'source_client_inputs_SHA256':sha(client/'inputs.json')},indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
inp['source_hashes'][source.name]=sha(source);inp['executable_SHA256']=sha(out/'application');inp['descriptor_control']={'source_inputs_SHA256':sha(client/'inputs.json'),'generator_SHA256':sha(__file__),'bytes_per_stage':8,'stages':[1,2],'native_GPU_tables_only':True};(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n');print(json.dumps({'status':'PASS','GPU_execution':False,'source_client':str(client)}))
