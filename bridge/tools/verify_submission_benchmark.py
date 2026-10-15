#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,statistics,struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve()
result=json.loads((root/'results.json').read_text());records=result['records'];mode_count=result.get('mode_count',2);assert mode_count in [2,3] and len(records)==12*mode_count
modes=['wait_each','submit32_wait_end','batch32'] if mode_count==3 else ['wait_each','batch32']
for r in records:
 data=Path(r['output_file']).read_bytes();n=r['elements'];seed=0x1234+r['pair']*37+31*101;assert seed==r['final_seed']
 assert len(data)==n*4+128 and data[:64]==data[-64:]==bytes([0xa5])*64
 expected=[(((((i*1664525)&0xffffffff)^seed)+((i*1013904223)&0xffffffff))&0xffffffff)^((seed*747796405)&0xffffffff) for i in range(n)]
 assert list(struct.unpack_from('<'+str(n)+'I',data,64))==expected
 assert not r['mismatches'] and not r['guard_mismatches'] and r['steps']==32 and r['dispatches']==64
 assert r['command_buffers']==(1 if r['mode']=='batch32' else 32)
 if 'wait_calls' in r:assert r['wait_calls']==(32 if r['mode']=='wait_each' else 1) and r['all_command_buffers_completed']
 assert r['warmup']==(r['pair']<3)
 counter=Path(r['counter_file']).read_bytes();audit=Path(r['audit_file']).read_bytes()
 assert len(counter)==132 and len(audit)==384 and counter[:64]==counter[-64:]==audit[:64]==audit[-64:]==bytes([0xa5])*64
 assert struct.unpack_from('<I',counter,64)[0]==r['GPU_dispatch_count']==64
 audit_words=struct.unpack_from('<64I',audit,64)
 for k in range(32):
  s=0x1234+r['pair']*37+k*101
  assert audit_words[2*k]==s and audit_words[2*k+1]==(s^((s*747796405)&0xffffffff))
for pair in range(12):
 rows=[r for r in records if r['pair']==pair];assert {r['mode'] for r in rows}==set(modes)
 assert all(Path(rows[0]['output_file']).read_bytes()==Path(r['output_file']).read_bytes() for r in rows[1:])
 assert rows[0]['mode']==(modes[pair%3] if mode_count==3 else 'batch32' if pair&1 else 'wait_each')
fields=['total_wall_ms','thread_cpu_ms','process_cpu_ms','encoding_wall_ms','encoding_thread_cpu_ms','submit_wall_ms','submit_thread_cpu_ms','wait_wall_ms','wait_thread_cpu_ms','upload_wall_ms','readback_wall_ms']
stats={}
for mode in modes:
 rows=[r for r in records if r['mode']==mode and not r['warmup']];assert len(rows)==9
 stats[mode]={}
 for field in fields:
  values=[r[field] for r in rows];q=statistics.quantiles(values,n=4,method='inclusive')
  stats[mode][field]={'median':statistics.median(values),'Q1':q[0],'Q3':q[2],'IQR':q[2]-q[0]}
ratios={}
for field in ['total_wall_ms','thread_cpu_ms','process_cpu_ms']:
 values=[]
 for pair in range(3,12):
  rows={r['mode']:r for r in records if r['pair']==pair};values.append(rows['wait_each'][field]/rows['batch32'][field])
 ratios[field]={'paired_median':statistics.median(values),'min':min(values),'max':max(values)}
manifest=json.loads((root/'manifest.json').read_text());assert manifest['system_before']==manifest['system_after']
for name,h in manifest['source_hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
summary={'warmup_pairs':3,'measured_pairs':9,'mode_count':mode_count,'raw_captures_verified':len(records)*3,'uint32_words_verified':len(records)*(32768+65),'guards_verified':len(records)*3*128,
 'GPU_dispatches_counted':len(records)*64,'GPU_dispatches_warmups':3*mode_count*64,'GPU_dispatches_measured':9*mode_count*64,'GPU_step_audits_verified':len(records)*32,
 'stats_ms':stats,'wait_each_over_batch32':ratios,'GPU_exclusive_time':False,'driver_modernization_demonstrated':False,
 'scope':'Identical native GPU arithmetic; observed application command-buffer batching benefit only. No inference throughput, global speedup, or driver optimization claim.'}
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
