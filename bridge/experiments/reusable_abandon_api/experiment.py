#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated real-plan witness; run only under the shared GPU lease."""
import argparse, json, os, shutil, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,check_driver_profile,commands,preflight,read,sha,write

def need(v,m):
 if not v: raise ValueError(m)
def transform(s):
 def change(old,new):
  nonlocal s
  need(s.count(old)==1,'unexpected source anchor');s=s.replace(old,new,1)
 change('struct Push{','#include "guard.inc"\nstruct Push{')
 change(' BOOL reuseEncoder=', ' BOOL witnessShared=[mode isEqual:@"ownership"];if(witnessShared)mode=@"basic";\n BOOL reuseEncoder=')
 change(' BOOL reuseEncoder=', ' id<MTLCommandBuffer>witnessStale=nil;BOOL witnessPrepared=NO;uint32_t witnessGeneration=0,witnessCompletedRefusals=0;BOOL witnessBeforeRestore=NO,witnessAfterRestore=NO;\n BOOL reuseEncoder=')
 change('  if(producer&&![plan reserveCommandIRProducerInCommandBuffer:pbuf error:&error])', '#include "plan_probe.inc"\n  if(producer&&![plan reserveCommandIRProducerInCommandBuffer:pbuf error:&error])')
 change(' if(scope)[scope restore];', ' witnessBeforeRestore=witnessPrepared&&witnessBlock(witnessStale,@selector(commit))&&witnessBlock(witnessStale,@selector(enqueue));\n if(scope)[scope restore];\n witnessAfterRestore=witnessBlock(witnessStale,@selector(commit))&&witnessBlock(witnessStale,@selector(enqueue))&&witnessStale.status==MTLCommandBufferStatusNotEnqueued;if(!witnessBeforeRestore||!witnessAfterRestore)return 87;')
 change('if(!done(main))return 12;', 'if(!done(main))return 12;NSError*doneError=nil;if([plan experimentallyAbandonReusableProducer:main error:&doneError]||!doneError)return 88;witnessCompletedRefusals++;')
 change('emit(@{@"mode":mode,@"native_reference":', 'emit(@{@"witness_completed_refusals":@(witnessCompletedRefusals),@"witness_generation":@(witnessGeneration),@"witness_prepared":@(witnessPrepared),@"witness_before_restore":@(witnessBeforeRestore),@"witness_after_restore":@(witnessAfterRestore),@"witness_stale_status":@((int)witnessStale.status),@"mode":mode,@"native_reference":')
 return s
def build(a):
 base=a.base.resolve();lib=a.library.resolve();out=a.out.resolve();preflight(out);lm=check_library(lib);i=read(base/'inputs.json')
 need(i['reusable_contexts_built'] and i['static_library_SHA256']==lm['static_library_SHA256'],'base/library mismatch')
 for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
  for n,h in i[key].items():need(sha(base/folder/n)==h,'changed base '+n)
 need(sha(base/'src/command_ir_dataflow_client.mm')==sha(BRIDGE/'tools/command_ir_dataflow_client.mm'),'current client differs')
 check_driver_profile();out.mkdir();(out/'src').mkdir()
 for n in ('guard.inc','plan_probe.inc','experiment.py'):shutil.copyfile(HERE/n,out/'src'/n)
 (out/'src/client.mm').write_text(transform((base/'src/command_ir_dataflow_client.mm').read_text()))
 run=commands(out);run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=0','-DKP_NATIVE_MSL_COMMANDS=1','-DKP_PUBLIC_ARGUMENT_ENCODER=1','-DKP_FUNCTION_ARGUMENT_ENCODER=1','-DKP_REUSABLE_CONTEXTS=1','-DKP_STABLE_PIPELINE_IDENTITIES=1','-I',out/'src','-I',base/'src',out/'src/client.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
 run('sign',['codesign','--force','--sign','-',out/'application']);run('verify',['codesign','--verify','--strict',out/'application'])
 write(out/'inputs.json',{'base_inputs_SHA256':sha(base/'inputs.json'),'library_SHA256':lm['static_library_SHA256'],'base':str(base),'frozen':{p.name:sha(p) for p in (out/'src').iterdir()},'application_SHA256':sha(out/'application'),'driver_SHA256':check_driver_profile(),'uid':os.getuid(),'GPU_dispatches':0})
 print(json.dumps({'status':'BUILD_PASS','GPU_dispatches':0}))
def run(a):
 b=a.build.resolve();out=a.out.resolve();preflight(out);x=read(b/'inputs.json');base=Path(x['base']);i=read(base/'inputs.json')
 need(x['base_inputs_SHA256']==sha(base/'inputs.json') and x['application_SHA256']==sha(b/'application') and x['driver_SHA256']==check_driver_profile() and x['uid']==os.getuid(),'build or profile changed')
 for n,h in x['frozen'].items():need(sha(b/'src'/n)==h and (n=='client.mm' or sha(HERE/n)==h),'witness changed '+n)
 for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
  for n,h in i[key].items():need(sha(base/folder/n)==h,'base changed '+n)
 out.mkdir();(out/'outputs').mkdir()
 for folder in ['src','lowered','include','assets','legacy-assets','runtime','oracles']:shutil.copytree(base/folder,out/folder)
 shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
 inp=dict(i,executable_SHA256=sha(out/'application'),kind='reusable',mode='basic',driver_SHA256=x['driver_SHA256'],native_library_factory_run=False,source_build_inputs_SHA256=x['base_inputs_SHA256'],witness_build_inputs_SHA256=sha(b/'inputs.json'))
 write(out/'inputs.json',inp);sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
 m=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'outputs'),'ownership' if a.scenario=='shared' else 'basic'],a.lab.resolve());d=read(out/'execution/execution.stdout');write(out/'results.json',d)
 if a.scenario=='shared':
  need(d['scenario']=='shared_owner' and d['refused'] and d['both_owners_retained'] and not d['producer_submitted'] and not d['system_modified'],'shared-owner refusal');print(json.dumps({'status':'PASS_SHARED_OWNER_REFUSED','PID':m['pid']}));return
 need(d['witness_prepared'] and d['witness_before_restore'] and d['witness_after_restore'] and d['witness_stale_status']==0 and d['witness_generation']==d['runs'][0]['generation'] and d['witness_completed_refusals']==4,'witness failed')
 sys.path.insert(0,str(out/'oracles'));import verify_command_ir_dataflow as oracle
 proof=oracle.verify(out);proof.update(kind='reusable',PID=m['pid'],static_library_SHA256=x['library_SHA256'],witness_build_inputs_SHA256=sha(b/'inputs.json'))
 write(out/'independent-verification.json',proof);print(json.dumps({k:v for k,v in proof.items() if k!='raw_SHA256'}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(required=True)
 b=sp.add_parser('build');b.add_argument('--base',type=Path,required=True);b.add_argument('--library',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.set_defaults(fn=build)
 r=sp.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--lab',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--scenario',choices=['positive','shared'],default='positive');r.set_defaults(fn=run);a=p.parse_args();a.fn(a)
