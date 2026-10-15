#!/usr/bin/env python3
"""Independent native-render packet, private-index and pixel oracle."""
from pathlib import Path
import argparse, hashlib, json, struct
from decode_native_commands import decode
LIBRARY = '965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
RECTS = [(3,4,13,9),(25,8,11,17),(9,30,21,11)]
SELECTIONS = [[0,1,2],[0,1,2],[0,2],[1],[],[0,1,2],[0,1,2],[0,1,2]]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok, message):
    if not ok: raise ValueError(message)
def packet_oracle(raw, meta, kind):
    packets = decode(raw); require(len(packets) == (17 if kind == 0 else 19), 'packet count differs')
    require(len(raw) == (216 if kind == 0 else 252), 'record size differs')
    require(hashlib.sha256(raw).hexdigest() == meta['SHA256'] and len(raw) == meta['bytes'], 'record hash differs')
    require(meta['kind'] == kind and meta['scissor'] == list(RECTS[kind]) and not meta['recording_command_buffer_committed'] and not meta['native_shader_code_patched'], 'record profile differs')
    x,y,w,h = RECTS[kind]
    for i,p in enumerate(packets[:16]):
        require(p['subchannel'] == 0 and p['kind'] == 'incrementing' and p['method_addresses'] == [hex(0xe04+i*16),hex(0xe08+i*16)] and p['values'] == [(x+w)<<16|x,(y+h)<<16|y], 'scissor fields differ')
    if kind:
        start = meta['index_GPU_address'] + meta['index_offset']; end = meta['index_GPU_address'] + meta['index_buffer_length'] - 1
        require(meta['index_buffer_length'] == (128 if kind == 1 else 192) and meta['index_offset'] == (64 if kind == 1 else 96), 'index allocation differs')
        require(packets[16]['subchannel'] == 0 and packets[16]['method'] == '0x1644' and packets[16]['values'] == [0], 'restart state differs')
        require(packets[17]['subchannel'] == 0 and packets[17]['method'] == '0x17c8' and packets[17]['values'] == [start>>32,start&0xffffffff,end>>32,end&0xffffffff,kind], 'private index address/type differs')
    draw = packets[-1]; values = [4,3,2 if kind == 2 else 1,0,0] + ([0] if kind else [])
    require(draw['subchannel'] == 0 and draw['kind'] == 'one_increment' and draw['method'] == ('0x3840' if kind else '0x3830') and draw['values'] == values, 'draw macro fields differ')
    return len(packets)
def index_bytes(kind, degenerate=False):
    size,offset,fmt = (128,64,'<3H') if kind == 1 else (192,96,'<3I')
    raw = bytearray(b'\xa5'*size); values = ((0,0,0) if kind == 1 else (1,1,1)) if degenerate else (0,1,2)
    struct.pack_into(fmt,raw,offset,*values); return bytes(raw)
