#!/usr/bin/env python3
"""Independent raw-byte CPU oracle, including unordered atomic return values."""
from pathlib import Path
import argparse,hashlib,json,struct
ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--relocate-from',type=Path);ap.add_argument('--relocate-to',type=Path);args=ap.parse_args();assert bool(args.relocate_from)==bool(args.relocate_to);ROOT=args.input.resolve();records=json.loads((ROOT/'results.json').read_text());rows=[]
for record in records:
    d=record.get('result',{});c=d.get('case',record);kind=c['kind'];op=c.get('op','');local=c['local'];groups=c['groups'];width=d.get('thread_execution_width',32);N=c.get('resources',0)
    for run in d.get('runs',[]):
        path=Path(run['output_file'])
        if args.relocate_from:path=args.relocate_to/path.relative_to(args.relocate_from)
        raw=path.read_bytes();values=list(struct.iter_unpack('<4I',raw[64:-64]));assert len(values)==local*groups
        seed=run['seed'];iteration=run['iteration'];mismatches=[]
        def binding(i):return i if iteration==0 else (i+3)%N if iteration==1 else N-1-i
        for i,v in enumerate(values):
            tid=i%local;g=i//local;lane=tid%width;base=tid//width*width;active=min(width,local-base);expected=[0,0,0,i]
            if kind.startswith('argument'):
                gpu=kind.startswith('argument_gpu');requested=(i*13+seed)%N;encoded=(requested+seed%N)%N if gpu else requested
                expected[0]=(binding(encoded)+1)*65536+((i*7+seed)&63)*17
                if kind in ['argument_mixed','argument_gpu_mixed']:
                    t=(i*5+seed)%N;slot=binding((t+seed%N)%N if gpu else t);x=(i*3+seed)%16;y=(i*5+seed)%16;s=(i+seed)&1;x=x%8 if s else min(x,7);y=y%8 if s else min(y,7);expected[1]=(slot+1)*1024+y*8+x
                else:expected[1]=requested
                expected[2]=seed
            elif kind=='simd':
                def value(t):return ((g*local+t)*17)%97+(seed%97)+1
                data=[value(t) for t in range(base,base+active)]
                if op in ['sum','sum_float']:answer=sum(data)
                elif op=='sum_divergent':answer=sum(value(t) for t in range(base,base+active) if t&1) if tid&1 else 0xdead0000
                elif op=='min':answer=min(data)
                elif op=='max':answer=max(data)
                elif op=='prefix':answer=sum(value(t) for t in range(base,tid))
                elif op=='shuffle':answer=value(base)
                elif op=='xor':answer=value(base+(lane^1))
                elif op=='ballot':answer=sum(1<<t for t in range(active) if (base+t)&1)
                elif op=='all':answer=int(all(t>50 for t in data))
                elif op=='any':answer=int(any(t>50 for t in data))
                elif op=='control':answer=value(tid)
                expected=[answer,lane,width,i]
            elif kind=='cas':
                initial=seed+g*0x10001;replacement=seed^0x55667788;contended=c['contended'];miss=c['variant']!=0
                if op=='weak':
                    if v[1] not in [0,1]:mismatches.append([i,'invalid success flag'])
                    succeeded=bool(v[1]);expected=[initial if miss or not contended or succeeded else replacement,0 if miss else 1 if not contended else v[1],initial if miss else replacement,i]
                elif op=='load_store':expected=[initial,int(not miss),initial if miss else replacement,i]
                else:expected=[v[0] if contended else initial,1,initial+(local if contended else 1),i]
            if tuple(expected)!=v:mismatches.append([i,list(v),expected])
        if kind=='cas' and c['contended']:
            for g in range(groups):
                block=values[g*local:(g+1)*local];initial=seed+g*0x10001
                if op=='add' and sorted(v[0] for v in block)!=list(range(initial,initial+local)):mismatches.append([g,'atomic ADD multiset mismatch'])
                if op=='weak' and sum(v[1] for v in block)!=(0 if c['variant'] else 1):mismatches.append([g,'CAS success-count mismatch'])
        guard_errors=sum(v!=0xa5 for v in raw[:64]+raw[-64:]);rows.append({'label':record['label'],'iteration':iteration,'words_checked':len(values)*4,'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_file':str(path),'mismatches':len(mismatches),'examples':mismatches[:5],'guard_mismatches':guard_errors,'host_reported_mismatches':run['mismatches']})
summary={'raw_runs_checked':len(rows),'words_checked':sum(r['words_checked'] for r in rows),'numeric_mismatches':sum(r['mismatches'] for r in rows),'guard_mismatches':sum(r['guard_mismatches'] for r in rows),'records':rows,'note':'Raw captures only. Pipeline/command failures cannot count as GPU passes. CPU oracle does not execute on a GPU.'}
(ROOT/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
assert summary['numeric_mismatches']==0 and summary['guard_mismatches']==0
