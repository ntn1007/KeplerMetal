#!/usr/bin/env python3
"""Independent packet, resource-bound, lifetime and CPU raster oracle."""
from pathlib import Path
import argparse, base64, hashlib, json, math, struct
from decode_native_commands import decode

LIB='c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43'
ACTIVE=[[0,1,2],[0],[1],[2],[0],[],[0,1,2],[0,1],[0,1]]
PLAN=[ [('smooth',64,2,3),('linear',64,17,5),('flat',64,64,3)],
       [('smooth',64,2,3)], [('linear',64,17,5)], [('flat',64,64,3)],
       [('smooth',1024,2,3)], [],
       [('smooth',1024,2,3),('linear',64,17,5),('flat',64,64,3)],
       [('linear',64,17,5),('flat',64,64,3)],
       [('linear',64,17,5),('flat',64,64,3)] ]

def require(value,message):
    if not value: raise ValueError(message)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def macro(count,instances,base): return struct.pack('<6I',0xa0050ea8,4,count,instances,5,base)

def raster(image,vbo,ibo,vertex_offset,instance_offset,instances,base,interpolation,rect,inline=None):
    x0,y0,w,h=rect
    for instance in range(base,base+instances):
        offsets=inline if inline is not None else struct.unpack_from('<4f',ibo,instance_offset+16*instance)
        vertices=[]
        for i in range(5,11):
            v=struct.unpack_from('<8f',vbo,vertex_offset+32*i)
            vertices.append(((v[0]/v[3]+offsets[0]+1)*32,
                (1-v[1]/v[3]-offsets[1])*24,v[3],
                (v[4],v[5],v[6]+instance/64+offsets[2],v[7])))
        for start in (0,3):
            a,b,c=vertices[start:start+3]
            area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            require(abs(area)>1e-12,'fixture unexpectedly degenerate')
            # Derivation from clip coordinates and barycentric interpolation;
            # no values from the GPU output participate in the expectation.
            for y in range(y0,y0+h):
                for x in range(x0,x0+w):
                    dx,dy=x+.5-a[0],y+.5-a[1]
                    l1=(dx*(c[1]-a[1])-dy*(c[0]-a[0]))/area
                    l2=((b[0]-a[0])*dy-(b[1]-a[1])*dx)/area
                    weights=[1-l1-l2,l1,l2]
                    if min(weights)<-1e-10: continue
                    if interpolation=='flat': color=a[3]
                    else:
                        if interpolation=='smooth':
                            weights=[t/v[2] for t,v in zip(weights,(a,b,c))]
                            divisor=sum(weights);weights=[t/divisor for t in weights]
                        color=[sum(t*v[3][k] for t,v in zip(weights,(a,b,c))) for k in range(4)]
                    image[y*64+x]=color

