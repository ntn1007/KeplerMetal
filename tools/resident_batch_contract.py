#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU audit of the bounded optional resident-batch SDK cohort."""
from pathlib import Path
import argparse,hashlib,json,struct

ROOT=Path(__file__).resolve().parents[1]
POISON=0xa53c6f09
SPECS={
 'only-a':([0],[]),'only-b':([1],[]),'pair-serial-ab':([0,1],[1]),'pair-serial-ba':([1,0],[1]),
 'serial-ab':([0,1,2,3],[1,2,3]),'serial-ba':([3,2,1,0],[1,2,3]),
 'pair-parallel-ab':([0,1],[]),'pair-parallel-ba':([1,0],[]),
 'segmented-ab':([0,1,2,3],[2]),'segmented-ba':([3,2,1,0],[2]),
 'source-barrier-ab':([0,1,2,3],[2]),'source-barrier-ba':([3,2,1,0],[2]),
 'parallel-ab':([0,1,2,3],[]),'parallel-ba':([3,2,1,0],[])}

def require(ok,text):
    if not ok:raise ValueError(text)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def u64(b,o):return struct.unpack_from('<Q',b,o)[0]
def pack(a):return struct.pack('<'+'I'*len(a),*a)
def oracle(nonce,role):
    x=nonce^[0x9e3779b9,0x85ebca6b][role]
    for i in range(128):x=((((x<<7)&0xffffffff)|(x>>25))*1664525+1013904223+i)&0xffffffff
    return x
def overlap(a,b):return a['begin']<b['end'] and b['begin']<a['end']
def check_plan(plan,indices,barriers):
    require(plan['record_indices']==indices and plan['barrier_before_positions']==barriers,'immutable selected records and requested boundaries')
    require(all(0<b<len(indices) for b in barriers) and barriers==sorted(set(barriers)),'bounded ordered boundaries')
    rows=plan['footprints'];require(len(rows)==len(indices),'complete profile footprints')
    for r in rows:
        require(len(r['ranges'])==3,'three typed footprints')
        for i,(access,n) in enumerate([('atomic',12),('write',32),('read',16)]):
            a=r['ranges'][i];require(a['binding']==i and a['access']==access and a['end']-a['begin']==n and 0<a['begin']<a['end']<1<<40,'exact pinned kernel footprint')
        require(not any(overlap(a,b) for i,a in enumerate(r['ranges']) for b in r['ranges'][i+1:]),'no self alias')
    for i,a in enumerate(rows):
        for j,b in enumerate(rows[i+1:],i+1):
            if any(i<k<=j for k in barriers):continue
            require(a['descriptor']!=b['descriptor'],'distinct resident descriptor inside a concurrent segment')
            for x in a['ranges']:
                for y in b['ranges']:
                    if overlap(x,y):require(x['access']==y['access']=='read' or x['access']==y['access']=='atomic' and x['begin']==y['begin'] and x['end']==y['end'],'no unsynchronized non-atomic or partial-atomic alias')

def witness(row,indices,barriers,nonce):
    s,o=row['sync_words'],row['output_words'];require(len(s)==256 and len(o)==512,'complete raw output witnesses')
    require(len(indices)==len(set(indices)),'this oracle covers distinct observed outputs')
    active=set(indices);count=len(indices);require(s[64:67]==[2*count,int(bool(active&{0,2})),int(bool(active&{1,3}))],'exact sequence count/start flags')
    require(all(v==POISON for v in s[:64]+s[67:]),'all sync guards')
    tags=[];written=set();expected_rows=[]
    for i in sorted(indices):
        start=64*(i+1);v=o[start:start+8];written.update(range(start,start+8));tags.extend(v[:2])
        require(1<=v[0]<v[1]<=2*count and v[2] in [0,1] and 1<=v[3]<=4096 and (v[2] or v[3]==4096),'valid bounded ordering and peer polling')
        if not any(j%2!=i%2 for j in active):require(v[2]==0,'missing peer control')
        n=(nonce+37*i)&0xffffffff;require(v[4:]==[oracle(n,i%2),n,i%2,128],'independent uint32 oracle and invocation marker')
        expected_rows.append(dict(index=i,begin=v[0],end=v[1],seen=v[2],iterations=v[3],arithmetic=v[4]))
    require(sorted(tags)==list(range(1,2*count+1)) and row['results']==expected_rows,'all atomic tags unique and native summary exact')
    require(all(v==POISON for i,v in enumerate(o) if i not in written),'all omitted output and guard words')
    interleaved=crossed=0
    for i,a in enumerate(indices):
        for j,b in enumerate(indices[i+1:],i+1):
            x,y=o[64*(a+1):64*(a+1)+2],o[64*(b+1):64*(b+1)+2]
            interleaved+=x[0]<y[1] and y[0]<x[1]
            if any(i<k<=j for k in barriers):require(x[1]<y[0],'prior atomic end tags precede every post-boundary begin')
            crossed+=i<2<=j and x[1]>=y[0]
    require(row['arithmetic_mismatches']==row['guard_mismatches']==0 and row['active_dispatches']==count and row['interleaved_pairs']==interleaved and row['crossed_midpoint_pairs']==crossed,'raw/native summary agreement')
    return dict(dispatches=count,arithmetic_results=count,raw_words=768,guard_words=765-8*count,interleaved_pairs=interleaved,crossed_midpoint_pairs=crossed)

