#!/usr/bin/env python3
"""Run the existing CAS client after a new descriptor import on the same thread."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--library',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
sdk=ROOT/'results/native-cas-sdk-build-20261014-02/KeplerNativeCAS';lib=a.library.resolve();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();lm=json.loads((lib/'manifest.json').read_text());assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']
for row in json.loads((sdk/'FILE_MANIFEST.json').read_text())['files']:assert sha(sdk/row['path'])==row['SHA256']
shutil.copytree(sdk/'assets',out/'assets');shutil.copyfile(lib/'src/KeplerNativeCAS.h',out/'KeplerNativeCAS.h')
parent=ROOT/'results/native-pipeline-command-client-build-20261015-02';pm=json.loads((parent/'inputs.json').read_text())
for source,target in [('carrier.metallib','descriptor-carrier.metallib'),('basic.sass','descriptor-basic.sass')]:assert sha(parent/'assets'/source)==pm['assets_SHA256'][source];shutil.copyfile(parent/'assets'/source,out/'assets'/target)
s=(sdk/'examples/client.mm').read_text();anchor='static NSString *digest(';i=s.index(anchor);s=s[:i]+'''@interface KPCommandIRProducerFactory : NSObject
+ (id<MTLComputePipelineState>)newPipelineForDevice:(id<MTLDevice>)device carrier:(NSData*)carrier program:(NSData*)program descriptor:(MTLComputePipelineDescriptor*)descriptor error:(NSError**)error evidence:(NSDictionary**)evidence;
@end
'''+s[i:]
anchor=' NSError *error=nil;';assert s.count(anchor)==1
prelude='''
 NSData*descriptorCarrier=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"descriptor-carrier.metallib"]],*descriptorCode=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"descriptor-basic.sass"]];
 MTLComputePipelineDescriptor*preludeDescriptor=[MTLComputePipelineDescriptor new];preludeDescriptor.label=@"cas-descriptor-prelude";NSDictionary*descriptorProof=nil;
 id<MTLComputePipelineState>descriptorPipeline=[KPCommandIRProducerFactory newPipelineForDevice:device carrier:descriptorCarrier program:descriptorCode descriptor:preludeDescriptor error:&error evidence:&descriptorProof];
 if(!descriptorPipeline||![descriptorProof[@"contract_verified"]boolValue])return 9;
'''.replace('\n+','\n')
s=s.replace(anchor,anchor+prelude,1);anchor='@"mode":mode';assert s.count(anchor)==1;s=s.replace(anchor,anchor+',@"descriptor_transport_prelude":@YES,@"descriptor_transport_import":descriptorProof',1);(out/'cas_client.mm').write_text(s)
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cas_client.mm'),str(lib/'libKeplerMetal.a'),'-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'cas_example')];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr[-2500:]
(out/'inputs.json').write_text(json.dumps({'module_static_library_SHA256':sha(lib/'libKeplerMetal.a'),'client_source_SHA256':sha(out/'cas_client.mm'),'public_header_SHA256':sha(out/'KeplerNativeCAS.h'),'executable_SHA256':sha(out/'cas_example'),'assets':{p.name:sha(p)for p in(out/'assets').iterdir()},'source_generator_SHA256':sha(__file__),'GPU_execution':False},indent=2)+'\n');print(json.dumps({'status':'PASS','out':str(out)}))
