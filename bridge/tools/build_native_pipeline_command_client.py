#!/usr/bin/env python3
"""Use the public function pipeline factory, keeping native root bindings."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--refusals',action='store_true');a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/native-root-command-client-build-20261015-02';base=json.loads((old/'inputs.json').read_text());lib=a.library.resolve();lm=json.loads((lib/'manifest.json').read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']
for key,folder in [('source_hashes',old),('assets_SHA256',old/'assets'),('runtime_SHA256',old/'runtime')]:
 for n,h in base[key].items():assert sha(folder/n)==h
shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime')
for n in base['source_hashes']:shutil.copyfile(old/n,out/n)
shutil.copyfile(lib/'src/KeplerCPUICB.h',out/'KeplerCPUICB.h')
s=(out/'command_ir_dataflow_client.mm').read_text()
assert s.count('writer=KPCreatePipeline(')==1
start=s.index('writer=KPCreatePipeline(');end=s.index('id<MTLLibrary>f=',start);s=s[:start]+s[end:]
lines=s.splitlines();matches=[i for i,x in enumerate(lines)if 'producerFunction=[scope newCommandIRFunctionWithLibraryData:'in x];assert len(matches)==1
bootstrap='''
 NSData*carrierBytes=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"carrier.metallib"]],*programBytes=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[semantic stringByAppendingString:@".sass"]]];
 for(unsigned badRegistration=0;badRegistration<3;badRegistration++){
  NSMutableData*badCarrier=[carrierBytes mutableCopy],*badProgram=[programBytes mutableCopy];
  if(badRegistration==0)((uint8_t*)badProgram.mutableBytes)[0]^=1;
  else if(badRegistration==1)((uint8_t*)badCarrier.mutableBytes)[0]^=1;
  else badProgram=[[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[([semantic isEqual:@"basic"]?@"barrier":@"basic") stringByAppendingString:@".sass"]]]mutableCopy];
  NSError*rejection=nil;NSUInteger before=scope.events.count;
  if([scope registerCommandIRProducerForFunction:producerFunction carrierData:badCarrier programData:badProgram error:&rejection]||!rejection||scope.events.count!=before)return 3;
 }
 if(![scope registerCommandIRProducerForFunction:producerFunction carrierData:carrierBytes programData:programBytes error:&error]){emit(@{@"failure":@"producer_registration",@"error":error.description?:@"nil"});return 3;}
 NSError*duplicate=nil;if([scope registerCommandIRProducerForFunction:producerFunction carrierData:carrierBytes programData:programBytes error:&duplicate]||!duplicate)return 3;
 writer=[d newComputePipelineStateWithFunction:producerFunction error:&error];id<MTLComputePipelineState>cached=[d newComputePipelineStateWithFunction:producerFunction error:&error];
 if(!writer||writer!=cached||![NSStringFromClass(object_getClass(writer))isEqual:@"NVMTLComputePipelineState"])return 3;
 for(NSDictionary*event in scope.events)if([event[@"operation"]isEqual:@"register_IRv2_native_producer"])importProof=event[@"profile"][@"import"];
 id<MTLLibrary>ordinary=load(d,[assets stringByAppendingPathComponent:@"consumer.metallib"],&error);id<MTLComputePipelineState>untouched=[d newComputePipelineStateWithFunction:[ordinary newFunctionWithName:@"dependency_seed"]error:&error];if(!untouched)return 3;
 id<MTLLibrary>unregistered=load(d,[assets stringByAppendingPathComponent:@"producer.metallib"],&error);NSError*nativeError=nil;
 if([d newComputePipelineStateWithFunction:[unregistered newFunctionWithName:[@"encode_dataflow_"stringByAppendingString:semantic]]error:&nativeError]||![nativeError.description containsString:@"air.compute_pipeline_state"])return 3;
'''.replace('@"encode_dataflow_"string','@"encode_dataflow_" string')
lines.insert(matches[0]+1,bootstrap)
restores=[i for i,x in enumerate(lines)if 'MTLArgument*restoredReflection=nil;'in x];assert len(restores)==1
lines.insert(restores[0]+1,' NSError*restoredFactoryError=nil;if([d newComputePipelineStateWithFunction:producerFunction error:&restoredFactoryError]||![restoredFactoryError.description containsString:@"air.compute_pipeline_state"])return 13;')
s='\n'.join(lines)+'\n'
anchor='@"native_root_binding":@YES,@"host_push_buffer_required":@NO';assert s.count(anchor)==1;s=s.replace(anchor,anchor+',@"public_pipeline_factory":@YES,@"producer_registration_refusals":@(KP_DATAFLOW_NATIVE?0:4),@"ordinary_pipeline_passthrough":@YES,@"unregistered_native_failure_preserved":@(!KP_DATAFLOW_NATIVE),@"native_factory_restored":@YES',1)
# The native-reference branch is unchanged. New bootstrap is Kepler-only.
assert 'writer=KPCreatePipeline('not in s
(out/'command_ir_dataflow_client.mm').write_text(s);commands=[]
for label,cmd in [('import',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out,'-c',out/'KeplerProgramImport.mm','-o',out/'KeplerProgramImport.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=0','-DKP_PUBLIC_ARGUMENT_ENCODER=1','-DKP_FUNCTION_ARGUMENT_ENCODER=1','-DKP_ARGUMENT_REFUSALS='+str(int(a.refusals)),'-I',out,out/'command_ir_dataflow_client.mm',out/'KeplerProgramImport.o',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
base.update(source_hashes={n:sha(out/n)for n in base['source_hashes']},static_library_SHA256=sha(lib/'libKeplerMetal.a'),library_build_manifest_SHA256=sha(lib/'manifest.json'),source_parent_inputs_SHA256=sha(old/'inputs.json'),source_generator_SHA256=sha(__file__),executable_SHA256=sha(out/'application'),public_pipeline_factory=True,argument_refusals=a.refusals)
(out/'inputs.json').write_text(json.dumps(base,indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out),'public_pipeline_factory':True,'library':base['static_library_SHA256']}))
