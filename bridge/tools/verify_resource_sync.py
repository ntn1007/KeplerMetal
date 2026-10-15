#!/usr/bin/env python3
"""CPU oracle, byte guards, GPU completion and explicit stage classification."""
from pathlib import Path
import argparse, hashlib, json, struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve()
records=json.loads((root/'results.json').read_text());checked=[];words=0;capture_count=0;guard_count=0;negative_errors=0
for case in records:
    kind=case['kind'];r=case['result'];process=case['process']
    assert not process['authoritative_ps_status'] and not process['SIGKILL_requested']
    if not r.get('GPU_dispatch'):
        assert r.get('failure_stage') and not r.get('passed')
        checked.append({'kind':kind,'status':'BLOCKED','stage':r['failure_stage'],'GPU_dispatch':False,'factory_created':r.get('factory_created',False)})
        continue
    runs=[]
    for run in r['runs']:
        data=Path(run['output_file']).read_bytes();n=run['elements'];seed=0x1234+37*run['iteration'];assert seed==run['seed']
        render=kind=='icb_render';expected=bytearray([0xa5]*(16*256+128 if render else n*4+128));bad=0
        for i in range(n):
            value=((((i*1664525)&0xffffffff)^seed)+((i*1013904223)&0xffffffff))&0xffffffff
            value^=(seed*747796405)&0xffffffff
            if render:value=(255 if seed&1 else 0)|(0xff00 if seed&2 else 0)|(0xff0000 if seed&4 else 0)|0xff000000
            offset=64+((i//16)*256+(i%16)*4 if render else i*4)
            struct.pack_into('<I',expected,offset,value)
            bad+=struct.unpack_from('<I',data,offset)[0]!=value
        assert len(data)==len(expected)
        guard_positions=list(range(64))+list(range(len(data)-64,len(data)))
        if render:guard_positions += [64+row*256+pad for row in range(16) for pad in range(64,256)]
        guards=sum(data[x]!=0xa5 for x in guard_positions);assert not guards and guards==run['guard_mismatches']
        assert all(run[x]['status']==4 and not run[x]['timed_out'] for x in ['producer','consumer','readback'])
        assert bad==run['mismatches']
        if kind=='control_missing_producer':assert bad==n;negative_errors+=bad
        else:assert not bad and data==bytes(expected)
        if kind=='shared_event':assert run['GPU_signaled_value']>=run['iteration']+1
        words+=n;capture_count+=1;guard_count+=len(guard_positions)
        runs.append({'iteration':run['iteration'],'elements':n,'bad_words':bad,'guards_checked':len(guard_positions),
                     'output_sha256':hashlib.sha256(data).hexdigest()})
    if kind=='control_missing_producer':status='NEGATIVE_CONTROL_PASS';assert not r['passed'] and r['negative_control_detected']
    else:status='PASS';assert r['passed']
    if kind=='heap_alias':
        assert r['alias_capacity_control_nil'] and r['alias_old_object_retained'] and r['alias_reallocation_created']
        assert r['resources_owned_by_heap']
    checked.append({'kind':kind,'status':status,'GPU_dispatch':True,'runs':runs})
manifest=json.loads((root/'manifest.json').read_text());assert manifest['system_before']==manifest['system_after']
for name,h in manifest['source_hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
summary={'cases':len(checked),'functional_cases':sum(c['status']=='PASS' for c in checked),'blocked_cases':sum(c['status']=='BLOCKED' for c in checked),
         'negative_controls_detected':sum(c['status']=='NEGATIVE_CONTROL_PASS' for c in checked),'captures':capture_count,
         'uint32_words_checked':words,'guard_bytes_checked':guard_count,'negative_control_bad_words':negative_errors,
         'system_files_unchanged':True,'results':checked,
         'limits':'Bounded samples; alias reuse only where separately recorded, no sustained lifetime stress, full API conformance, benchmark, new feature family or system implementation.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
