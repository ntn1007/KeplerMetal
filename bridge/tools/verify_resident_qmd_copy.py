#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,struct
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,portable=False):
 root=Path(root);read=lambda n:json.loads((root/n).read_text());d=read('results.json');m=read('execution/manifest.json');inp=read('inputs.json');mode=d['mode'];prep=mode=='prepare';copied=mode=='copy';local=d['local'];groups=d['groups']
 assert mode in ['prepare','copy','no_copy'] and d['registry_id']==4294968458 and d['device']=='NVIDIA GeForce GTX 880M' and d['scope_restored']
 assert not any(d[k] for k in ['system_modified','CPU_expected_answers_uploaded','intermediate_descriptor_CPU_readback','full_ICB_contract','performance_benchmark'])
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 for n,h in inp['source_SHA256'].items():assert sha(root/n)==h
 assert sha(root/'library.metallib')==inp['library_SHA256']=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 assert len(d['runs'])==3;n=local*groups;checked=invocations=guards=0;hashes={}
 for t,r in enumerate(d['runs']):
  seeds=[0x3311+t*97,0x7733+t*101];assert r['trial']==t and r['seeds']==seeds and r['local']==local and r['groups']==groups and r['before_commit_untouched'] and r['uncommitted_materialization_status']==0 and r['committed']==(not prep) and r['command_status']==(0 if prep else 4)
  assert r['copy_encoded']==(copied or prep) and r['copy_executed']==copied and r['source_QMD_address']!=r['destination_QMD_address']
  for e in r['initialization']:assert e['operation']=='initialize_resident_QMD' and e['bytes']==256 and e['GPU_blit'] and e['user_kernel_dispatches']==0 and not e['system_modified']
  e=r['resident_launch'];assert e['operation']=='resident_QMD_launch' and e['command_bytes']==24 and e['descriptor_GPU_address']==r['destination_QMD_address'] and e['CPU_QMD_uploads_in_launch']==e['CPU_constant_uploads_in_launch']==e['native_preparation_GPU_dispatches']==0 and e['owners']==2 and not e['launch_suppressed'] and not e['full_ICB_contract'] and not e['system_modified']
  assert len(r['files'])==4
  for k in [0,1]:
   active=not prep and k==(0 if copied else 1);want=bytearray(b'\xa5'*10368)
   if active:
    for i in range(n):struct.pack_into('<4I',want,64+i*16,((seeds[k]*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,groups|0x01010000,local)
   path=root/'outputs'/r['files'][k*2];assert path.read_bytes()==bytes(want),str(path);hashes[path.name]=sha(path);guards+=10368-(n*16 if active else 0)
   counter=bytearray(b'\xa5'*132);struct.pack_into('<I',counter,64,n if active else 0);path=root/'outputs'/r['files'][k*2+1];assert path.read_bytes()==bytes(counter);hashes[path.name]=sha(path);guards+=128
   if active:checked+=n*4;invocations+=n
 return {'status':'PASS_PREPARED_UNCOMMITTED' if prep else 'PASS_EXPECTED_OLD_DESTINATION' if mode=='no_copy' else 'PASS','mode':mode,'local':local,'groups':groups,'exact_uint32_words':checked,'GPU_invocations_counted':invocations,'guard_and_untouched_bytes_verified':guards,'executed_GPU_QMD_copies':3 if copied else 0,'executed_resident_launches':0 if prep else 3,'resident_launch_command_bytes_each':24,'CPU_QMD_uploads_in_launch':0,'CPU_constant_uploads_in_launch':0,'integration_level':1,'full_ICB_contract':False,'performance_benchmark':False,'raw_SHA256':hashes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
