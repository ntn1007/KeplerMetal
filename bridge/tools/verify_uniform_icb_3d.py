#!/usr/bin/env python3
"""Independent 3D-coordinate and native-dimension oracle, no GPU execution."""
import argparse,hashlib,json,struct,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from decode_native_commands import decode
LIBRARY='5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0'
MANIFEST='fa081fc43d24d54873d069006f9581f6b73b631f505ed9b854cb3429107ec4f3'
GROUPS=[(3,5,1),(2,3,4),(3,2,2),(2,1,1),(1,1,1),(3,5,2)]
LOCAL=[(8,4,1),(4,2,2),(5,3,2),(1,1,64),(32,32,1),(8,4,2)]
ACTIVE=[list(range(6)),[1,2,3],list(range(6)),list(range(6)),list(range(6)),[0],[]]
def require(v,s):
 if not v:raise ValueError(s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def u32(d,o):return struct.unpack_from('<I',d,o)[0]
def dimensions(trial,node):return ((2,2,2),(4,4,4)) if node==0 and trial>=3 else (GROUPS[node],LOCAL[node])
def packed(d):return d[0]|d[1]<<10|d[2]<<20
def verify(root,current=False,portable=False):
 root=Path(root).resolve();inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=inp['mode'];form=inp['form'];lease=m['GPU_reservation']
 require(mode in ('prepare','execute') and form in ('groups','threads') and d==json.loads((root/'execution/execution.stdout').read_text()),'mode or result differs')
 require(d['mode']==mode and d['dispatch_form']==form and d['registry_id']==inp['registry_id'] and d['scope_restored'] and d['integration_level']==1 and not d['system_modified'] and not d['ICB_contract_complete'],'scope differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live'],'child not successfully terminal')
 require(m['arguments']==[str(root/'assets/cpu_icb_grid3d.metallib'),str(root/'assets/cpu_icb_grid3d.json'),str(root/'outputs'),mode,form,str(inp['registry_id'])],'host arguments differ')
 require(sha(root/'assets/cpu_icb_grid3d.metallib')==inp['library_SHA256']==LIBRARY and sha(root/'assets/cpu_icb_grid3d.json')==inp['manifest_SHA256']==MANIFEST,'library/manifest differs')
 for name,h in inp['frozen'].items():require(sha(root/name)==h,'frozen source differs: '+name)
 require(sha(root/'runtime_archive.a')==inp['runtime_archive_SHA256'] and sha(root/'application')==m['original_binary_sha256']==inp['executable_SHA256'] and sha(root/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'host or archive differs')
 require(m['launcher_SHA256']==inp['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==inp['frozen']['runtime/lab_gpu_reservation.py'],'launcher differs')
 require({r['case'] for r in d['rejections']}=={'zero_dimension','local_z_over64','local_product_over1024','grid_product_over_contract','partial_x','partial_y','partial_z','zero_local'} and len(d['rejections'])==8 and all(r['rejected'] for r in d['rejections']),'invalid-dimension controls missing')
 events=d['events'];material=[e for e in events if e['operation']=='materialize_CPU_command'];executions=[e for e in events if e['operation']=='executeCommandsInBuffer'];count=7 if mode=='execute' else 1
 require(len(d['runs'])==len(executions)==count and len(material)==(7 if mode=='execute' else 6),'trial/materialization count differs')
 raw={};out=root/'outputs';program=None;invocations=words=0
 def load(name):
  p=out/name;raw[name]=sha(p);return p.read_bytes()
 for prefix in ['before','materialized-0']+(['materialized-3'] if mode=='execute' else []):
  for node in range(6):
   for key in ['coordinates','geometry']:require(load(f'{prefix}-{node}.{key}.bin')==b'\xa5'*(2048*16+128),'pre-commit output changed')
   require(load(f'{prefix}-{node}.counter.bin')==b'\xa5'*64+bytes(4)+b'\xa5'*64,'pre-commit kernel counted')
 for trial,(run,event) in enumerate(zip(d['runs'],executions)):
  active=ACTIVE[trial];require(run['trial']==trial and event['executed_indices']==active,'range selection differs');stream=load(f'trial-{trial}.commands.bin');ev=event['evidence'];require(len(stream)==464*len(active),'native stream size differs')
  if active:
   require(hashlib.sha256(stream).hexdigest()==ev['stream_SHA256'] and ev['command_bytes']==len(stream) and ev['native_preparation_API_calls']==1 and ev['native_preparation_GPU_dispatches']==0 and ev['raw_packet_copies']==len(active),'stream/primer differs')
  else:require(not ev,'empty source ICB emitted work')
  for element,node in enumerate(active):
   part=stream[element*464:(element+1)*464];ps=decode(part);e=ev['elements'][element];r=e['relocation'];g,l=dimensions(trial,node);full=tuple(x*y for x,y in zip(g,l))
   require([p['method'] for p in ps]==['0x180','0x1b0','0x1b4','0x180','0x1b0','0x1b4','0x2b4','0x2bc','0x110'],'packet framing differs');require(hashlib.sha256(part).hexdigest()==e['commands_SHA256']==r['relocated_SHA256'] and r['function']=='grid_coordinates' and r['library_SHA256']==LIBRARY,'program identity differs')
   require(r['groups_shape']==list(g) and r['local_shape']==list(l),'record lost dimensions')
   builtin=ps[2]['values'];require(builtin[:3]==list(l) and builtin[4:7]==list(g) and builtin[8:11]==[0,0,0] and builtin[12:15]==list(full),'native builtin XYZ constants differ')
   qmd=part[184:440];require(u32(qmd,0x30)==g[0] and u32(qmd,0x34)==g[1]|g[2]<<16 and u32(qmd,0x48)>>16==l[0] and u32(qmd,0x4c)==l[1]|l[2]<<16 and qmd[187]==21 and qmd[0x50]==6,'QMD XYZ/GPR differs')
   cb=r['dedicated_CB_GPU_address'];qd=r['dedicated_QMD_GPU_address'];require((ps[0]['values'][2]<<32)|ps[0]['values'][3]==cb+0x6f0 and (ps[3]['values'][2]<<32)|ps[3]['values'][3]==qd and ps[6]['values']==[qd>>8] and ps[7]['values']==[3] and ps[8]['values']==[0],'relocation/launch differs')
   require(len(r['bindings'])==4 and all(b['native_table_address']==b['GPU_address']+b['offset'] for b in r['bindings']),'buffer binding table differs')
   offset=u32(qmd,0x20);require(offset and (program is None or program==offset),'native program changed');program=offset
  if mode=='prepare':require(not run['main_command_buffer_committed'],'prepare submitted user work');continue
  require(run['command_status']==4 and run['selected_buffer']==('copy' if trial in (4,5) else 'source'),'source/copy execution differs')
  for node in range(6):
   g,l=dimensions(trial,node);full=tuple(x*y for x,y in zip(g,l));n=math.prod(full);seed=0x1234+37*trial+101*node;c=bytearray();geo=bytearray()
   if node in active:
    for z in range(full[2]):
     for y in range(full[1]):
      for x in range(full[0]):
       index=x+full[0]*(y+full[1]*z);c.extend(struct.pack('<4I',x,y,z,index));geo.extend(struct.pack('<4I',packed((x%l[0],y%l[1],z%l[2])),packed((x//l[0],y//l[1],z//l[2])),packed(g),packed(l)^seed))
    invocations+=n;words+=8*n
   for key,payload in [('coordinates',c),('geometry',geo)]:require(load(f'trial-{trial}-node-{node}.{key}.bin')==b'\xa5'*64+payload+b'\xa5'*(2048*16+64-len(payload)),'coordinate/local/group/builtin payload or guard differs')
   count=n if node in active else 0;require(load(f'trial-{trial}-node-{node}.counter.bin')==b'\xa5'*64+struct.pack('<I',count)+b'\xa5'*64,'atomic invocation count/guards differ')
 if mode=='execute':require(invocations==18632 and words==149056,'experiment totals differ')
 return {'status':'PASS','mode':mode,'form':form,'gpu_registry_id':inp['registry_id'],'GPU_user_submissions':7 if mode=='execute' else 0,'GPU_invocations_counted':invocations,'correct_uint32_words':words,'dimensions_2D_3D_native_QMD_and_builtin_checked':True,'local_1024_and_Z64_tested':mode=='execute','raw_files_verified':len(raw),'materialized_commands':len(material),'dimension_rejection_controls':8,'reshape_and_CPU_copy_preserve_dimensions':mode=='execute','all_children_terminal':True,'scope_restored':True,'system_modified':False,'integration_level':1,'ICB_contract_complete':False,'GPU_resident_ICB':False,'performance_benchmark':False,'host_executable_SHA256_rechecked':not portable,'portable_raw_verification_only':portable,'raw_SHA256':raw,'verifier_SHA256':sha(Path(__file__))}
if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1]).resolve()),sort_keys=True))
