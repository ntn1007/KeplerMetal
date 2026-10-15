#!/usr/bin/env python3
"""Independent native fragment argument-buffer packet and numeric image oracle."""
from pathlib import Path
import argparse,base64,hashlib,json,math,struct
from decode_native_commands import decode
LIB='45c98ce0a295f0cde1a2396c90e60f6a4e2154f2cccf2f30191e65b124c48bbf'
ACTIVE=[[0,1,2],[0],[1],[2],[0],[0,1,2],[],[0,1,2]]
def require(v,msg):
 if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def macro(n):return struct.pack('<6I',0xa0050e0c,4,n,1,0,0)
def color(data,params,x,y,linear):
 p=struct.unpack_from('<8f',params,256)
 if linear:
  x1=min(x+1,63);y1=min(y+1,47);a=struct.unpack_from('<4f',data,(y*64+x)*16);b=struct.unpack_from('<4f',data,(y*64+x1)*16);c=struct.unpack_from('<4f',data,(y1*64+x)*16);d=struct.unpack_from('<4f',data,(y1*64+x1)*16);v=[a[k]*.75*.875+b[k]*.25*.875+c[k]*.75*.125+d[k]*.25*.125 for k in range(4)]
 else:v=struct.unpack_from('<4f',data,(y*64+x)*16)
 return [v[k]*p[k]+p[k+4] for k in range(4)]
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());proc=json.loads((root/'execution/manifest.json').read_text());execute=d['mode']=='execute'
 require(proc['exit_code']==0 and not proc['SIGKILL_requested'] and not proc['authoritative_ps_status'],'child not successfully terminal')
 if not portable:require(sha(root/'cpu_icb_fragment_probe')==proc['original_binary_sha256'] and sha(root/'execution/cpu_icb_fragment_probe')==proc['signed_binary_sha256'],'host executable differs')
 require(d['passed'] and d['scope_restored'] and d['registry_id']==4294968458 and d['integration_level']==1 and not any(d[k] for k in ('system_modified','GPU_resident_ICB','full_ICB_contract','performance_benchmark')),'scope differs')
 require(sha(root/'fragment_resources.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB and sha(root/'cpu_icb_fragment_profiles.json')==inp['manifest_SHA256']==d['manifest_SHA256'],'library/manifest differs')
 for n,h in inp['source_hashes'].items():
  require(sha(root/n)==h,'frozen source differs')
  if current:require(sha(Path(__file__).resolve().parents[1]/('src' if n.startswith('Kepler') or n.endswith('.json') else 'tools')/n)==h,'current source differs: '+n)
 require({r['case'] for r in d['rejections']}=={'fragment_alignment','fragment_index','copy_fragment_capacity','referenced_buffer_range','uncertified_argument_buffer','modified_argument_payload'} and all(r['rejected'] for r in d['rejections']),'negative controls differ')
 require(len(d['runs'])==(8 if execute else 1),'trial count differs');out=root/'outputs';rawhash={};channels=colored=records=0;maximum=0
 def load(n):p=out/n;rawhash[n]=sha(p);return p.read_bytes()
 for trial,r in enumerate(d['runs']):
  require(r['trial']==trial and r['committed']==execute and r['command_status']==(4 if execute else 0),'trial/status differs');e=r['execution_event'];require(e['executed_indices']==ACTIVE[trial] and e['caller_vertex_slots_restored']==0 and e['caller_fragment_slots_restored']==(1 if ACTIVE[trial] else 0),'range/copy/reset/restore differs')
  rs=e['evidence'].get('sequence_records',[]);require(len(rs)==len(ACTIVE[trial]),'record count differs')
  if rs:require(e['caller_pipeline_restored'] and e['evidence']['resource_usage_declared'] and e['evidence']['record_leases_until_completion'],'caller/resources trace differs')
  for j,(row,slot) in enumerate(zip(rs,ACTIVE[trial])):
   m=row['record'];raw=load(f'trial-{trial}.record-{j}.commands.bin');prefix=load(f'trial-{trial}.record-{j}.prefix.bin');require(m['name']==['read','nearest','linear'][slot] and m['library_SHA256']==LIB and m['manifest_SHA256']==d['manifest_SHA256'] and m['bindings']==[] and m['fragment_buffers']==1 and m['direct_method']==0x3830 and m['vertex_start']==0 and m['vertex_count']==3 and m['instances']==1 and m['base_instance']==0,'record ABI differs')
   require(raw==macro(3)==base64.b64decode(row['commands_base64']) and hashlib.sha256(raw).hexdigest()==m['SHA256'] and base64.b64decode(row['primer_draw_base64'])==macro(1) and row['native_primer_draw_removed'],'actual copied causal packet differs')
   require(prefix==base64.b64decode(row['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'] and row['primer_bytes']==len(prefix)+24,'retained prefix differs');ps=decode(prefix) if prefix else []
   if ps and ps[0]['method']=='0xe04':
    require(len(ps)>=16,'scissor framing differs')
    for k,p in enumerate(ps[:16]):require(p['method']==hex(0xe04+k*16) and p['values']==[64<<16,48<<16],'scissor data differs')
    ps=ps[16:]
   require(not ps or len(ps)==1 and ps[0]['method']=='0x3ab0' and ps[0]['values']==[0],'unknown state prefix');records+=1
  textures=[load(f'trial-{trial}.texture-{i}.input.bin') for i in range(2)];params=[load(f'trial-{trial}.params-{i}.bin') for i in range(4)];args=[load(f'trial-{trial}.arguments-{i}.bin') for i in range(4)]
  for i in range(2):
   expected=bytearray()
   for y in range(48):
    for x in range(64):expected+=struct.pack('<4f',((x*3+y*5+(i+trial%2)*7)&63)/64,((x*7+y*11+(i+trial%2)*3)&63)/64,(((x^y)+(i+trial%2)*5)&31)/32,1)
   require(textures[i]==expected,'texture input differs')
  for i in range(4):
   require(len(params[i])==512 and params[i][:256]==b'\xa5'*256 and params[i][288:]==b'\xa5'*224 and len(args[i])==1024 and args[i][:256]==b'\xa5'*256 and args[i][280:]==b'\xa5'*744,'parameter/argument guards differ')
  require(struct.unpack_from('<8f',params[0],256)==(1,1,1,1,0,0,0,0) and struct.unpack_from('<8f',params[1],256)==(.5,1.5,1,1,.125,0,0,0),'parameter contract differs')
  before=load(f'trial-{trial}.before.bin');after=load(f'trial-{trial}.after.bin');require(before==b'\xa5'*49664 and after[:256]==before[:256] and after[-256:]==before[-256:],'image guards differ')
  if not execute:require(after==before,'uncommitted prepare changed image');continue
  last=ACTIVE[trial][-1] if ACTIVE[trial] else None;ordinary=trial in (0,5);require(r['ordinary_native_draw_after_ICB']==ordinary,'caller control differs');actual=struct.unpack_from('<12288f',after,256)
  for y in range(48):
   for x in range(64):
    if ordinary and x<16:expected=color(textures[0],params[3],x,y,False)
    elif last is None:expected=(0,0,0,0)
    else:
     tex,param=(1,1) if last==1 or last==0 and trial>=4 else (0,last);expected=color(textures[tex],params[param],x,y,last==2)
    colored+=expected[3]!=0
    for k in range(4):
     v=actual[(y*64+x)*4+k];error=abs(v-expected[k]);maximum=max(maximum,error);require(math.isfinite(v) and error<=2e-6,f'pixel differs trial={trial} xy={(x,y)} component={k} GPU={v} CPU={expected[k]}')
  channels+=12288
 if execute:require(d['runs'][-1]['classes_restored_before_commit'],'pending-command scope restore control missing')
 return {'status':'PASS','mode':d['mode'],'main_command_buffers':8 if execute else 0,'copied_draw_records':records,'correct_float32_channels':channels,'colored_pixels':colored,'maximum_error':maximum,'tolerance':2e-6,'native_fragment_argument_buffer_bindings_qualified':execute,'texture_read_nearest_linear_qualified':execute,'parameter_payload_and_resource_updates_qualified':execute,'caller_fragment_buffers_and_inline_restore_qualified':execute,'negative_controls':6,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'GPU_resident_ICB':False,'performance_benchmark':False,'source_sha256':inp['source_hashes'],'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('source_sha256','raw_sha256')},indent=2))
