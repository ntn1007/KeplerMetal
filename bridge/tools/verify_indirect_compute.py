#!/usr/bin/env python3
"""Check exact raw values, geometry, invocation counter and missing-producer control."""
from pathlib import Path
import argparse,hashlib,json,struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve();cases=json.loads((root/'results.json').read_text());records=[];invocations=0;negative_bad=0;captures=0;positive_words=0
direct={}
for case in cases:
 result=case['result'];local=result['local'];groups=result['groups'];mode=result['mode'];missing=mode=='missing_producer'
 assert result['passed'] and result['native_only'] and result['args_private'] and not result['args_CPU_read_before_dispatch'] and not result['ICB_created']
 assert result['registry_id']==4294968458 and result['device']=='NVIDIA GeForce GTX 880M'
 assert not case['process']['SIGKILL_requested'] and not case['process']['authoritative_ps_status']
 runs=[]
 for run in result['runs']:
  base=Path(run['base']);out=base.with_suffix('.bin').read_bytes();args=base.with_suffix('.args').read_bytes();counter=base.with_suffix('.count').read_bytes()
  assert len(out)==640*16+128 and len(args)==140 and len(counter)==132
  for raw in [out,args,counter]:assert raw[:64]==raw[-64:]==bytes([0xa5])*64
  actual_groups=1 if missing else groups;n=actual_groups*local;seed=0x1234+37*run['iteration'];assert seed==run['seed']
  assert struct.unpack_from('<I',counter,64)[0]==n==run['actual_invocations']
  assert struct.unpack_from('<3I',args,64)==((groups if mode=='GPU_indirect' else 1),1,1)
  values=struct.unpack_from('<'+str(n*4)+'I',out,64);wanted=[]
  for i in range(n):wanted.extend([((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,actual_groups|0x01010000,local])
  assert list(values)==wanted and out[64+n*16:-64]==bytes([0xa5])*(640-n)*16
  assert run['command_status']==run['readback_status']==4 and not run['mismatches'] and not run['guard_mismatches']
  key=(local,groups,run['iteration'])
  if mode=='direct':direct[key]=out
  if mode=='GPU_indirect':assert direct[key]==out
  intended_bad=0
  if missing:
   full=struct.unpack_from('<'+str(groups*local*4)+'I',out,64);expected=[]
   for i in range(groups*local):expected.extend([((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,groups|0x01010000,local])
   intended_bad=sum(v!=w for v,w in zip(full,expected));assert intended_bad>0 and n<groups*local;negative_bad+=intended_bad
  else:positive_words+=n*4
  invocations+=n;captures+=3;runs.append({'iteration':run['iteration'],'actual_invocations':n,'intended_full_output_bad_words':intended_bad,'output_SHA256':hashlib.sha256(out).hexdigest()})
 records.append({'name':case['name'],'status':'PASS_NEGATIVE_CONTROL' if missing else 'PASS','runs':runs})
manifest=json.loads((root/'manifest.json').read_text())
for file,h in manifest['source_hashes'].items():assert hashlib.sha256((root/file).read_bytes()).hexdigest()==h
assert hashlib.sha256((root/'indirect_compute_probe.metallib').read_bytes()).hexdigest()==manifest['library_sha256']
summary={'status':'PASS','configurations':len(records),'direct_cases':sum(c['result']['mode']=='direct' for c in cases),
 'GPU_indirect_cases':sum(c['result']['mode']=='GPU_indirect' for c in cases),'negative_cases':sum(c['result']['mode']=='missing_producer' for c in cases),
 'raw_captures':captures,'consumer_invocations_counted':invocations,'correct_positive_uint32_words':positive_words,
 'incorrect_intended_words_in_negative_controls':negative_bad,'guard_mismatches':0,'CPU_read_of_arguments_before_dispatch':False,
 'ICB_implemented':False,'performance_benchmark':False,'results':records,
 'scope':'GPU-generated Private indirect compute arguments and geometry validated against direct dispatch; existing native primitive, not ICB object/command-stream support.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
