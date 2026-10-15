#!/usr/bin/env python3
"""Mixed binding/geometry oracle and byte-exact relocation/control verification."""
from pathlib import Path
import argparse,hashlib,json,struct
from decode_native_commands import decode
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve();result=json.loads((root/'results.json').read_text());process=json.loads((root/'execution/manifest.json').read_text());originalRoot=Path(process['original_executable']).parent
def local(path):return root/Path(path).relative_to(originalRoot)
def sha(d):return hashlib.sha256(d).hexdigest()
def u32(d,o):return struct.unpack_from('<I',d,o)[0]
def u64(d,o):return struct.unpack_from('<Q',d,o)[0]
def guards(d):assert d[:64]==d[-64:]==b'\xa5'*64
def output(raw,count,seed,groups,local_size,repeats,disabled=False):
 guards(raw);guards(count);assert len(raw)==10368 and len(count)==132;n=groups*local_size;assert u32(count,64)==(0 if disabled else repeats*n)
 if disabled:assert raw==b'\xa5'*len(raw);return 0
 expected=[]
 for i in range(n):expected.extend([((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,groups|0x01010000,local_size])
 assert list(struct.unpack_from('<'+str(n*4)+'I',raw,64))==expected and raw[64+n*16:-64]==b'\xa5'*(640-n)*16;return n*4
assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'];assert result['passed'] and result['registry_id']==4294968458 and result['wrong_queue_rejected_before_submission'] and not result['ICB_implemented'] and not result['system_modifications']
records=result['records'];assert len(records)==3 and [(r['groups'],r['local']) for r in records]==[(1,32),(3,33),(5,128)]
for key in ['dedicated_CB_GPU_address','dedicated_QMD_GPU_address','parameters_GPU_address','output_GPU_address','counter_GPU_address']:assert len({r['relocation'][key] for r in records})==3
parts=[];snapshots=[];qmd_offsets=[];words=0;source_references=0
for record in records:
 base=local(record['base']);info=record['relocation'];original=Path(str(base)+'.commands.bin').read_bytes();relocated=Path(str(base)+'.relocated.bin').read_bytes();assert sha(original)==info['original_SHA256'] and sha(relocated)==info['relocated_SHA256'] and len(original)==len(relocated)==464
 packets=decode(original);assert len(packets)==len(decode(relocated))==9;expected=bytearray(original);qmd=packets[5]['offset']+4;geometry=packets[2]['offset']+4
 for offset,value in [(12,(info['dedicated_CB_GPU_address']+0x6f0)>>32),(16,(info['dedicated_CB_GPU_address']+0x6f0)&0xffffffff),(168,info['dedicated_QMD_GPU_address']>>32),(172,info['dedicated_QMD_GPU_address']&0xffffffff),(qmd+0x7c,info['dedicated_CB_GPU_address']&0xffffffff),(qmd+0x80,(u32(original,qmd+0x80)&0xffffff00)|(info['dedicated_CB_GPU_address']>>32)),(444,info['dedicated_QMD_GPU_address']>>8)]:struct.pack_into('<I',expected,offset,value)
 assert expected==relocated
 cb=Path(str(base)+'.constants.bin').read_bytes();desc=Path(str(base)+'.descriptor.bin').read_bytes();guards(cb);guards(desc);cb=cb[64:-64];desc=desc[64:-64];assert len(cb)==65536 and desc[:256]==original[qmd:qmd+256] and cb[0x6f0:0x770]==original[geometry:geometry+128]
 assert u64(cb,8)==info['output_GPU_address']+64 and u64(cb,40)==info['counter_GPU_address']+64 and u64(cb,72)==info['parameters_GPU_address']
 assert record['seed']==0x1234+101*record['index'];words+=output(Path(str(base)+'.output.bin').read_bytes(),Path(str(base)+'.counter.bin').read_bytes(),record['seed'],record['groups'],record['local'],1);source_references+=record['groups']*record['local'];parts.append(relocated);snapshots.append(cb);qmd_offsets.append(qmd)
invocations=positive_elements=negative_elements=0;checked=[]
for run in result['runs']:
 variant=run['variant'];suppressed={1} if variant==2 else {0,1,2} if variant==3 else set();repeats=4 if variant==1 else 1;evidence=run['evidence'];assert run['repetitions']==repeats
 sequence=b''
 for index,part in enumerate(parts):
  chunk=bytearray(part)
  if index in suppressed:struct.pack_into('<II',chunk,448,(u32(chunk,448)&~0x1fff)|(0x100//4),0)
  sequence+=chunk
 stream=Path(str(local(run['base']))+'.commands.bin').read_bytes();assert stream==sequence*repeats and len(stream)==evidence['command_bytes']==3*repeats*464 and sha(stream)==evidence['stream_SHA256']
 assert evidence['native_preparation_API_calls']==1 and evidence['native_preparation_GPU_dispatches']==0 and evidence['sequence_elements']==3 and evidence['sequence_repetitions']==repeats and evidence['raw_packet_copies']==3*repeats
 if not run['GPU_replay']:assert not run['committed'] and result['mode']=='prepare';continue
 assert run['command_status']==4 and result['mode']=='execute';outputs=run['outputs'];assert len(outputs)==3
 for o in outputs:
  index=o['index'];r=records[index];disabled=index in suppressed;assert o['launch_suppressed']==disabled and o['mismatches']==o['guard_mismatches']==0;seed=0x1234+101*index+37*run['iteration'];assert seed==o['seed'];base=local(o['base']);raw=Path(str(base)+'.output.bin').read_bytes();count=Path(str(base)+'.counter.bin').read_bytes();words+=output(raw,count,seed,r['groups'],r['local'],repeats,disabled)
  assert o['actual_invocations']==o['expected_invocations']==u32(count,64);cb=Path(str(base)+'.constants.bin').read_bytes();desc=Path(str(base)+'.descriptor.bin').read_bytes();guards(cb);guards(desc);qmd=qmd_offsets[index];assert cb[64:-64]==snapshots[index] and desc[64:320]==parts[index][qmd:qmd+256]
  if disabled:negative_elements+=1
  else:positive_elements+=1;invocations+=repeats*r['groups']*r['local']
 checked.append({'iteration':run['iteration'],'variant':variant,'repetitions':repeats,'suppressed_elements':sorted(suppressed),'stream_SHA256':sha(stream)})
inputs=json.loads((root/'inputs.json').read_text())
for file,h in inputs['source_hashes'].items():assert sha((root/file).read_bytes())==h
assert sha((root/'indirect_compute_probe.metallib').read_bytes())==inputs['library_SHA256']=='b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d'
summary={'status':'PASS','mode':result['mode'],'independent_records':3,'source_native_reference_invocations':source_references,'submitted_mixed_sequences':len(checked),'positive_element_results':positive_elements,'suppressed_element_results':negative_elements,'replayed_consumer_invocations':invocations,'correct_uint32_words_including_reference':words,'native_preparation_calls_per_sequence':1,'native_preparation_GPU_invocations':0,'CB_snapshot_bytes_preserved_per_element':65536,'wrong_queue_rejected':True,'guard_mismatches':0,'ICB_implemented':False,'integration_level':1,'system_modifications':False,'performance_benchmark':False,'scope':'One pinned native pipeline, independent bindings/geometries/backings, a single native preparation for the full mixed packet sequence. Partial and full launch suppression controls preserve unaffected elements. No arbitrary Metal ICB/runtime/render/other-shader claim.','sequences':checked}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='sequences'},indent=2))
