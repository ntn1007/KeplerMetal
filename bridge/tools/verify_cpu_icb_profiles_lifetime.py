#!/usr/bin/env python3
"""Recompute the three native-program lifetime client's raw results, no GPU calls."""
import argparse,hashlib,json,struct
from pathlib import Path
LIBRARY='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(c,s):
 if not c:raise ValueError(s)
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode']
 require(mode in ('prepare','execute') and d['scope_restored'] and d['registered_pipelines']==3 and d['integration_level']==1 and not d['system_modified'],'scope differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 require(sha(root/'cpu_icb_profiles.metallib')==inp['library_SHA256']==LIBRARY,'library differs')
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs: '+name)
  if current:
   folder='src' if name.startswith('Kepler') or name.endswith('.metal') else 'tools'
   require(sha(Path(__file__).resolve().parents[1]/folder/name)==h,'current source differs: '+name)
 if not portable:
  require(sha(root/'cpu_icb_profiles_lifetime_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_profiles_lifetime_probe')==m['signed_binary_sha256'],'host executable differs')
 require(all(c['exit_code']==0 for c in json.loads((root/'commands.json').read_text())),'build/observation failed')
 require(len(d['cases'])==3,'lifetime cases missing');raw={};invocations=words=0
 for test,row in enumerate(d['cases']):
  retained=test!=1;submitted=retained and mode=='execute';n=99 if submitted else 0
  require(row['case']==test and row['retainedReferences']==retained and row['main_command_buffer_committed']==submitted and row['unretained_negative_never_submitted']==(test==1),'unsafe negative submission or missing positive')
  require(all(row[k] for k in ['ICB_released_before_commit','encoder_released_before_commit','scope_released_before_commit','device_class_restored_before_commit']),'caller objects not released/restored')
  require(row['automatic_scope_release']==(test==2),'automatic restoration differs')
  require(len(row['weak_owner_observations_after_scope_release'])==len(row['outputs'])==3,'owner/node observations missing')
  for node,owners in enumerate(row['weak_owner_observations_after_scope_release']):
   require(owners['node']==node and owners['output']==owners['counter']==retained and (not retained or owners['pipeline']),'native private binding/pipeline lost before commit')
   seed=0x7654+97*test+101*node;payload=bytearray()
   for i in range(n):
    first=((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff)
    if node==1:first=struct.unpack('<I',struct.pack('<f',(i&31)*0.5+(seed&255)))[0]
    if node==2:neighbor=(i//33)*33+(i%33+1)%33;first=((seed*1664525)&0xffffffff)^((neighbor*1013904223)&0xffffffff)
    payload.extend(struct.pack('<4I',first,i,0x01010003,33))
   expected=b'\xa5'*64+payload+b'\xa5'*(10368-64-len(payload));out=root/f'outputs/case-{test}-node-{node}.output.bin';counter=root/f'outputs/case-{test}-node-{node}.counter.bin'
   require(out.read_bytes()==expected,'native lifetime numerical output differs')
   require(counter.read_bytes()==b'\xa5'*64+struct.pack('<I',n)+b'\xa5'*64,'native lifetime invocation count/guards differ')
   r=row['outputs'][node];require(r['node']==node and r['seed']==seed and r['actual_invocations']==n and r['mismatches']==0,'host record disagrees with raw output')
   raw[out.name]=sha(out);raw[counter.name]=sha(counter);invocations+=n;words+=4*n
 require(invocations==(594 if mode=='execute' else 0) and words==4*invocations,'lifetime totals differ')
 return {'status':'PASS','mode':mode,'lifetime_cases':3,'registered_native_programs':3,'GPU_submitted_user_buffers':2 if mode=='execute' else 0,'GPU_user_invocations':invocations,'correct_uint32_words':words,'raw_files_verified':len(raw),'private_bindings_and_three_pipelines_alive_after_ICB_scope_release':True,'unretained_negative_never_submitted':True,'automatic_scope_restoration_before_submit':True,'all_children_terminal':True,'system_modified':False,'integration_level':1,'performance_benchmark':False,'ICB_contract_complete':False,'host_executable_SHA256_rechecked':not portable,'portable_raw_verification_only':portable,'raw_SHA256':raw,'verifier_SHA256':sha(Path(__file__)),'limitation':'Weak owner instrumentation checks these bounded synchronous cases. General compiler cache destruction, concurrent mutation and GPU-generated ICBs are not qualified.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable)
 (root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
