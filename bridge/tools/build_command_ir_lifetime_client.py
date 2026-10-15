#!/usr/bin/env python3
"""Freeze a caller-release/autorelease-pool lifetime fixture around native IRv2."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--client',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--return-header',type=Path);p.add_argument('--recompile-import',action='store_true');a=p.parse_args();client=a.client.resolve();library=a.library.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');inp=json.loads((client/'inputs.json').read_text());assert sha(library/'libKeplerMetal.a')==inp['static_library_SHA256']
for key,base in [('source_hashes',client),('assets_SHA256',client/'assets'),('runtime_SHA256',client/'runtime')]:
 for n,h in inp[key].items():assert sha(base/n)==h
shutil.copytree(client,out);source=out/'command_ir_dataflow_client.mm';s=source.read_text()
if a.return_header:
 candidate=a.return_header.read_text();original=(out/'KeplerProgramImport.h').read_text();assert candidate.count('NS_RETURNS_RETAINED')==6 and candidate.replace(' NS_RETURNS_RETAINED','')==original;shutil.copyfile(a.return_header,out/'KeplerProgramImport.h');inp['source_hashes']['KeplerProgramImport.h']=sha(out/'KeplerProgramImport.h')
def replace(old,new):
 global s
 assert s.count(old)==1,(old[:100],s.count(old));s=s.replace(old,new,1)
replace('#include <cstring>','#include <cstring>\n#include <unistd.h>')
replace('BOOL producer=![mode', '''NSString*variant=mode;
 if(![@[@"keep",@"drop",@"restore",@"split_restore",@"copy_restore",@"no_producer_restore",@"no_consumer_restore",@"cancel_legacy",@"cancel_leases"]containsObject:variant])return 24;
 BOOL cancelled=[variant hasPrefix:@"cancel_"];mode=[variant isEqual:@"copy_restore"]?@"copy":[variant isEqual:@"split_restore"]?@"split":[variant isEqual:@"no_producer_restore"]?@"no_producer":[variant isEqual:@"no_consumer_restore"]?@"no_consumer":@"basic";
 BOOL producer=![mode''')
opening='''unsigned sizes[4]={256,1024,4096,32768},locals[4][3]={{32,128,1024},{33,256,512},{128,33,1024},{1024,256,33}};NSUInteger APIrefusals=0;NSMutableArray*runs=[NSMutableArray new];
 for(unsigned trial=0;trial<4;trial++){@autoreleasepool{'''
replace('if(!writer)return 3;'+opening,'if(!writer)return 3;')
replace(' if(!d)return 2;id<MTLCommandQueue>', ''' if(!d)return 2;Class nativeDeviceClass=object_getClass(d);NSDictionary*finalInfo=@{},*finalImport=@{};
 '''+opening.replace('for(unsigned trial=0;trial<4;trial++){@autoreleasepool{','''for(unsigned trial=0;trial<4;trial++){
 id<MTLCommandBuffer>pending=nil;NSMutableDictionary*savedHosts=nil,*deferredRow=nil;id<MTLBuffer>savedWitness=nil;NSArray*callerOwners=nil;
 __weak KPGPUCommandSelection*weakPlan=nil;__weak KPCPUICBScope*weakScope=nil;__weak id weakICB=nil,weakRecord=nil,weakBinding=nil,weakRoot=nil,weakPrivate=nil,weakWriter=nil;
 @autoreleasepool{''')+'''
 id<MTLCommandQueue>''')
replace('NSArray*keep=@[root,p,writer,plan];', '''NSArray*keep=[variant isEqual:@"cancel_legacy"]?@[root,p,writer,plan]:@[root,p,writer,plan.commandIRProducerResources];''')
replace('[b endEncoding];if(!done(main))return 12;','''[b endEncoding];pending=main;savedHosts=hosts;savedWitness=witnessHost;
  weakPlan=plan;weakScope=scope;weakICB=icb;weakRecord=[[plan valueForKey:@"targetRecords"]firstObject];weakBinding=[[plan valueForKey:@"commandIRBindingRecords"]firstObject];weakRoot=root;weakPrivate=buffers[@"stage0"];weakWriter=writer;
  if([variant isEqual:@"keep"])callerOwners=@[scope,plan,icb,root,writer,pipelines,params,buffers];
  if(![variant isEqual:@"keep"]&&![variant isEqual:@"drop"])[scope restore];
  finalInfo=info;finalImport=importProof;''')
replace('[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[name]=f;','files[name]=f;')
replace('[[NSData dataWithBytes:witnessHost.contents length:witnessHost.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];files[@"witness"]=f;','files[@"witness"]=f;')
replace('[runs addObject:@{','deferredRow=[@{')
replace('@"scope_events":scope?scope.events:@[]}];','@"scope_events":scope?scope.events:@[]}mutableCopy];')
tail=''' }}
 if(scope)[scope restore];BOOL restored=object_getClass(d)==original;emit(@{@"mode":mode,@"native_reference":@(KP_DATAFLOW_NATIVE),@"device":d.name,@"registry_id":@(d.registryID),@"runs":runs,@"API_refusals":@(APIrefusals),@"producer_info":info,@"producer_import":importProof,@"scope_restored":@(restored),@"CPU_expected_answers_uploaded":@NO,@"IR_CPU_read_before_execution":@NO,@"performance_benchmark":@NO,@"system_modified":@NO});return restored?0:13;'''
newtail=''' } // Every caller-owned scope/ICB/plan/pipeline/resource local has left its pool.
 @autoreleasepool{
  NSMutableDictionary*life=[@{@"variant":variant,@"caller_pool_drained_before_commit":@YES,@"caller_bundle_retained":@(callerOwners!=nil),@"main_status_before_commit":@(pending.status),@"device_restored_before_commit":@(object_getClass(d)==nativeDeviceClass),@"plan_alive_before_commit":@(weakPlan!=nil),@"scope_alive_before_commit":@(weakScope!=nil),@"ICB_alive_before_commit":@(weakICB!=nil),@"record_alive_before_commit":@(weakRecord!=nil),@"binding_record_alive_before_commit":@(weakBinding!=nil),@"root_alive_before_commit":@(weakRoot!=nil),@"private_buffer_alive_before_commit":@(weakPrivate!=nil)}mutableCopy];
  if(pending.status!=MTLCommandBufferStatusNotEnqueued)return 25;
  if(!cancelled&&!done(pending))return 12;
  deferredRow[@"command_status"]=@(pending.status);deferredRow[@"committed"]=@(!cancelled);
  if(!cancelled){for(NSString*name in savedHosts){id<MTLBuffer>h=savedHosts[name];NSString*f=deferredRow[@"files"][name];[[NSData dataWithBytes:h.contents length:h.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];}if(savedWitness){NSString*f=deferredRow[@"files"][@"witness"];[[NSData dataWithBytes:savedWitness.contents length:savedWitness.length]writeToFile:[out stringByAppendingPathComponent:f]atomically:YES];}}
  if(weakScope)[weakScope restore];callerOwners=nil;pending=nil;
  for(unsigned wait=0;wait<250&&(weakPlan||weakScope||weakICB);wait++)usleep(1000);
  life[@"plan_alive_after_command_release"]=@(weakPlan!=nil);life[@"scope_alive_after_command_release"]=@(weakScope!=nil);life[@"ICB_alive_after_command_release"]=@(weakICB!=nil);life[@"record_alive_after_command_release"]=@(weakRecord!=nil);life[@"binding_record_alive_after_command_release"]=@(weakBinding!=nil);life[@"root_alive_after_command_release"]=@(weakRoot!=nil);life[@"private_buffer_alive_after_command_release"]=@(weakPrivate!=nil);life[@"device_restored_after_release"]=@(object_getClass(d)==nativeDeviceClass);life[@"abandoned_without_commit"]=@(cancelled);
  life[@"imported_writer_alive_after_release"]=@(weakWriter!=nil);deferredRow[@"lifetime"]=life;[runs addObject:deferredRow];
 }
 }
 BOOL restored=object_getClass(d)==nativeDeviceClass;emit(@{@"mode":mode,@"lifetime_variant":variant,@"native_reference":@NO,@"device":d.name,@"registry_id":@(d.registryID),@"runs":runs,@"API_refusals":@(APIrefusals),@"producer_info":finalInfo,@"producer_import":finalImport,@"scope_restored":@(restored),@"CPU_expected_answers_uploaded":@NO,@"IR_CPU_read_before_execution":@NO,@"performance_benchmark":@NO,@"system_modified":@NO});return restored?0:13;'''
replace(tail,newtail);source.write_text(s)
if a.recompile_import:
 cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(out),'-c',str(out/'KeplerProgramImport.mm'),'-o',str(out/'KeplerProgramImport.o')];r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'lifetime-MRC.stderr').write_text(r.stderr);(out/'lifetime-MRC.json').write_text(json.dumps({'argv':cmd,'exit_code':r.returncode,'MRC_object_SHA256':sha(out/'KeplerProgramImport.o')if not r.returncode else None},indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=0','-I',str(out),str(source),str(out/'KeplerProgramImport.o'),'-L',str(library),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/'lifetime-build.stdout').write_text(r.stdout);(out/'lifetime-build.stderr').write_text(r.stderr);(out/'lifetime-build.json').write_text(json.dumps({'argv':cmd,'exit_code':r.returncode,'generator_SHA256':sha(__file__),'source_client_inputs_SHA256':sha(client/'inputs.json')},indent=2)+'\n');assert not r.returncode,r.stderr[-4000:]
inp['source_hashes'][source.name]=sha(source);inp['executable_SHA256']=sha(out/'application');inp['lifetime_generator_SHA256']=sha(__file__);inp['lifetime_source_inputs_SHA256']=sha(client/'inputs.json');inp['return_ownership_annotated']=bool(a.return_header);inp['same_frozen_MRC_import_object_SHA256']=sha(out/'KeplerProgramImport.o');inp['MRC_import_recompiled']=a.recompile_import;(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n');print(json.dumps({'status':'PASS','GPU_execution':False,'runtime_unchanged':True,'library_SHA256':inp['static_library_SHA256']}))
