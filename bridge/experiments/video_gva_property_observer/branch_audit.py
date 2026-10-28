#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the exact cache branch following the observed GVA codec property read."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]/'tools'))
from inspect_video_cache import Cache
REGION='f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19';META='22da58007d8e29451d363e0e726752e71b4e883823f33be5488ae2cb84fa24d8';MAP='2d9c4ed04bcdbdd4049bb7ed88f0a545d3f42b1b478ab320e43fc8feb6a39ffd'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(x,s):
 if not x:raise ValueError(s)
def branch(data,start):
 def at(offset,pattern):
  i=offset-start;need(i>=0 and data[i:i+len(pattern)]==pattern,'instruction differs at '+str(offset))
 at(150807,b'\xe8');at(150812,b'\x48\x85\xc0');at(150815,b'\x74');at(150821,b'\xc6\x86\x63\x04\x00\x00\x01');at(150845,b'\xe8')
 rel=struct.unpack_from('<b',data,150816-start)[0];target=150817+rel;need(target==150858 and target>150845,'null branch target differs');return {'null_branch_target':target,'nonnull_flag_write_offset':150821,'nonnull_string_call_offset':150845}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for arg in ('cache','capture','mapping','host','out'):p.add_argument('--'+arg,type=Path,required=True)
 a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');mfile=a.capture/'metadata.json';need(sha(mfile.read_bytes())==META and sha(a.mapping.read_bytes())==MAP,'metadata or mapping differs');m=json.loads(mfile.read_text());r=m['region'];payload=(a.capture/'function-region.private.bin').read_bytes();need(m['image']['UUID']=='ca5414f369373c059ea2d82b35afd4f0' and r['SHA256']==REGION and sha(payload)==REGION and r['boundary_source']=='LC_FUNCTION_STARTS','capture differs');need(sha(Cache(a.cache.resolve()).read(r['start_VM'],r['bytes']))==REGION,'current cache differs')
 mapped=json.loads(a.mapping.read_text());need(mapped['status']=='STATIC_ONLY' and mapped['source_region_SHA256']==REGION and not mapped['runtime_target_proved'],'static map differs');rows={e['caller_offset']:e for e in mapped['rows']};need('_IORegistryEntryCreateCFProperty' in rows[150807]['exact_defined_symbols'] and '_CFStringGetCString' in rows[150845]['exact_defined_symbols'],'mapped targets differ')
 trace=(a.host/'execution/execution.stderr').read_text();wanted='KM_PROPERTY offset=150812 profile=1 id_ok=1 registry=4294968416 class=nvAccelerator key=IOGVACodec options=0 present=0 type=0 numeric_ok=0 numeric=0 text=NONE';need(trace.splitlines().count(wanted)==1,'runtime witness differs');manifest=json.loads((a.host/'execution/manifest.json').read_text());need(manifest['exit_code']==0 and manifest['GPU_reservation']['state']=='terminal' and not manifest['authoritative_ps_status'],'host not terminal')
 result={'status':'PASS','GVA_UUID':m['image']['UUID'],'region_SHA256':REGION,'runtime_property_result_present':False,'property_call_offset':150807,'runtime_return_offset':150812,**branch(payload,r['start_VM']-m['image_base_VM']),'inference':'Null return follows pinned conditional branch, skipping this flag write and string conversion; later node state is not independently observed.','resident_code_pin_in_witness':True,'hardware_video_execution_proved':False,'system_modified':False}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
