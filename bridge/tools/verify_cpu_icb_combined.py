#!/usr/bin/env python3
"""Independent indexed command, GPU producer, resource and raster oracle."""
from pathlib import Path
import argparse,base64,hashlib,json,math,struct
from decode_native_commands import decode
LIB='3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775'
COMPUTE='7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911'
ACTIVE=[[0],[1],[2],[1],[3],[3],[3],[],[1],[],[0,1,2,3],[0,1,2]]
PRODUCER=[False,False,False,False,True,True,False,True,False,False,True,False]
S0=('smooth',1,'indices16',6,2,-2,3)
S1=('smooth',2,'indices32',6,64,-2,3)
S2=('flat',1,'indices16',6,2,-2,3)
S3=('linear',2,'produced',3,17,5,5)
PLAN=[[('smooth',1,'indices16',6,2,5,3)],[('linear',2,'indices32',6,17,5,5)],[S2],[S1],[('smooth',2,'produced',3,2,5,3)],[S3],[S3],[],[S1],[],[S0,S1,S2,S3],[S0,S1,S2]]
def require(v,msg):
 if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def packet(meta,count):
 start=meta['index_GPU_address']+64;end=meta['index_GPU_address']+127
 return struct.pack('<15I',0x20010591,0,0x200505f2,start>>32,start&0xffffffff,end>>32,end&0xffffffff,meta['kind'],0xa0060eaa,4,count,meta['instances'],0,meta['base_vertex']&0xffffffff,meta['base_instance'])

def raster(image,vbo,ibo,vertex_offset,instance_offset,instances,base,interpolation,rect,inline=None,fetches=None,texture=None,fragment_params=None,sample_mode=None):
    x0,y0,w,h=rect
    for instance in range(base,base+instances):
        offsets=inline if inline is not None else struct.unpack_from('<4f',ibo,instance_offset+16*instance)
        vertices=[]
        for i in (fetches if fetches is not None else range(5,11)):
            v=struct.unpack_from('<8f',vbo,vertex_offset+32*i)
            vertices.append(((v[0]/v[3]+offsets[0]+1)*32,
                (1-v[1]/v[3]-offsets[1])*24,v[3],
                (v[4],v[5],v[6]+instance/64+offsets[2],v[7])))
        for start in range(0,len(vertices),3):
            a,b,c=vertices[start:start+3]
            area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            if abs(area)<1e-12: continue
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
                    if texture is not None:
                        if sample_mode=='linear':
                            x1=min(x+1,63);y1=min(y+1,47);ts=[struct.unpack_from('<4f',texture,(yy*64+xx)*16) for xx,yy in [(x,y),(x1,y),(x,y1),(x1,y1)]];sample=[ts[0][k]*.75*.875+ts[1][k]*.25*.875+ts[2][k]*.75*.125+ts[3][k]*.25*.125 for k in range(4)]
                        else:sample=struct.unpack_from('<4f',texture,(y*64+x)*16)
                        p=struct.unpack_from('<8f',fragment_params,256);color=[sample[k]*color[k]*p[k]+p[k+4] for k in range(4)]
                    image[y*64+x]=color