def audit(build,run):
    inputs=load(build/'inputs.json')
    for n,h in inputs['files_SHA256'].items():require(sha(build/n)==h,'frozen build '+n)
    require(load(run/'inputs.json')==inputs,'run uses exact build')
    d=load(run/'results.json');m=load(run/'execution/manifest.json')
    require(d==load(run/'execution/execution.stdout') and d['pid']==m['pid'],'complete native process result')
    require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'normal terminal process')
    require(m['original_binary_sha256']==inputs['files_SHA256']['application'] and sha(run/'execution/application')==m['signed_binary_sha256'],'signed immutable process identities')
    lease=m['GPU_reservation'];require(lease['state']=='terminal' and lease['lock_inherited_by_child'] and lease['bootstrap_process_table_checked'] and not lease['known_signed_processes_live'],'same inherited cooperative host lease')
    require(d['status']=='PASS' and d['uid']==d['euid']>0 and d['device']=='NVIDIA GeForce GTX 880M' and d['scope_restored'] and d['source_slots_reset_before_execution'],'unprivileged correct GPU and reset-source lifetime')
    require(not any(d[k] for k in ['system_modified','common_runtime_modified','native_shader_changed','performance_benchmark']),'experiment boundaries')
    require(d['library_SHA256']==inputs['files_SHA256']['probe.metallib'] and d['manifest_SHA256']==inputs['files_SHA256']['manifest.json'],'native registered program inputs')
    rejections=['empty','out-of-range','first-barrier','past-barrier','duplicate-in-segment','output-alias','partial-atomic-alias','self-alias','resident-state-alias','output-config-alias','unbounded-config','foreign-queue','restored-scope']
    require([r['label'] for r in d['rejections']]==rejections and all(r['reason'] and r['user_dispatches']==0 for r in d['rejections']),'all actual refusal controls retained')
    state_ranges=[];backing=d['resident_backing'];require(len(backing)==4,'four actual resident records')
    for i,r in enumerate(backing):
        prefix=run/'captures'/('record-'+str(i));data={n:Path(str(prefix)+'.'+n+'.bin').read_bytes() for n in ['QMD','constants','original','relocated']}
        require([len(data[n]) for n in data]==[256,65536,464,464],'full GPU state/record readbacks')
        for n,v in data.items():require(hashlib.sha256(v).hexdigest()==r[n+'_SHA256'],'GPU state hash')
        q,c,original,relocated=[data[n] for n in data]
        e=r['relocation'];descriptor=e['dedicated_QMD_GPU_address'];constants=e['dedicated_CB_GPU_address']
        require(q==relocated[184:440] and relocated[440:464]==pack([0x200120ad,descriptor>>8,0x200120af,3,0x20012044,0]),'exact native relocated QMD/tail')
        require(all(original[o:o+4]==relocated[o:o+4] for o in range(0,464,4) if o not in [12,16,168,172,308,312,444]),'only state-address relocation')
        materialized=[x for x in d['scope_events'] if x['operation']=='materialize_CPU_command' and x['relocation']['dedicated_QMD_GPU_address']==descriptor]
        require(len(materialized)==1 and materialized[0]['snapshot_SHA256']==r['constants_SHA256'],'GPU constants equal native source snapshot')
        require(u32(q,0xb8)>>24==e['native_register_count']==17 and u32(q,0x50)&255==e['constant_buffer_valid_mask']==7,'native register and bank metadata')
        require(((u32(q,0x80)&255)<<32|u32(q,0x7c))==constants and u32(q,0x80)>>15==65536,'actual dedicated constant-bank QMD')
        literal=e['native_literal_bank_0'];require(literal['variant_owner_retained'] and literal['bytes']==256 and literal['native_code_bytes']==2304 and ((u32(q,0x78)&255)<<32|u32(q,0x74))==literal['GPU_address']==literal['native_code_GPU_address']+2304,'unchanged retained native code/literal-bank metadata')
        for b in e['bindings']:require(u64(c,b['index']*32+8)==b['GPU_address']+b['offset']==b['native_table_address'],'actual GPU binding table')
        state_ranges.extend([(descriptor,descriptor+4096),(constants,constants+65536)])
    require(all(b<=c or d<=a for i,(a,b) in enumerate(state_ranges) for c,d in state_ranges[i+1:]),'all eight resident allocations disjoint')
    for name,(indices,barriers) in SPECS.items():
        plan=d['plans'][name];check_plan(plan,indices,barriers)
        require(plan['source_slot_barrier_positions']==([2] if name.startswith('source-barrier') else []),'source setBarrier snapshot')
        for pos,i in enumerate(indices):
            p=plan['footprints'][pos];e=backing[i]['relocation'];require(p['descriptor']==e['dedicated_QMD_GPU_address'] and p['constants']==e['dedicated_CB_GPU_address'] and p['function']==e['function'],'actual retained record identity')
            for j,b in enumerate(e['bindings']):require(p['ranges'][j]['begin']==b['native_table_address'],'actual native binding footprint')
    require(witness(d['preparation_untouched_witness'],[],[],710003)['dispatches']==0,'preparation and negative controls left witnesses intact')
    mode=d['mode'];n=int(m['arguments'][-1]);require(1<=n<=4,'bounded trial request')
    names=['none','only-a','only-b','pair-serial-ab','pair-serial-ba','serial-ab','serial-ba']
    if mode in ['segmented','parallel']:names+=['pair-parallel-ab','pair-parallel-ba','segmented-ab','segmented-ba','source-barrier-ab','source-barrier-ba']
    if mode=='parallel':names+=['parallel-ab','parallel-ba']
    protocol=[]
    if mode!='prepare':
        for i,name in enumerate(names):
            repeats=n if mode=='serial' or mode=='segmented' and i>=7 or mode=='parallel' and i>=13 else 1
            protocol.extend((name,j) for j in range(repeats))
    require([(r['kind'],r['trial']) for r in d['runs']]==protocol,'complete ordered control/experiment protocol')
    totals=dict(dispatches=0,arithmetic_results=0,raw_words=0,guard_words=0,interleaved_pairs=0,crossed_midpoint_pairs=0,parameter_bytes=0)
    per_kind={}
    for i,row in enumerate(d['runs']):
        name=row['kind'];indices,barriers=SPECS.get(name,([],[]));nonce=(710011+104729*i)&0xffffffff
        require(row['nonce']==nonce and row['command_status']==4,'fresh nonce and completed buffer')
        result=witness(row,indices,barriers,nonce)
        if indices:
            e=row['encoding'];require(e['plan']==d['plans'][name] and e['carrier_encoder_ended'] and e['terminal_wait_retained'] and e['native_encoder_dispatch_type']==0 and not e['system_modified'] and not e['ordinary_concurrent_API'],'SDK-owned native encoder/stream scope')
            original=[]
            for j in indices:original.extend([0x200120ad,backing[j]['relocation']['dedicated_QMD_GPU_address']>>8,0x200120af,3,0x20012044,0])
            expected=original.copy();offsets=[24*j+16 for j in range(len(indices)-1) if j+1 not in barriers]
            for offset in offsets:expected[offset//4]=0x20012040
            require(e['original_stream_words']==original and e['candidate_stream_words']==expected and e['changed_word_offsets']==offsets,'only explicit barrier-free waits changed; final wait retained')
            require(hashlib.sha256(pack(original)).hexdigest()==e['original_stream_SHA256']==e['transport']['stream_SHA256'] and hashlib.sha256(pack(expected)).hexdigest()==e['candidate_stream_SHA256'],'original/candidate actual readback digests')
            require(e['transport']['native_preparation_GPU_dispatches']==e['transport']['CPU_QMD_uploads_in_launch']==e['transport']['CPU_constant_uploads_in_launch']==0,'resident launch has no CPU state upload')
        else:require(row['encoding']=={},'empty-dispatch control')
        for j in range(4):
            raw=(run/'captures'/('trial-'+str(i)+'.params-'+str(j)+'.bin')).read_bytes();expected=bytearray(b'\xa5'*1024);struct.pack_into('<4I',expected,256,4096,(nonce+37*j)&0xffffffff,128,0)
            require(raw==expected,'all parameter bytes and padding')
        for k,v in result.items():totals[k]+=v
        totals['parameter_bytes']+=4096;per_kind.setdefault(name,dict(trials=0,interleaved_pairs=0,crossed_midpoint_pairs=0));per_kind[name]['trials']+=1
        for k in ['interleaved_pairs','crossed_midpoint_pairs']:per_kind[name][k]+=result[k]
    require(totals['dispatches']==d['user_compute_dispatches'],'all counted GPU invocations')
    labels=['after'] if mode in ['prepare','serial'] else ['before-'+n for n in names[7:]]+['after']
    require([(r['label'],r['index']) for r in d['resident_state_rechecks']]==[(label,i) for label in labels for i in range(4)],'all planned GPU state rechecks')
    for r in d['resident_state_rechecks']:
        for name in ['QMD','constants']:
            file=run/'captures'/(r['label']+'-'+str(r['index'])+'.'+name+'.bin')
            require(sha(file)==r[name+'_SHA256']==backing[r['index']][name+'_SHA256'],'GPU state stable before experimental classes and after all kernels')
    return dict(status='PASS',mode=mode,trials=len(d['runs']),totals=totals,per_kind=per_kind,input_manifest_SHA256=sha(build/'inputs.json'),execution_manifest_SHA256=sha(run/'execution/manifest.json'),results_SHA256=sha(run/'results.json'),auditor_SHA256=sha(__file__),scope='Pinned four-record explicit SDK batch, not ordinary Metal concurrency or general data-visibility conformance',performance_benchmark=False,global_objective_complete=False)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.relative_to(ROOT/'results');require(not out.exists(),'fresh independent audit output required')
    r=audit(a.build.resolve(),a.run.resolve());out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ['status','mode','trials','totals','per_kind']}))
if __name__=='__main__':main()