def verify(root, current=False, portable=False):
    inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text())
    mode=d['mode'];require(mode in ('prepare','execute') and d['passed'] and d['registry_id']==4294968458,'mode/device differs')
    require(d['integration_level']==1 and not d['system_modified'] and not d['native_shader_code_patched'] and not d['render_ICB_implemented'] and not d['GPU_resident_ICB'] and not d['recording_buffers_committed'],'scope differs')
    require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
    require(sha(root/'render_state_carrier.metallib')==inp['library_SHA256']==d['library_SHA256']==LIBRARY,'library differs')
    for name,h in inp['source_hashes'].items():
        require(sha(root/name)==h,'frozen source differs')
        if current:
            folder='src' if name.startswith('Kepler') else 'tools';require(sha(Path(__file__).resolve().parents[1]/folder/name)==h,'current source differs: '+name)
    if not portable:
        require(sha(root/'native_render_replay_probe')==m['original_binary_sha256'] and sha(root/'execution/native_render_replay_probe')==m['signed_binary_sha256'],'host binary differs')
    out=root/'outputs';hashes={}
    def load(name):
        p=out/name;hashes[name]=sha(p);return p.read_bytes()
    original=[]
    for kind,row in enumerate(d['records']):
        raw=load(f'record-{kind}.commands.bin');require(row['raw']['saved'] and row['raw']['SHA256']==hashes[f'record-{kind}.commands.bin'],'record artifact differs');packet_oracle(raw,row['record'],kind);original.append(raw)
    for label in ['initial']+(['lifetime'] if mode=='execute' else []):
        for kind in (1,2):require(load(f'{label}.indices{16 if kind==1 else 32}.bin')==index_bytes(kind),'uploaded private index/guards differs')
    if mode=='execute':
        require(load('degenerate.indices16.bin')==index_bytes(1,True) and load('degenerate.indices32.bin')==index_bytes(2,True),'GPU patched private indices/guards differs')
    require(d['range_rejection'] and len(d['runs'])==(8 if mode=='execute' else 1),'range/trials differs')
    floats=colored_total=replay_float=0;checks=[]
    for trial,run in enumerate(d['runs']):
        selected=SELECTIONS[trial];require(run['trial']==trial and run['selected']==selected and not run['mismatches'],'trial selection or observed mismatches differs')
        before=load(f'trial-{trial}.before.bin');after=load(f'trial-{trial}.after.bin');require(before==b'\xa5'*49664,'pre-commit readback changed')
        for key,raw in [('before',before),('after',after)]:require(hashlib.sha256(raw).hexdigest()==run[key]['SHA256'] and len(raw)==run[key]['bytes'],'image raw hash differs')
        if mode=='execute' and trial==0:require(run['native_control'] and not run['evidence'] and not run['stream'],'native control unexpectedly used replay')
        else:
            require(not run['native_control'],'replay used native control');ev=run['evidence'];stream=load(f'trial-{trial}.commands.bin')
            require(len(stream)==ev['stream_bytes'] and hashlib.sha256(stream).hexdigest()==ev['stream_SHA256']==run['stream']['SHA256'] and ev['native_primer_bytes']==24 and ev['native_primer_prefix_preserved']==0 and ev['native_primer_draw_removed'] and ev['native_draw_API_calls_during_encoding']==1,'replay/primer framing differs')
            require(ev['cursor_after']==ev['cursor_before']+len(stream) and ev['raw_records_copied']==len(selected) and ev['record_leases_until_completion'] and not ev['render_ICB_implemented'] and not ev['GPU_resident_ICB'],'replay scope differs')
            offset=0
            for index,row in zip(selected,ev['elements']):
                require(row['index']==index,'record order differs');n=216 if index==0 else 252;part=stream[offset:offset+n];offset+=n;packet_oracle(part,row['record'],index)
                if trial!=5:require(part==original[index],'reused record modified')
            require(offset==len(stream) and len(ev['elements'])==len(selected),'record framing differs')
        if mode=='prepare':require(not run['committed'] and after==before,'prepare committed or rendered');continue
        require(run['committed'] and run['command_status']==4,'render did not complete')
        expected=bytearray(b'\xa5'*256);colored=0
        for y in range(48):
            for x in range(64):
                covered=any(not (index==1 and trial>=6 or index==2 and trial>=7) and RECTS[index][0]<=x<RECTS[index][0]+RECTS[index][2] and RECTS[index][1]<=y<RECTS[index][1]+RECTS[index][3] for index in selected)
                colored+=covered;expected.extend(struct.pack('<4f',.75,.125,.25,1) if covered else bytes(16))
        expected.extend(b'\xa5'*256);require(after==bytes(expected) and run['colored_pixels']==colored,'CPU pixel or guard oracle differs')
        require(run['caller_release_lifetime']==(trial==5) and run['weak_batch_record_private_index_alive_before_commit'],'lifetime evidence differs')
        floats+=12288;colored_total+=colored;replay_float+=12288 if trial else 0;checks.append({'trial':trial,'colored_pixels':colored,'native_control':trial==0,'GPU_private_index_controls':trial in (6,7)})
    if mode=='execute':require(floats==98304 and replay_float==86016 and colored_total==2605,'totals differ')
    require(d['GPU_user_render_command_buffers']==(8 if mode=='execute' else 0) and d['GPU_index_upload_command_buffers']==(4 if mode=='execute' else 1),'submission totals differ')
    return {'status':'PASS','mode':mode,'GPU_render_command_buffers':8 if mode=='execute' else 0,
        'correct_float32_channels_including_native_control':floats,'correct_replay_float32_channels':replay_float,
        'colored_pixels_total':colored_total,'private_indices_UInt16_UInt32_GPU_data_dependence_qualified':mode=='execute',
        'caller_release_lifetime_qualified':mode=='execute','exact_instance_invocation_count_qualified':False,
        'raw_files_verified':len(hashes),'raw_SHA256':hashes,'trials':checks,'all_children_terminal':True,
        'integration_level':1,'render_ICB_implemented':False,'GPU_resident_ICB':False,'native_shader_code_patched':False,
        'performance_benchmark':False,'system_modified':False,'portable_raw_verification_only':portable,
        'host_executable_SHA256_rechecked':not portable,'verifier_SHA256':sha(Path(__file__)),
        'scope':'One fixed native shader/pass profile; raw driver packets copied on CPU. Full render state, API ICB and transparent integration remain unqualified.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable)
    (root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