def verify(root,current=False,portable=False):
    inputs=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text())
    process=json.loads((root/'execution/manifest.json').read_text());control=d['native_one_vertex_control'];execute=d['mode']=='execute'
    require(process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'],'probe not successfully terminal')
    if not portable:
        require(sha(root/'cpu_icb_vertex_probe')==process['original_binary_sha256'] and sha(root/'execution/cpu_icb_vertex_probe')==process['signed_binary_sha256'],'host executable hash differs')
    require(d['passed'] and d['scope_restored'] and d['registry_id']==4294968458,'device/scope differs')
    require(d['integration_level']==1 and not any(d[k] for k in ('system_modified','full_ICB_contract','GPU_resident_ICB','performance_benchmark')),'qualification scope differs')
    require(sha(root/'vertex_io_carrier.metallib')==inputs['library_SHA256']==d['library_SHA256']==LIB,'vertex library differs')
    require(sha(root/'render_state_carrier.metallib')==inputs['legacy_library_SHA256']=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7','legacy library differs')
    require(sha(root/'cpu_icb_vertex_profiles.json')==inputs['manifest_SHA256']==d['manifest_SHA256'],'manifest differs')
    for name,h in inputs['source_hashes'].items():
        require(sha(root/name)==h,'frozen source differs: '+name)
        if current:
            folder='src' if name.startswith('Kepler') or name.endswith('.json') else 'tools'
            require(sha(Path(__file__).resolve().parents[1]/folder/name)==h,'current source differs: '+name)
    negatives={'foreign_pipeline','vertex_index','unaligned_vertex','fragment_binding','missing_vertex_binding','short_vertex_range','short_instance_range','wrong_library_hash','wrong_manifest_hash'}
    require({r['case'] for r in d['rejections']}==negatives and all(r['rejected'] for r in d['rejections']),'negative controls missing')
    require(len(d['runs'])==(1 if control or not execute else 9),'run count differs')
    registered=[e for e in d['events'] if e['operation']=='register_render_vertex_library']
    require(len(registered)==1 and registered[0]['max_vertex_bindings']==2 and not registered[0]['registration_is_GPU_qualification'],'registration evidence differs')
    material=[e for e in d['events'] if e['operation']=='materialize_CPU_render_command']
    require(len(material)==(0 if control else 4 if execute else 3) and all(e['GPU_render_dispatches']==0 for e in material),'materialization differs')
    maximum=0;channels=colored=records=0;rawhash={};out=root/'outputs'
    def load(name):
        p=out/name;rawhash[name]=sha(p);return p.read_bytes()
    for trial,run in enumerate(d['runs']):
        require(run['trial']==trial and run['committed']==execute and run['buffers_private'],'trial/storage differs')
        require(run['command_status']==(4 if execute else 0),'command completion differs')
        e=run['execution_event'];plans=[] if control else PLAN[trial]
        rect=(3,4,13,9) if trial==1 else (0,0,64,48);require(run['scissor']==list(rect),'scissor differs')
        if control:
            require(e=={'operation':'native_one_vertex_control','vertex_count':1,'instances':64,'base_instance':3,'ICB_executed':False},'native control differs')
        else:
            require(e['operation']=='execute_CPU_render_ICB' and e['executed_indices']==ACTIVE[trial],'range/copy/reset differs')
            require(e['caller_vertex_slots_restored']==(2 if plans else 0),'caller buffer restoration trace differs')
            ev=e['evidence'];rs=ev.get('sequence_records',[]);require(len(rs)==len(plans),'record count differs')
            if plans:
                require(ev['raw_records_copied']==len(plans) and ev['native_draw_API_calls_during_encoding']==len(plans) and ev['record_leases_until_completion'] and ev['resource_usage_declared'] and not ev['GPU_resident_ICB'] and e['caller_pipeline_restored'],'transport/restoration trace differs')
            for j,(r,plan) in enumerate(zip(rs,plans)):
                name,offset,instances,base=plan;meta=r['record'];raw=load(f'trial-{trial}.record-{j}.commands.bin');prefix=load(f'trial-{trial}.record-{j}.prefix.bin')
                require(meta['name']==name and meta['vertex_start']==5 and meta['vertex_count']==6 and meta['instances']==instances and meta['base_instance']==base,'pipeline/geometry differs')
                require(meta['library_SHA256']==LIB and meta['manifest_SHA256']==d['manifest_SHA256'] and not meta['recording_command_buffer_committed'] and not meta['native_shader_code_patched'],'record provenance differs')
                require(raw==macro(6,instances,base)==base64.b64decode(r['commands_base64']) and hashlib.sha256(raw).hexdigest()==meta['SHA256'],'actual native command memory differs')
                require(base64.b64decode(r['primer_draw_base64'])==macro(1,instances,base) and r['primer_vertex_count']==1 and r['native_primer_draw_removed'],'one-vertex causal primer differs')
                require(prefix==base64.b64decode(r['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==r['prefix_SHA256'] and r['primer_bytes']==len(prefix)+24 and r['native_state_prefix_preserved_bytes']==len(prefix),'actual retained state prefix differs')
                packets=decode(prefix) if prefix else []
                if packets and packets[0]['method']=='0xe04':
                    require(len(packets)>=16,'incomplete scissor state');x,y,w,h=rect
                    for i,p in enumerate(packets[:16]): require(p['method']==hex(0xe04+i*16) and p['values']==[x|((x+w)<<16),y|((y+h)<<16)],'inherited scissor differs')
                    packets=packets[16:]
                require(not packets or len(packets)==1 and packets[0]['method']=='0x3ab0' and packets[0]['values']==[0],'unknown native state prefix')
                require([(b['index'],b['offset'],b['length'],b['storage_mode']) for b in meta['bindings']]==[(0,offset,4096,2),(1,128,2048,2)],'vertex/instance binding evidence differs')
                records+=1
        before=load(f'trial-{trial}.before.bin');after=load(f'trial-{trial}.after.bin');vbo=load(f'trial-{trial}.vertices.input.bin');ibo=load(f'trial-{trial}.instances.input.bin')
        require(before==b'\xa5'*49664 and len(after)==49664 and after[:256]==before[:256] and after[-256:]==before[-256:],'readback/guards differ')
        if execute:
            require(load(f'trial-{trial}.vertices.after.bin')==vbo and load(f'trial-{trial}.instances.after.bin')==ibo,'private input bytes or guards changed')
            image=[(0.,0.,0.,0.) for _ in range(3072)]
            for name,offset,instances,base in plans:raster(image,vbo,ibo,offset,128,instances,base,name,rect)
            ordinary=not control and trial in (0,3,8);require(run['ordinary_native_draw_after_ICB']==ordinary,'caller draw differs')
            if ordinary:raster(image,vbo,ibo,1024,256,1,0,'linear',(0,0,16,48),inline=(0,0,.3125,0) if trial%2 else None)
            actual=struct.unpack_from('<12288f',after,256)
            for i,expected in enumerate(image):
                colored+=expected[3]!=0
                for k in range(4):
                    v=actual[4*i+k];error=abs(v-expected[k]);maximum=max(maximum,error)
                    require(math.isfinite(v) and error<=2e-6,f'GPU/CPU pixel differs trial={trial} xy={(i%64,i//64)} channel={k} GPU={v} CPU={expected[k]}')
            channels+=12288
        else:require(after==before,'uncommitted prepare changed readback')
    if execute and not control:
        require(d['runs'][-1]['scope_and_resources_released_before_commit'] and d['runs'][-1]['classes_restored_before_commit'],'pending-command lifetime control missing')
    return {'status':'PASS','mode':d['mode'],'native_one_vertex_control':control,'main_command_buffers':len(d['runs']) if execute else 0,'copied_draw_records':records,'correct_float32_channels':channels,'colored_pixels':colored,'maximum_float_error':maximum,'tolerance':2e-6,'negative_controls':len(negatives),'all_children_terminal':True,'integration_level':1,'GPU_resident_ICB':False,'performance_benchmark':False,'source_sha256':inputs['source_hashes'],'raw_sha256':rawhash}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();d=verify(a.root.resolve(),a.current,a.portable);text=json.dumps(d,indent=2)+'\n'
    if a.out:a.out.write_text(text)
    print(json.dumps({k:v for k,v in d.items() if k not in ('raw_sha256','source_sha256')},indent=2))
