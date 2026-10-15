#!/usr/bin/env python3
"""Independent native packet relocation/reuse oracle from raw snapshots."""
from pathlib import Path
import argparse,hashlib,json,struct
from decode_native_commands import decode
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve();result=json.loads((root/'results.json').read_text());info=result['relocation'];process=json.loads((root/'execution/manifest.json').read_text());originalRoot=Path(process['original_executable']).parent
def local(path):return root/Path(path).relative_to(originalRoot)
def sha(d):return hashlib.sha256(d).hexdigest()
def u32(d,o):return struct.unpack_from('<I',d,o)[0]
def u64(d,o):return struct.unpack_from('<Q',d,o)[0]
def guards(data):assert data[:64]==data[-64:]==b'\xa5'*64
def output_oracle(raw,counter,seed,groups,local_size,copies,disabled=False):
 guards(raw);guards(counter);assert len(raw)==10368 and len(counter)==132;n=groups*local_size
 assert u32(counter,64)==(0 if disabled else n*copies)
 if disabled:assert raw==b'\xa5'*len(raw);return 0
 expected=[]
 for i in range(n):expected.extend([((seed*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,groups|0x01010000,local_size])
 assert list(struct.unpack_from('<'+str(n*4)+'I',raw,64))==expected and raw[64+n*16:-64]==b'\xa5'*(640-n)*16;return n*4
assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status']
assert result['passed'] and not result['system_modifications'] and not result['ICB_implemented'] and result['integration_level']==1
out=root/'outputs';original=(out/'original.commands.bin').read_bytes();relocated=(out/'relocated.commands.bin').read_bytes();assert len(original)==len(relocated)==464
assert sha(original)==info['original_SHA256'] and sha(relocated)==info['relocated_SHA256'];packets=decode(original);changed=decode(relocated);assert len(packets)==len(changed)==9
geometry=packets[2]['offset']+4;qmd=packets[5]['offset']+4
assert packets[2]['method']=='0x1b4' and len(packets[2]['values'])==32 and len(packets[5]['values'])==64
expected=bytearray(original)
for offset,value in [(12,(info['dedicated_CB_GPU_address']+0x6f0)>>32),(16,(info['dedicated_CB_GPU_address']+0x6f0)&0xffffffff),(168,info['dedicated_QMD_GPU_address']>>32),(172,info['dedicated_QMD_GPU_address']&0xffffffff),(qmd+0x7c,info['dedicated_CB_GPU_address']&0xffffffff),(qmd+0x80,(u32(original,qmd+0x80)&0xffffff00)|(info['dedicated_CB_GPU_address']>>32)),(444,info['dedicated_QMD_GPU_address']>>8)]:struct.pack_into('<I',expected,offset,value)
assert relocated==expected,'Unexpected packet change outside relocation fields'
assert changed[6]['values']==[info['dedicated_QMD_GPU_address']>>8] and changed[7]['method']=='0x2bc' and changed[7]['values']==[3]
nativeCB=(out/'native.constants.bin').read_bytes();nativeQMD=(out/'native.descriptor.bin').read_bytes();guards(nativeCB);guards(nativeQMD);nativeCB=nativeCB[64:-64];nativeQMD=nativeQMD[64:-64]
assert nativeQMD[:256]==original[qmd:qmd+256] and nativeCB[0x6f0:0x770]==original[geometry:geometry+128]
assert u64(nativeCB,8)==info['output_GPU_address']+64 and u64(nativeCB,40)==info['counter_GPU_address']+64 and u64(nativeCB,72)==info['parameters_GPU_address']
groups=result['groups'];local_size=result['local'];nop_record=result.get('record_preparation_user_kernel_executed') is False
if nop_record:
 preparation=(out/'record-preparation.commands.bin').read_bytes();wanted=bytearray(original);struct.pack_into('<II',wanted,448,(u32(original,448)&~0x1fff)|(0x100//4),0);assert preparation==wanted and result['reference_native_invocations']==0
positive_words=output_oracle((out/'reference.output.bin').read_bytes(),(out/'reference.counter.bin').read_bytes(),0x1234,groups,local_size,1,disabled=nop_record);positive_invocations=0;positive_trials=negative_trials=0;records=[]
assert len(result['rejections'])==3 and all(x['rejected'] and not x['GPU_replay'] for x in result['rejections'])
for run in result['runs']:
 base=local(run['base']);stream=Path(str(base)+'.commands.bin').read_bytes();evidence=run['evidence'];copies=run['copies'];disabled=evidence['launches_suppressed'];single=bytearray(relocated)
 if disabled:struct.pack_into('<II',single,info['launch_header_offset'],(u32(single,info['launch_header_offset'])&~0x1fff)|(0x100//4),0)
 assert stream==single*copies and sha(stream)==evidence['stream_SHA256'] and len(stream)==evidence['command_bytes']==464*copies
 assert evidence['cursor_after']-evidence['cursor_before']==len(stream) and evidence['native_preparation_GPU_dispatches']==0 and evidence['native_preparation_API_calls']==1
 if not run['GPU_replay']:
  assert result['mode']=='prepare' and not run['committed'];records.append({'variant':run['variant'],'status':'PASS_PREPARATION_NOT_SUBMITTED'});continue
 assert result['mode']=='execute' and run['command_status']==4 and run['mismatches']==run['guard_mismatches']==0
 seed=0x1234+37*run['iteration'];assert run['seed']==seed
 raw=Path(str(base)+'.output.bin').read_bytes();counter=Path(str(base)+'.counter.bin').read_bytes();words=output_oracle(raw,counter,seed,groups,local_size,copies,disabled)
 assert u32(counter,64)==run['actual_invocations']==run['expected_invocations']
 cb=Path(str(base)+'.constants.bin').read_bytes();desc=Path(str(base)+'.descriptor.bin').read_bytes();guards(cb);guards(desc);assert cb[64:-64]==nativeCB and desc[64:64+256]==relocated[qmd:qmd+256]
 if disabled:negative_trials+=1
 else:positive_trials+=1;positive_words+=words;positive_invocations+=groups*local_size*copies
 records.append({'iteration':run['iteration'],'copies':copies,'status':'PASS_LAUNCH_SUPPRESSION_CONTROL' if disabled else 'PASS_GPU_REPLAY','actual_invocations':run['actual_invocations'],'output_SHA256':sha(raw),'stream_SHA256':sha(stream)})
inputs=json.loads((root/'inputs.json').read_text())
for file,h in inputs['source_hashes'].items():assert sha((root/file).read_bytes())==h
assert sha((root/'indirect_compute_probe.metallib').read_bytes())==inputs['library_SHA256']==result['source_library_SHA256']
summary={'status':'PASS','mode':result['mode'],'geometry':[groups,local_size],'recorded_native_reference_invocations':groups*local_size,'positive_replay_trials':positive_trials,'launch_suppression_controls':negative_trials,'replayed_consumer_invocations':positive_invocations,'correct_uint32_words_including_reference':positive_words,'constant_snapshot_bytes_preserved':65536,'rejected_templates':3,'packet_relocation_only_expected_fields':True,'ICB_implemented':False,'integration_level':1,'system_modifications':False,'performance_benchmark':False,'scope':'Pinned native packet prototype, one frozen pipeline/binding/geometry profile reused with changing seeds and copies. Source preparation is removed before submission; no-launch controls verify no residual native preparation kernel. No arbitrary shader/state, ICB API or transparent integration claim.','records':records}
if nop_record:summary.update(recorded_native_reference_invocations=0,record_materialized_without_user_kernel=True)
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
