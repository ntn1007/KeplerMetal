#!/usr/bin/env python3
"""Check captured encoding layouts and guards; never credit a GPU dispatch."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--suite',type=Path,required=True);p.add_argument('--m1',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
rows=[];local_source=None
for case in json.loads((a.suite/'history.json').read_text()):
 root=ROOT/'results'/Path(case['directory']).name;d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text());mode=case['case'];r=d['runs'][0]
 assert case['exit_code']==0 and m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 assert inp['static_library_SHA256']=='d88158307ed566d1a048f7f729c2896419c6836b3f44899ab6711a59850456fc'
 local_source=inp['source_hashes']['argument_encoder_boundary_probe.mm']
 assert d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458 and not d['GPU_execution']and len(d['runs'])==1 and not r['GPU_dispatch']and not r['command_buffers_submitted']and r['device_class_restored']
 if mode=='buffer':
  assert r['status']=='ACCEPTED_CPU_ONLY'and r['stage']=='setBuffer'and r['encoded_length']==r['alignment']==8
  raw=(root/'outputs/encoded-root.bin').read_bytes();assert len(raw)==136 and raw[:64]==raw[-64:]==b'\xa5'*64 and raw[64:72]!=b'\xa5'*8
 elif mode=='scope_identity':
  assert r['status']=='EXCEPTION'and r['stage']=='read_scoped_gpuResourceID'and r['exception_name']=='KeplerCPUICBUnsupported'and r['exception_reason']=='GPU argument-buffer ICB identity is not implemented'and not r['native_encoder_used']
  assert any(e.get('operation')=='scope_restore'and e['device_class_restored']for e in r['scope_events'])
 else:assert mode in ['pipeline','icb','scope_icb']and r['status']=='UNSUPPORTED_ENCODER_LAYOUT'and r['encoded_length']==0 and r['alignment']==1 and r['stage']=='newArgumentEncoderWithArguments'and r['local_layout_guard']and not r['root_files']
 rows.append({'host':'GTX 880M','mode':mode,'observation':r,'results_SHA256':sha(root/'results.json'),'directory':str(root)})
assert len(rows)==5
ref=a.m1/'Reference';receipt=json.loads((a.m1/'receipt.json').read_text());assert receipt['status']=='PASS'and not receipt['GPU_dispatch'];manifest=json.loads((ref/'REFERENCE_RETURN.json').read_text())
for e in manifest['files']:assert sha(ref/e['path'])==e['SHA256']and(ref/e['path']).stat().st_size==e['bytes']
assert sha(ref/'argument_encoder_boundary_probe.mm')==local_source
summary=json.loads((ref/'results/summary.json').read_text());assert summary['machine']=='arm64'and not summary['GPU_dispatch']and len(summary['rows'])==3
for row in summary['rows']:
 assert row['exit_code']==0 and not row['ps_after'];d=row['result'];r=d['runs'][0];assert d['device']=='Apple M1 Max'and not d['GPU_execution']and not r['command_buffers_submitted']and not r['GPU_dispatch']and r['device_class_restored']and r['status']=='ACCEPTED_CPU_ONLY'and r['encoded_length']==r['alignment']==8
 raw=(ref/'results'/row['mode']/'encoded-root.bin').read_bytes();assert len(raw)==136 and raw[:64]==raw[-64:]==b'\xa5'*64 and raw[64:72]!=b'\xa5'*8
 rows.append({'host':'Apple M1 Max','mode':row['mode'],'observation':r})
result={'evidence_integrity':'PASS','observations':8,'GTX_command_buffers_submitted':0,'M1_command_buffers_submitted':0,'same_probe_source_SHA256':local_source,'GTX_build_flags':'x86_64, KP_ARGUMENT_NATIVE=0 (default), static runtime d881','M1_build_flags':'arm64, KP_ARGUMENT_NATIVE=1, Apple native driver','native_ICB_GPU_execution_proven':False,'existing_scope_ICB_identity_supported':False,'full_objective_complete':False,'rows':rows}
with a.out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items()if k!='rows'}))
