#!/usr/bin/env python3
"""Verify GPU work from raw bytes, then calculate balanced paired statistics."""
from pathlib import Path
import argparse,hashlib,json,statistics,struct

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stats(values):
    q=statistics.quantiles(values,n=4,method='inclusive')
    return {'n':len(values),'median':statistics.median(values),'q1':q[0],'q3':q[2],'min':min(values),'max':max(values)}
def verify(root,portable=False):
    root=Path(root);read=lambda n:json.loads((root/n).read_text());d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
    assert d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==4294968458 and d['scope_restored']
    assert d['performance_benchmark'] and d['cold_preparation_excluded'] and d['output_transfers_excluded'] and d['work_identical_between_modes']
    assert not any(d[k]for k in ['gated_waits','system_modified','new_driver_installed','CPU_expected_answers_uploaded','intermediate_descriptor_CPU_readback','full_ICB_contract'])
    assert d['source_function']=='profile_integer' and d['source_local']==32 and d['source_groups']==3 and d['source_seed']==0x3311
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
    for n,h in inp['source_SHA256'].items():assert sha(root/n)==h
    assert sha(root/'library.metallib')==inp['library_SHA256']=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'
    assert inp['static_library_SHA256']=='9d518d1cff252ff60f0e8bd50117f41405265884483dae015aef9c0e059ef754' and inp['core_source_compilations']==0
    if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
    modes=['wait_each','submit_all','single_CB'];runs=d['runs'];assert len(runs)==36
    hashes={};guard=words=invocations=0;measured={x:{}for x in modes};pending=0
    for index,r in enumerate(runs):
        cycle,order=index//3,index%3;mode=modes[(cycle+order)%3]
        assert r['cycle']==cycle and r['order']==order and r['mode']==mode and r['warmup']==(cycle<3) and r['iterations']==32
        assert r['command_buffers']==r['submissions']==(1 if mode=='single_CB'else 96)
        assert r['explicit_completion_waits']==(96 if mode=='wait_each'else 1)
        assert r['blit_encoders']==r['QMD_copies']==64 and r['compute_encoders']==r['user_dispatches']==32
        assert r['command_buffer_final_states']==[4]*r['command_buffers']
        assert all(isinstance(r[k],int)and r[k]>0 for k in ['wall_ns','process_CPU_ns','thread_CPU_ns'])
        assert r['GPU_span_ms'] is None or r['GPU_span_ms']>0
        assert len(r['events'])==96 and len(r['files'])==6
        for step in range(32):
            c1,c2,e=r['events'][step*3:step*3+3]
            for j,c in enumerate([c1,c2]):
                assert c['operation']=='GPU_QMD_copy' and c['source_location']==j and c['destination_index']==j+1 and c['length']==1 and c['bytes']==256 and c['encoded_GPU_blits']==1 and not c['CPU_shadow_is_execution_source']
                pair=c['descriptor_pairs'][0];assert pair['source']!=pair['destination'] and pair['owners']==j+2 and pair['copied_function']=='profile_integer' and pair['copied_groups']==3 and pair['copied_local']==32
                assert pair['destination_original_function']==['profile_fma','profile_shared'][j]
            assert e['operation']=='executeCommandsInBuffer' and e['executed_indices']==[2] and e['resident_GPU_descriptor']
            p=e['evidence'];assert p['resident_launches']==1 and p['command_bytes']==24 and p['owners']==3 and p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==p['native_preparation_GPU_dispatches']==0
            for event in [c1,c2,e]:
                for proof in event['predecessor_order']:
                    assert proof['consumer_status']==0 and proof['same_queue'] and not proof['CPU_wait_performed']
                    assert proof['producer_status'] in [0,2,3,4]
                    if proof['producer_status'] in [2,3]:pending+=1
        for k in range(3):
            expected=bytearray(b'\xa5'*10368)
            if k==0:
                for i in range(96):struct.pack_into('<4I',expected,64+i*16,((0x3311*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,3|0x01010000,32)
                words+=96*4;invocations+=96*32
            path=root/'outputs'/r['files'][k*2];assert path.read_bytes()==expected,str(path);hashes[path.name]=sha(path);guard+=10368-(1536 if k==0 else 0)
            count=bytearray(b'\xa5'*132);struct.pack_into('<I',count,64,96*32 if k==0 else 0)
            path=root/'outputs'/r['files'][k*2+1];assert path.read_bytes()==count,str(path);hashes[path.name]=sha(path);guard+=128
        if cycle>=3:measured[mode][cycle]=r
    assert all(len(v)==9 for v in measured.values())
    summaries={}
    for mode,bycycle in measured.items():
        summaries[mode]={k:stats([r[k]*1e-6 for r in bycycle.values()])for k in ['wall_ns','process_CPU_ns','thread_CPU_ns']}
        for k in summaries[mode]:summaries[mode][k]['unit']='ms'
        summaries[mode]['GPU_span_ms']=stats([r['GPU_span_ms']for r in bycycle.values()])if all(r['GPU_span_ms']is not None for r in bycycle.values())else None
    comparisons={}
    for a,b in [('wait_each','submit_all'),('submit_all','single_CB'),('wait_each','single_CB')]:
        c={}
        for metric in ['wall_ns','process_CPU_ns','thread_CPU_ns']:
            am=summaries[a][metric]['median'];bm=summaries[b][metric]['median']
            c[metric]={'paired_ratio':stats([measured[a][i][metric]/measured[b][i][metric]for i in range(3,12)]),'ratio_of_medians':am/bm,'reduction_from_medians_percent':100*(1-bm/am)}
        comparisons[a+'_vs_'+b]=c
    return {'status':'PASS','warmup_runs':9,'measured_runs':27,'measured_runs_per_mode':9,'warmup_dispatches':288,'measured_dispatches':864,'all_dispatches':1152,'all_GPU_invocations_counted':invocations,'final_uint32_words_exact':words,'guard_and_untouched_bytes_verified':guard,'raw_files':len(hashes),'pending_predecessor_admissions':pending,'statistics':summaries,'comparisons':comparisons,'integration_level':2,'core_source_compilations':0,'new_driver_installed':False,'whole_hardware_exclusive':False,'performance_scope':d['timed_region'],'general_driver_speedup':False,'raw_SHA256':hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items()if k!='raw_SHA256'},indent=2))
