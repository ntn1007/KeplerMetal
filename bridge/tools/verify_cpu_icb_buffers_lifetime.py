#!/usr/bin/env python3
"""Raw vector-input/output oracle and observed ownership checks; no GPU calls."""
import argparse,hashlib,json,struct
from pathlib import Path
def require(x,s):
 if not x:raise ValueError(s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode']
 require(mode in ('prepare','execute') and d['scope_restored'] and d['integration_level']==1 and not d['system_modified'],'scope differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 require(sha(root/'cpu_icb_buffers.metallib')==inp['library_SHA256']=='ba0f51c96f993240f9637f0b848e14a5362e125d9c5cdf2aa38efd518531a8fd' and sha(root/'cpu_icb_buffers.json')=='0c5f52ae67fdc53da8b9d43544b88173f67c4bdbe69e15797432315f6a55ca66','library/manifest differs')
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs: '+name)
  if current:
   folder='src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools';require(sha(Path(__file__).resolve().parents[1]/folder/name)==h,'current source differs: '+name)
 if not portable:require(sha(root/'cpu_icb_buffers_lifetime_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_buffers_lifetime_probe')==m['signed_binary_sha256'],'host binary differs')
 require(len(d['cases'])==3,'lifetime cases missing');raw={};processed=0
 for test,row in enumerate(d['cases']):
  retained=test!=1;active=retained and mode=='execute';require(row['case']==test and row['retainedReferences']==retained and row['main_command_buffer_committed']==active and row['unretained_negative_never_submitted']==(not retained),'unsafe negative or missing positive submission')
  require(all(row[k] for k in ['ICB_released_before_commit','encoder_released_before_commit','scope_released_before_commit','device_class_restored_before_commit']) and row['automatic_scope_release']==(test==2) and row['private_bindings_alive_after_scope_release']==[retained]*3,'native binding ownership/restoration differs')
  seed=0x1234+101*test;a=[];b=[]
  for i in range(8192):
   for k in range(4):a.append(float((i*13+k*7+seed)%127)-63.0);b.append((float((i*19+k*11+seed)%61)-30.0)*0.5)
  payloads=[struct.pack('<32768f',*[x*2+y for x,y in zip(a,b)]) if active else b'\xa5'*(8192*16),struct.pack('<32768f',*a),struct.pack('<32768f',*b)]
  for kind,key in enumerate(['out','a','b']):
   offset=[128,64,256][kind];p=root/f'outputs/case-{test}.{key}.bin';require(p.read_bytes()==b'\xa5'*offset+payloads[kind]+b'\xa5'*(1024-offset),'vector/input preservation/guards differ');raw[p.name]=sha(p)
  require(row['mismatches']==0,'host disagrees with raw data');processed+=8192 if active else 0
 return {'status':'PASS','mode':mode,'processed_float4_elements':processed,'correct_float32_values':processed*4,'default_private_bindings_alive_after_caller_release':True,'unretained_negative_never_submitted':True,'automatic_scope_restoration_before_submit':True,'raw_files_verified':len(raw),'all_children_terminal':True,'system_modified':False,'integration_level':1,'ICB_contract_complete':False,'performance_benchmark':False,'host_executable_SHA256_rechecked':not portable,'portable_raw_verification_only':portable,'raw_SHA256':raw,'verifier_SHA256':sha(Path(__file__))}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable);(root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
