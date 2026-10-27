#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for raw Apple Silicon nonuniform-threadgroup reference captures."""
import datetime,hashlib,json,math,struct,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def verify(root,check_current=False,cohort='qualified-01'):
    if cohort not in ('qualified-01','qualified-02'):raise ValueError('Unknown frozen cohort')
    root=Path(root).resolve();p=root/cohort;m=read(p/'manifest.json')
    assert m['status']=='PASS' and m['architecture']=='arm64' and m['user_UID']!=0 and not m['system_modified']
    assert sha(root/'reference.mm')==m['source_SHA256']==m['after']['source_SHA256']
    assert sha(root/'reference')==m['binary_SHA256']==m['after']['binary_SHA256'] and sha(root/'runner.py')==m['runner_SHA256']
    subprocess.run(['codesign','--verify','--strict',str(root/'reference')],check=True,capture_output=True,timeout=15)
    if check_current:
        repo=Path(__file__).resolve().parents[1];assert sha(repo/'tools/partial_grid_m1_reference.mm')==m['source_SHA256'] and sha(repo/'tools/partial_grid_m1_runner.py')==m['runner_SHA256']
    records=m['records'];assert [r['mode'] for r in records]==['negative3d','partial1d','partial3d'] and len({r['pid'] for r in records})==3
    assert all(r['exit_code']==0 and not r['kill_requested'] and r['elapsed_monotonic_ns']>0 for r in records)
    assert all(datetime.datetime.fromisoformat(a['completed_at'])<=datetime.datetime.fromisoformat(b['started_at']) for a,b in zip(records,records[1:]))
    checked=0;rows=[]
    for record in records:
        mode=record['mode'];d=p/mode;r=read(d/'result.json');raw=(d/'output.bin').read_bytes()
        assert sha(d/'result.json')==record['result_SHA256'] and sha(d/'output.bin')==record['output_SHA256']
        assert r['mode']==mode and r['pid']==record['pid'] and r['uid']==r['euid']==m['user_UID'] and r['device']=='Apple M1 Max' and r['registry_id'] and r['supports_apple4'] and r['threadgroup_barrier_used']
        grid=(33,1,1) if mode=='partial1d' else (11,7,5);nominal=(32,1,1) if mode=='partial1d' else (4,4,3);n=math.prod(grid);guard=64
        assert r['grid']==list(grid) and r['dispatch_local']==list(nominal) and r['elements']==n and r['guard']==guard and r['output_bytes']==n*128+2*guard and len(raw)==r['output_bytes']
        assert raw[:guard]==raw[-guard:]==b'\xa5'*guard
        if mode=='negative3d':
            assert not r['submitted'] and r['command_status']==0 and r['counter']==0 and raw==b'\xa5'*len(raw)
            rows.append({'mode':mode,'untouched_bytes':len(raw),'counter':0,'output_SHA256':sha(d/'output.bin')});continue
        assert r['submitted'] and r['command_status']==4 and r['counter']==n
        groups=tuple((g+l-1)//l for g,l in zip(grid,nominal));shapes=set();partial=0
        for z in range(grid[2]):
            for y in range(grid[1]):
                for x in range(grid[0]):
                    gid=(x,y,z);index=x+grid[0]*(y+grid[1]*z);group=tuple(g//l for g,l in zip(gid,nominal));lane=tuple(g%l for g,l in zip(gid,nominal));local=tuple(min(l,g-b*l) for g,l,b in zip(grid,nominal,group))
                    linear=lane[0]+local[0]*(lane[1]+local[1]*lane[2]);shapes.add(local);partial+=local!=nominal
                    expected=(*gid,index,*lane,linear,*group,0,*groups,0,*local,0,*nominal,0,*grid,0,math.prod(local),0,0,0)
                    assert struct.unpack_from('<32I',raw,guard+index*128)==expected,(mode,index)
                    checked+=32
        rows.append({'mode':mode,'threads':n,'groups':list(groups),'distinct_actual_group_sizes':[list(x) for x in sorted(shapes)],'threads_in_partial_groups':partial,'output_SHA256':sha(d/'output.bin')})
    return {'verification':'PASS','macOS':m['macOS'],'macOS_build':m['macOS_build'],'SDK':m['SDK'],'architecture':m['architecture'],
            'device':'Apple M1 Max','processes':len(records),'positive_threads':sum(x.get('threads',0) for x in rows),'uint32_values_checked':checked,
            'zero_dispatch_control':True,'threadgroup_barrier_witness':True,'source_SHA256':m['source_SHA256'],'binary_SHA256':m['binary_SHA256'],
            'runner_SHA256':m['runner_SHA256'],'manifest_SHA256':sha(p/'manifest.json'),'reference_only_not_Kepler_execution':True,'rows':rows}
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--check-current',action='store_true');p.add_argument('--cohort',choices=['qualified-01','qualified-02'],default='qualified-01');a=p.parse_args();print(json.dumps(verify(a.root,a.check_current,a.cohort),indent=2,sort_keys=True))