def verify(root,current=False,portable=False):
    inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());process=json.loads((root/'execution/manifest.json').read_text());execute=d['mode']=='execute'
    require(process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'],'child not successfully terminal')
    if not portable:require(sha(root/'cpu_icb_combined_probe')==process['original_binary_sha256'] and sha(root/'execution/cpu_icb_combined_probe')==process['signed_binary_sha256'],'host executable differs')
    require(d['passed'] and d['scope_restored'] and d['registry_id']==4294968458 and d['integration_level']==1 and not any(d[k] for k in ('system_modified','full_ICB_contract','GPU_resident_ICB','performance_benchmark')),'device/scope differs')
    require(sha(root/'combined_render_resources.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB and sha(root/'cpu_icb_gpu_indices.metallib')==inp['compute_library_SHA256']==d['compute_library_SHA256']==COMPUTE,'libraries differ')
    require(sha(root/'cpu_icb_combined_profiles.json')==inp['manifest_SHA256']==d['manifest_SHA256'] and sha(root/'cpu_icb_gpu_indices.json')==inp['compute_manifest_SHA256']==d['compute_manifest_SHA256']=='225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be','manifests differ')
    for name,h in inp['source_hashes'].items():
        require(sha(root/name)==h,'frozen source differs')
        if current:require(sha(Path(__file__).resolve().parents[1]/('src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools')/name)==h,'current source differs: '+name)
    require({r['case'] for r in d['rejections']}=={'index_alignment','index_range','index_count','base_vertex_limit','copy_binding_capacity'} and all(r['rejected'] for r in d['rejections']),'negative controls differ')
    require(len(d['runs'])==(12 if execute else 1),'trial count differs');out=root/'outputs';rawhash={};channels=colored=records=invocations=0;maximum=0;producer_address=None
    def load(name):p=out/name;rawhash[name]=sha(p);return p.read_bytes()
    for trial,r in enumerate(d['runs']):
        require(r['trial']==trial and r['committed']==execute and r['command_status']==(4 if execute else 0) and r['no_CPU_read_between_compute_and_render'] and r['producer_expected']==PRODUCER[trial],'trial/status differs')
        inputs={name:load(f'trial-{trial}.{name}.input.bin') for name in ('vertices','instances','indices16','indices32','produced','counter')}
        params=load(f'trial-{trial}.parameters.bin');require(len(params)==1536 and params[:256]==b'\xa5'*256 and params[272:]==b'\xa5'*(1536-272) and struct.unpack_from('<4I',params,256)==(int(trial==5),0x4400+trial,0,0),'parameters or guards differ')
        for name,wide,bias in [('indices16',False,7 if trial>=2 else 0),('indices32',True,7 if trial>=3 else 0)]:
            expected=bytearray(b'\xa5'*128);struct.pack_into('<6I' if wide else '<6H',expected,64,*range(bias,bias+6));require(inputs[name]==expected,'static index input differs')
        produced=bytearray(b'\xa5'*128);counter=bytearray(b'\xa5'*132);struct.pack_into('<4I',produced,64,0,0,0,0x77777777);struct.pack_into('<I',counter,64,0)
        require(inputs['produced']==produced and inputs['counter']==counter,'initial safe index/counter differs')
        ce=r['compute_event'];compute=load(f'trial-{trial}.compute.bin');require(ce['executed_indices']==([0] if PRODUCER[trial] else []),'producer range differs')
        if PRODUCER[trial]:
            cv=ce['evidence'];require(len(compute)==464 and hashlib.sha256(compute).hexdigest()==cv['stream_SHA256'] and cv['native_preparation_GPU_dispatches']==0,'compute stream differs');ps=decode(compute)
            require([p['method'] for p in ps]==['0x180','0x1b0','0x1b4','0x180','0x1b0','0x1b4','0x2b4','0x2bc','0x110'],'compute method framing differs');qmd=compute[184:440];rel=cv['elements'][0]['relocation']
            require(qmd[187]==7 and qmd[0x50]==6 and rel['function']=='gpu_indices' and rel['library_SHA256']==COMPUTE and rel['groups_shape']==[1,1,1] and rel['local_shape']==[32,1,1],'native program/geometry differs')
            bindings={b['index']:b for b in rel['bindings']};require(bindings[0]['offset']==64 and bindings[0]['length']==128 and bindings[1]['offset']==64 and bindings[1]['length']==132 and bindings[2]['offset']==256,'producer binding bounds differ');address=bindings[0]['GPU_address']
            if producer_address is not None:require(address==producer_address,'producer output resource changed')
            producer_address=address
        else:require(not compute and not ce['evidence'],'missing producer emitted commands')
        e=r['execution_event'];require(e['executed_indices']==ACTIVE[trial],'render range/reset/copy differs');rs=e['evidence'].get('sequence_records',[]);require(len(rs)==len(PLAN[trial]) and e['caller_vertex_slots_restored']==(2 if rs else 0),'render records/caller binding restore differ')
        if rs:require(e['caller_fragment_slots_restored']==1,'caller fragment state not restored');require(e['caller_pipeline_restored'] and e['evidence']['resource_usage_declared'] and e['evidence']['record_leases_until_completion'],'caller/residency/lifetime trace differs')
        for j,(row,plan) in enumerate(zip(rs,PLAN[trial])):
            name,kind,source,count,instances,base_vertex,base_instance=plan;meta=row['record'];raw=load(f'trial-{trial}.record-{j}.commands.bin');prefix=load(f'trial-{trial}.record-{j}.prefix.bin')
            require(meta['fragment_buffers']==1,'fragment buffer missing');require((meta['name'],meta['kind'],meta['index_count'],meta['instances'],meta['base_vertex'],meta['base_instance'])==(name,kind,count,instances,base_vertex,base_instance),'indexed PSO/arguments differ')
            require(meta['library_SHA256']==LIB and meta['manifest_SHA256']==d['manifest_SHA256'] and meta['indexed_vertex_domain']=={'minimum':5,'maximum':10} and meta['index_buffer_storage_mode']==2 and meta['index_offset']==64 and meta['index_buffer_length']==128 and not meta['recording_command_buffer_committed'] and not meta['native_shader_code_patched'] and not meta['CPU_read_of_index_contents_during_materialization'],'indexed provenance/domain differs')
            require(raw==packet(meta,count)==base64.b64decode(row['commands_base64']) and hashlib.sha256(raw).hexdigest()==meta['SHA256'],'actual copied indexed packets differ')
            require(base64.b64decode(row['primer_draw_base64'])==packet(meta,1) and row['primer_vertex_count']==1 and row['native_primer_draw_removed'],'one-index causal primer differs')
            require(prefix==base64.b64decode(row['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'] and row['primer_bytes']==len(prefix)+60 and row['native_state_prefix_preserved_bytes']==len(prefix),'actual preserved prefix differs')
            ps=decode(prefix) if prefix else []
            if ps and ps[0]['method']=='0xe04':
                require(len(ps)>=16,'scissor prefix truncated')
                for k,p in enumerate(ps[:16]):require(p['method']==hex(0xe04+k*16) and p['values']==[64<<16,48<<16],'inherited scissor differs')
                ps=ps[16:]
            require(not ps or len(ps)==1 and ps[0]['method']=='0x3ab0' and ps[0]['values']==[0],'unknown prefix')
            require([(b['index'],b['offset'],b['length'],b['storage_mode']) for b in meta['bindings']]==[(0,64,4096,2),(1,128,2048,2)],'stage-in bounds differ')
            if source=='produced' and producer_address is not None:require(meta['index_GPU_address']==producer_address,'GPU producer/consumer use different resources')
            records+=1
        texture=load(f'trial-{trial}.texture.input.bin');fgparams=[load(f'trial-{trial}.fragment-params-{j}.bin') for j in range(4)];fgargs=[load(f'trial-{trial}.arguments-{j}.bin') for j in range(4)]
        expected_texture=bytearray()
        for y in range(48):
            for x in range(64):expected_texture+=struct.pack('<4f',((x*3+y*5+(trial%2)*7)&63)/64,((x*7+y*11+(trial%2)*3)&63)/64,(((x^y)+(trial%2)*5)&31)/32,1)
        require(texture==expected_texture,'texture payload differs')
        for j in range(4):require(len(fgparams[j])==512 and fgparams[j][:256]==b'\xa5'*256 and fgparams[j][288:]==b'\xa5'*224 and len(fgargs[j])==1024 and fgargs[j][:256]==b'\xa5'*256 and fgargs[j][280:]==b'\xa5'*744,'fragment resource guards differ')
        before=load(f'trial-{trial}.before.bin');after=load(f'trial-{trial}.after.bin');require(before==b'\xa5'*49664 and len(after)==49664 and before[:256]==after[:256] and before[-256:]==after[-256:],'image readback guards differ')
        if not execute:require(after==before,'uncommitted prepare changed readback');continue
        if PRODUCER[trial]:
            values=(1,1,1) if trial==5 else (0,1,2);struct.pack_into('<4I',produced,64,*values,0x4400+trial);struct.pack_into('<I',counter,64,32);invocations+=32
        expected_payloads={**inputs,'produced':bytes(produced),'counter':bytes(counter)}
        for name,expected in expected_payloads.items():require(load(f'trial-{trial}.{name}.after.bin')==expected,'GPU input/output/guard mismatch: '+name)
        image=[(0.,0.,0.,0.) for _ in range(3072)]
        for name,kind,source,count,instances,base_vertex,base_instance in PLAN[trial]:
            payload=expected_payloads[source];indices=struct.unpack_from('<'+('H' if kind==1 else 'I')*count,payload,64);fetches=[i+base_vertex for i in indices];require(all(5<=i<=10 for i in fetches),'actual fixture indices exceed declared domain')
            raster(image,inputs['vertices'],inputs['instances'],64,128,instances,base_instance,name,(0,0,64,48),fetches=fetches,texture=texture,fragment_params=fgparams[['smooth','linear','flat'].index(name)],sample_mode=name)
        ordinary=trial in (0,3,11);require(r['ordinary_native_draw_after_ICB']==ordinary,'ordinary caller draw differs')
        if ordinary:raster(image,inputs['vertices'],inputs['instances'],1024,256,1,0,'linear',(0,0,16,48),inline=(0,0,.3125,0) if trial%2 else None,texture=texture,fragment_params=fgparams[3],sample_mode='linear')
        actual=struct.unpack_from('<12288f',after,256)
        for i,expected in enumerate(image):
            colored+=expected[3]!=0
            for k in range(4):
                v=actual[4*i+k];error=abs(v-expected[k]);maximum=max(maximum,error);require(math.isfinite(v) and error<=2e-6,f'pixel differs trial={trial} xy={(i%64,i//64)} channel={k} GPU={v} CPU={expected[k]}')
        channels+=12288
    if execute:require(invocations==128 and d['runs'][-1]['classes_restored_before_commit'] and d['runs'][-1]['scope_and_local_refs_released_before_commit'],'counted GPU work/lifetime differs')
    return {'status':'PASS','mode':d['mode'],'main_command_buffers':12 if execute else 0,'copied_indexed_records':records,'GPU_compute_invocations_counted':invocations,'correct_float32_channels':channels,'colored_pixels':colored,'maximum_float_error':maximum,'tolerance':2e-6,'negative_controls':5,'combined_indexed_fragment_resources_qualified':execute,'indices16_32_and_signed_base_vertex_qualified':execute,'GPU_generated_UInt32_indices_qualified':execute,'CPU_index_read_before_submission':False,'index_domain_checked_after_GPU_execution':execute,'general_untrusted_index_domain_enforcement':False,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'GPU_resident_ICB':False,'performance_benchmark':False,'source_sha256':inp['source_hashes'],'raw_sha256':rawhash}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();d=verify(a.root.resolve(),a.current,a.portable);text=json.dumps(d,indent=2)+'\n'
    if a.out:a.out.write_text(text)
    print(json.dumps({k:v for k,v in d.items() if k not in ('source_sha256','raw_sha256')},indent=2))
