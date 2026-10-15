#!/usr/bin/env python3
"""Independent raw oracle: consumer output, QMD writes and native CB changes."""
from pathlib import Path
import argparse,hashlib,json,struct
from decode_native_commands import decode
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve()
cases=json.loads((root/'results.json').read_text());records=[];direct={};positive_words=negative_bad=invocations=qmd_updates=cb_updates=raw_files=0
recorded_root=Path(cases[0]['process']['original_executable']).parent
def resolve_capture(path):
 # Raw verification also works after extracting this cohort on another host.
 return root/Path(path).relative_to(recorded_root)
def u32(raw,o):return struct.unpack_from('<I',raw,o)[0]
def sha(raw):return hashlib.sha256(raw).hexdigest()
for case in cases:
 result=case['result'];mode=result['mode'];local=result['local'];groups=result['groups'];missing=mode=='missing_producer';native_indirect=mode!='direct'
 assert result['passed'] and result['native_only'] and result['registry_id']==4294968458
 assert result['args_private'] and not result['args_CPU_read_before_dispatch'] and not result['ICB_created']
 assert case['process']['exit_code']==0 and not case['process']['SIGKILL_requested'] and not case['process']['authoritative_ps_status']
 for run in result['runs']:
  base=resolve_capture(run['base']);raw={ext:Path(str(base)+ext).read_bytes() for ext in ['.bin','.args','.count','.qmd','.cb']}
  assert len(raw['.bin'])==10368 and len(raw['.args'])==140 and len(raw['.count'])==132
  assert len(raw['.qmd'])==4224 and len(raw['.cb'])==393344
  for value in raw.values():assert value[:64]==value[-64:]==b'\xa5'*64
  actual=1 if missing else groups;n=actual*local;seed=0x1234+run['iteration']*37;assert run['seed']==seed
  expected=[]
  for i in range(n):expected.extend([((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,actual|0x01010000,local])
  assert list(struct.unpack_from('<'+str(n*4)+'I',raw['.bin'],64))==expected
  assert raw['.bin'][64+n*16:-64]==b'\xa5'*(640-n)*16
  assert u32(raw['.count'],64)==n==run['actual_invocations'] and struct.unpack_from('<3I',raw['.args'],64)==((groups if mode=='GPU_indirect' else 1),1,1)
  assert run['command_status']==run['readback_status']==4 and run['guard_mismatches']==run['mismatches']==0
  key=(local,groups,run['iteration'])
  if mode=='direct':direct[key]=raw['.bin']
  elif mode=='GPU_indirect':assert direct[key]==raw['.bin']
  if missing:
   observed=struct.unpack_from('<'+str(groups*local*4)+'I',raw['.bin'],64);intended=[]
   for i in range(groups*local):intended.extend([((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,groups|0x01010000,local])
   bad=sum(v!=w for v,w in zip(observed,intended));assert bad>0;negative_bad+=bad
  else:positive_words+=n*4
  commands=resolve_capture(run['encoding_file']).read_bytes();assert sha(commands)==run['encoding_SHA256'] and len(commands)==run['encoding_bytes']
  packets=decode(commands);assert len(commands)==(1052 if native_indirect else 464)
  upload_state={};descriptors={};uploads=[];launches=[];selection=None
  for packet in packets:
   if packet.get('subchannel')!=1:continue
   for method,value in zip(packet.get('method_addresses',[]),packet.get('values',[])):
    method=int(method,16)
    if method in [0x180,0x184,0x188,0x18c,0x1b0]:upload_state[method]=value
   if packet.get('method')=='0x1b4':
    target=(upload_state[0x188]<<32)|upload_state[0x18c];payload=struct.pack('<'+str(len(packet['values']))+'I',*packet['values']);assert len(payload)==upload_state[0x180]
    if run['qmd_GPU_address']<=target<run['qmd_GPU_address']+run['qmd_bytes']:
     assert len(payload)==256;descriptors[target]=payload
    else:uploads.append((target,payload))
   if packet.get('method')=='0x2b4':selection=packet['values'][0]<<8
   if packet.get('method')=='0x2bc':assert packet['values']==[3] and selection in descriptors;launches.append(selection)
  assert launches==([run['qmd_GPU_address']+256,run['qmd_GPU_address']] if native_indirect else [run['qmd_GPU_address']])
  gpuQMD=raw['.qmd'][64:-64];gpuCB=raw['.cb'][64:-64];changes=[]
  for target,cpu in descriptors.items():
   offset=target-run['qmd_GPU_address'];gpu=gpuQMD[offset:offset+256];expected_gpu=bytearray(cpu);helper=offset==256
   if helper:assert native_indirect and u32(cpu,0x30)==1 and u32(cpu,0x34)==65537 and u32(cpu,0x48)>>16==1
   else:
    assert u32(cpu,0x48)>>16==local
    assert (u32(cpu,0x30),u32(cpu,0x34))==((0,0) if native_indirect else (groups,65537))
    if native_indirect:struct.pack_into('<2I',expected_gpu,0x30,actual,65537)
   assert gpu==expected_gpu,'Unexpected QMD mutation'
   delta=[i for i in range(0,256,4) if cpu[i:i+4]!=gpu[i:i+4]];assert delta==([0x30,0x34] if native_indirect and not helper else [])
   qmd_updates+=len(delta);changes.append({'GPU_address':target,'helper':helper,'changed_word_offsets':delta,'CPU_SHA256':sha(cpu),'GPU_SHA256':sha(gpu),'program_offset':u32(cpu,32),'GPR':(u32(cpu,0xb8)>>24)&63})
  cb_changes=[]
  for target,cpu in uploads:
   offset=target-run['state_CB_GPU_address'];assert 0<=offset<=run['state_CB_bytes']-len(cpu)
   gpu=gpuCB[offset:offset+len(cpu)];wanted=bytearray(cpu)
   if offset==0x6f0 and native_indirect:
    for field,vals in [(0x10,(actual,1,1)),(0x30,(n,1,1)),(0x50,(actual,1,1))]:
     assert struct.unpack_from('<3I',cpu,field)==(0,0,0);struct.pack_into('<3I',wanted,field,*vals)
   assert gpu==wanted,'Unexpected native constant-state mutation'
   delta=[i for i in range(0,len(cpu),4) if cpu[i:i+4]!=gpu[i:i+4]]
   assert delta==([0x10,0x14,0x18,0x30,0x34,0x38,0x50,0x54,0x58] if offset==0x6f0 and native_indirect else [])
   cb_updates+=len(delta);cb_changes.append({'offset':offset,'bytes':len(cpu),'changed_word_offsets':delta,'CPU_SHA256':sha(cpu),'GPU_SHA256':sha(gpu)})
  assert len(uploads)==(3 if native_indirect else 1);invocations+=n;raw_files+=6
  records.append({'case':case['name'],'iteration':run['iteration'],'status':'PASS_NEGATIVE_CONTROL' if missing else 'PASS','actual_invocations':n,'descriptor_changes':changes,'constant_state_changes':cb_changes,'raw_SHA256':{k:sha(v) for k,v in raw.items()},'encoding_SHA256':sha(commands)})
manifest=json.loads((root/'manifest.json').read_text());assert sha((root/'indirect_descriptor_readback.mm').read_bytes())==manifest['source_SHA256'] and sha((root/'indirect_compute_probe.metallib').read_bytes())==manifest['library_SHA256']
summary={'status':'PASS','configurations':len(cases),'iterations':len(records),'raw_capture_files':raw_files,'consumer_invocations':invocations,'correct_positive_uint32_words':positive_words,'incorrect_intended_words_negative_controls':negative_bad,'QMD_words_changed':qmd_updates,'constant_state_words_changed':cb_updates,'all_other_uploaded_bytes_preserved':True,'guard_mismatches':0,'ICB_implemented':False,'performance_benchmark':False,'system_modifications':False,'Qwen_job_ids':[],'scope':'Private GPU-produced dispatch arguments, encoded helper and GPU readback show native descriptor grid plus builtin constant-state updates. Internal helper SASS not captured; no native command replay or API extension.','records':records}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
