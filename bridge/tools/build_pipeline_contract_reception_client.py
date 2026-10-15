#!/usr/bin/env python3
"""One frozen client selects six public pipeline factory variants by CLI prefix."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--thread-limit',type=int,choices=[0,32,64,128,256,512,1024],default=0);p.add_argument('--producer-threads',type=int,choices=[32,64,128,256,512,1024],default=32);p.add_argument('--automatic-encoders',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/native-pipeline-command-client-build-20261015-02';base=json.loads((old/'inputs.json').read_text());lib=a.library.resolve();lm=json.loads((lib/'manifest.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']
for key,folder in [('source_hashes',old),('assets_SHA256',old/'assets'),('runtime_SHA256',old/'runtime')]:
 for n,h in base[key].items():assert sha(folder/n)==h
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
for n in base['source_hashes']:shutil.copyfile(old/n,out/n)
shutil.copyfile(lib/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h');shutil.copyfile(ROOT/'tools/PipelineFactoryReception.inc',out/'PipelineFactoryReception.inc')
s=(out/'command_ir_dataflow_client.mm').read_text();anchor='#include <cstring>';assert s.count(anchor)==1;s=s.replace(anchor,anchor+'\n#include "PipelineFactoryReception.inc"',1)
anchor=' BOOL reuseEncoder=';assert s.count(anchor)==1;s=s.replace(anchor,' NSUInteger factoryKind=0;NSDictionary*factoryEvidence=nil;NSArray*parts=[mode componentsSeparatedByString:@":"];if(parts.count==2){factoryKind=[parts[0]integerValue];if(factoryKind>5||![[NSString stringWithFormat:@"%lu",(unsigned long)factoryKind]isEqual:parts[0]])return 1;mode=parts[1];}else if(parts.count!=1)return 1;\n'+anchor,1)
anchor='writer=[d newComputePipelineStateWithFunction:producerFunction error:&error];';assert s.count(anchor)==2;s=s.replace(anchor,'writer=receptionPipeline(d,producerFunction,factoryKind,&factoryEvidence,&error);')
s=s.replace('writer!=cached','(factoryKind==0&&writer!=cached)',1)
anchor='if(producer){id<MTLComputeCommandEncoder>e=[pbuf computeCommandEncoder];';assert s.count(anchor)==1;s=s.replace(anchor,anchor+'\n#if !KP_DATAFLOW_NATIVE\nif(![scope adaptComputeEncoder:e error:&error])return 10;\n#endif\n',1)
lines=s.splitlines();matches=[i for i,x in enumerate(lines)if'event[@"profile"][@"import"]'in x];assert len(matches)==1;lines.insert(matches[0]+1,' importProof=objc_getAssociatedObject(writer,sel_registerName("KeplerMetalProducerEvidence-v1"));if(![importProof[@"contract_verified"]boolValue])return 3;')
s='\n'.join(lines)+'\n'
if a.producer_threads!=32:
 anchor='[e useResource:r usage:MTLResourceUsageRead];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(1,1,1)];';assert s.count(anchor)==1;s=s.replace(anchor,anchor.replace('threadsPerThreadgroup:MTLSizeMake(1,1,1)','threadsPerThreadgroup:MTLSizeMake('+str(a.producer_threads)+',1,1)'),1)
 anchor='[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(32,1,1)];';assert s.count(anchor)==1;s=s.replace(anchor,anchor.replace('threadsPerThreadgroup:MTLSizeMake(32,1,1)','threadsPerThreadgroup:MTLSizeMake('+str(a.producer_threads)+',1,1)'),1)
if a.automatic_encoders:
 shutil.copyfile(ROOT/'tools/QueueFactoryReception.inc',out/'QueueFactoryReception.inc')
 s=s.replace('#include "PipelineFactoryReception.inc"','#include "PipelineFactoryReception.inc"\n#include "QueueFactoryReception.inc"',1)
 anchor='NSArray*parts=[mode componentsSeparatedByString:@":"];';assert s.count(anchor)==1
 s=s.replace(anchor,anchor+'if(parts.count==4){receptionQueueKind=[parts[1]integerValue];receptionEncoderKind=[parts[2]integerValue];if(receptionQueueKind>1||receptionEncoderKind>4||![[NSString stringWithFormat:@"%lu",(unsigned long)receptionQueueKind]isEqual:parts[1]]||![[NSString stringWithFormat:@"%lu",(unsigned long)receptionEncoderKind]isEqual:parts[2]])return 1;parts=@[parts[0],parts[3]];}',1)
 assert s.count('adaptComputeEncoder:')==2
 for code in [10,11]:
  anchor='if(![scope adaptComputeEncoder:e error:&error])return '+str(code)+';';assert s.count(anchor)==1
  s=s.replace(anchor,'if(![NSStringFromClass(object_getClass(e))hasPrefix:@"KPICBEncoder_"])return '+str(code)+';',1)
 assert 'adaptComputeEncoder:'not in s
 s=s.replace('[q commandBuffer]','receptionCommandBuffer(q)')
 for name in ['pbuf','main']:s=s.replace('['+name+' computeCommandEncoder]','receptionComputeEncoder('+name+')')
 s=s.replace('@"public_pipeline_factory":@YES','@"public_pipeline_factory":@YES,@"automatic_encoders":@YES,@"manual_compute_adaptation_calls":@0,@"queue_factory_kind":@(receptionQueueKind),@"encoder_factory_kind":@(receptionEncoderKind)',1)
anchor='@"public_pipeline_factory":@YES';assert s.count(anchor)==1;s=s.replace(anchor,anchor+',@"factory_kind":@(factoryKind),@"factory_evidence":factoryEvidence?:@{}',1);(out/'command_ir_dataflow_client.mm').write_text(s)
commands=[]
for label,cmd in [('import',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DESCRIPTOR_MAX_THREADS='+str(a.thread_limit),'-DKP_DATAFLOW_NATIVE=0','-DKP_PUBLIC_ARGUMENT_ENCODER=1','-DKP_FUNCTION_ARGUMENT_ENCODER=1','-DKP_ARGUMENT_REFUSALS=0','-I',out,out/'command_ir_dataflow_client.mm',out/'KeplerProgramImport.o',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
base.update(source_hashes={n:sha(out/n)for n in [*base['source_hashes'],'PipelineFactoryReception.inc',*(['QueueFactoryReception.inc']if a.automatic_encoders else[])]},static_library_SHA256=sha(lib/'libKeplerMetal.a'),library_build_manifest_SHA256=sha(lib/'manifest.json'),source_parent_inputs_SHA256=sha(old/'inputs.json'),source_generator_SHA256=sha(__file__),executable_SHA256=sha(out/'application'),pipeline_factory_variants=6,descriptor_thread_limit=a.thread_limit,producer_local_threads=a.producer_threads,automatic_encoders=a.automatic_encoders)
(out/'inputs.json').write_text(json.dumps(base,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'library':base['static_library_SHA256']}))
