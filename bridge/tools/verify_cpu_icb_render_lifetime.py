#!/usr/bin/env python3
from pathlib import Path
import argparse,base64,hashlib,json,struct
from decode_native_commands import decode
from verify_cpu_icb_render import draw,index_bytes,require,sha,LIBRARY
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];require(mode in ('prepare','execute') and d['passed'] and d['registry_id']==4294968458,'mode/device differs')
 require(d['scope_and_ICB_released_before_commit'] and d['private_indices_alive_before_commit'] and d['device_encoder_classes_restored'] and not d['system_modified'] and not d['full_ICB_contract'],'lifetime/scope differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 require(sha(root/'render_state_carrier.metallib')==inp['library_SHA256']==d['library_SHA256']==LIBRARY,'library differs')
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs')
  if current:require(sha(Path(__file__).resolve().parents[1]/('src' if name.startswith('Kepler') else 'tools')/name)==h,'current source differs')
 if not portable:require(sha(root/'cpu_icb_render_lifetime_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_render_lifetime_probe')==m['signed_binary_sha256'],'host binaries differ')
 hashes={};out=root/'outputs'
 def load(name):p=out/name;hashes[name]=sha(p);return p.read_bytes()
 for kind in (1,2):require(load(f'lifetime.indices{16 if kind==1 else 32}.bin')==index_bytes(kind),'private index/guards differs')
 events=[x for x in d['events'] if x['operation']=='execute_CPU_render_ICB'];require(len(events)==1 and events[0]['executed_indices']==[1,2],'range differs');ev=events[0]['evidence'];stream=load('lifetime.commands.bin');prefix=load('lifetime.prefix.bin');require(len(stream)==120 and len(prefix)==192 and hashlib.sha256(stream).hexdigest()==ev['stream_SHA256'] and prefix==base64.b64decode(ev['native_state_prefix_base64']),'stream/prefix differs')
 for i,(meta,kind) in enumerate(zip(ev['records'],[1,2])):draw(stream[i*60:(i+1)*60],meta,kind)
 require(len(ev['records'])==2 and ev['record_leases_until_completion'] and ev['native_primer_draw_removed'] and ev['native_primer_bytes']==216,'lease/primer differs')
 ps=decode(prefix);require(len(ps)==16,'prefix count differs')
 for i,p in enumerate(ps):require(p['subchannel']==0 and p['method_addresses']==[hex(0xe04+i*16),hex(0xe08+i*16)] and p['values']==[(30<<16)|9,(41<<16)|30],'inherited scissor differs')
 before=load('lifetime.before.bin');after=load('lifetime.after.bin');require(before==b'\xa5'*49664,'pre-commit bytes changed')
 if mode=='prepare':require(not d['committed'] and after==before,'prepare submitted/rendered')
 else:
  require(d['committed'] and d['command_status']==4 and d['colored_pixels']==231 and not d['mismatches'],'GPU completion differs');expected=bytearray(b'\xa5'*256)
  for y in range(48):
   for x in range(64):expected.extend(struct.pack('<4f',.75,.125,.25,1) if 9<=x<30 and 30<=y<41 else bytes(16))
  expected.extend(b'\xa5'*256);require(after==bytes(expected),'CPU pixel/guard oracle differs')
 return {'status':'PASS','mode':mode,'correct_float32_channels':12288 if mode=='execute' else 0,'GPU_render_command_buffers':1 if mode=='execute' else 0,'caller_scope_ICB_released':True,'private_indices_retained':True,'device_encoder_classes_restored':True,'all_children_terminal':True,'integration_level':1,'full_ICB_contract':False,'system_modified':False,'raw_files_verified':len(hashes),'raw_SHA256':hashes,'host_executable_SHA256_rechecked':not portable,'portable_raw_verification_only':portable,'verifier_SHA256':sha(Path(__file__))}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable);(root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
