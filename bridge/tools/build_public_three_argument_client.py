#!/usr/bin/env python3
"""Reuse the qualified n3 shared-memory fixture and change its binding API only."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--public',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/command-ir-lifetime-final-production-v2-three-build-20261015';base=json.loads((old/'inputs.json').read_text());library=a.library.resolve();lm=json.loads((library/'manifest.json').read_text());assert sha(library/'libKeplerMetal.a')==lm['static_library_SHA256']
for key,folder in [('source_hashes',old),('assets_SHA256',old/'assets'),('runtime_SHA256',old/'runtime')]:
 for n,h in base[key].items():assert sha(folder/n)==h
assert base['assets_SHA256']['command_ir_materializer.metallib']=='a16652f21d39de58e16dbb4704b98813565b5ec3e9e2f0f926c0eb6d77015997'
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
for n in ['KeplerProgramImport.h','KeplerProgramImport.mm']:shutil.copyfile(ROOT/'src'/n,out/n)
shutil.copyfile(library/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h');s=(old/'gpu_command_bindings_client.mm').read_text()
assert s.count('NSArray*keep=@[root,pushBuffer,IRproducer,plan.commandIRProducerResources];')==1
anchor='   id<MTLBuffer>root=[plan newCommandIRArgumentsForCandidateIndex:(t+1)%3 resourceIndex:(t+2)%3 error:&error];if(!root)return 9;';assert s.count(anchor)==1
replacement='''   id<MTLBuffer>root=nil;
#if KP_PUBLIC_THREE_ARGUMENTS
   unsigned candidate=(t+1)%3,bank=(t+2)%3;NSMutableArray*descriptors=[NSMutableArray new];for(unsigned i=0;i<5;i++){MTLArgumentDescriptor*a=[MTLArgumentDescriptor argumentDescriptor];a.index=i;a.arrayLength=1;a.dataType=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;[descriptors addObject:a];}
   __weak id weakEncoder=nil;@autoreleasepool{id<MTLArgumentEncoder>ae=[d newArgumentEncoderWithArguments:descriptors];weakEncoder=ae;if(ae.encodedLength!=40||ae.alignment!=8)return 9;root=[d newBufferWithLength:40 options:MTLResourceStorageModeShared];[ae setArgumentBuffer:root offset:0];[ae setIndirectCommandBuffer:icb atIndex:0];[ae setComputePipelineState:pipelines[specs[candidate][@"function"]]atIndex:1];NSDictionary*x=resourceEntries[bank];[ae setBuffer:x[@"output"]offset:[x[@"outputOffset"]unsignedIntegerValue]atIndex:2];[ae setBuffer:x[@"counter"]offset:[x[@"counterOffset"]unsignedIntegerValue]atIndex:3];[ae setBuffer:params[candidate]offset:1024 atIndex:4];}
   if(weakEncoder||![plan validateCommandIRArgumentBindings:&error])return 9;
#else
   root=[plan newCommandIRArgumentsForCandidateIndex:(t+1)%3 resourceIndex:(t+2)%3 error:&error];
#endif
   if(!root)return 9;'''
s=s.replace(anchor,replacement,1);(out/'gpu_command_bindings_client.mm').write_text(s);commands=[]
for label,cmd in [('import',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_SELECT_NATIVE=0','-DKP_PUBLIC_THREE_ARGUMENTS='+str(int(a.public)),'-I',out,out/'gpu_command_bindings_client.mm',out/'KeplerProgramImport.o',library/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
inp={'source_hashes':{n:sha(out/n)for n in ['gpu_command_bindings_client.mm','KeplerCPUICB.h','KeplerProgramImport.h','KeplerProgramImport.mm']},'assets_SHA256':{n:sha(out/'assets'/n)for n in base['assets_SHA256']},'runtime_SHA256':{n:sha(out/'runtime'/n)for n in base['runtime_SHA256']},'static_library_SHA256':sha(library/'libKeplerMetal.a'),'library_build_manifest_SHA256':sha(library/'manifest.json'),'source_parent_inputs_SHA256':sha(old/'inputs.json'),'source_generator_SHA256':sha(__file__),'public_three_argument_encoder':a.public,'executable_SHA256':sha(out/'application'),'GPU_execution':False};(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n');print(json.dumps({'status':'PASS','public':a.public,'out':str(out),'library':inp['static_library_SHA256']}))
